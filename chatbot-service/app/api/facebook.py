from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.adapters.base import InboundMessage
from app.adapters.facebook import FacebookAdapter
from app.core.config import settings
from app.core.database import get_pool
from app.domain import ConversationStatus, MessageStatus, SenderType
from app.repositories import PostgresConversationRepository
from app.services.agent_service import AgentService
from app.services.bot_orchestrator import BotOrchestrator
from app.services.conversation_service import ConversationService
from app.services.event_service import EventService
from app.services.facebook_service import (
    HANDOVER_MESSAGE,
    RESUME_BOT_MESSAGE,
    MessengerAdminCommand,
    is_customer_resume_command,
    log_facebook_event,
    state_store,
)
from app.services.message_service import MessageService
from app.services.realtime_service import RealtimeService

router = APIRouter(prefix="/facebook", tags=["facebook"])
facebook_adapter = FacebookAdapter()
realtime = RealtimeService()


@dataclass(frozen=True)
class InboundPersistResult:
    conversation_id: str | None = None
    process_bot: bool = False
    customer_resume: bool = False


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_facebook_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    verified_challenge = facebook_adapter.verify_challenge(mode, token, challenge)
    if verified_challenge is None:
        raise HTTPException(status_code=403, detail="Facebook webhook verification failed.")
    return PlainTextResponse(verified_challenge)


@router.post("/webhook")
async def receive_facebook_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    raw_body = await request.body()
    if not facebook_adapter.verify_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid Facebook signature.")

    payload = facebook_adapter.parse_webhook_payload(raw_body)

    for command in facebook_adapter.parse_admin_commands(payload):
        if await state_store.is_duplicate(command.message_id):
            continue
        await state_store.mark_processed(command.message_id)
        await handle_admin_command(command)

    for inbound in facebook_adapter.parse_inbound_event(payload):
        if await state_store.is_duplicate(inbound.external_message_id):
            await _log(
                event="duplicate_ignored",
                inbound=inbound,
                conversation_id=None,
            )
            continue

        await state_store.mark_processed(inbound.external_message_id)
        result = await persist_inbound_message(inbound)
        if result.customer_resume and result.conversation_id:
            background_tasks.add_task(send_customer_resume_notice, result.conversation_id, inbound)
        elif result.process_bot and result.conversation_id:
            background_tasks.add_task(
                process_bot_reply,
                result.conversation_id,
                inbound.text,
                inbound.external_message_id,
            )

    return {"status": "ok"}


async def handle_admin_command(command: MessengerAdminCommand) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            repo = PostgresConversationRepository(conn)
            conversations = ConversationService(repo)
            conversation = await conversations.find_or_create(
                channel="MESSENGER",
                channel_account_id=command.page_id or "default",
                external_user_id=command.psid,
                metadata={"source": "facebook_admin_command"},
            )
            await repo.lock_conversation(conversation.id)

    agent = AgentService(PostgresConversationRepository(pool), facebook_adapter)
    await agent.return_to_bot(conversation.id, agent_id="page-admin")
    await state_store.disable_human_mode(command.psid)
    await _log(
        event="resume_bot_admin",
        inbound=InboundMessage(
            channel="MESSENGER",
            channel_account_id=command.page_id or "default",
            external_user_id=command.psid,
            external_message_id=command.message_id,
            text=command.text,
            timestamp=command.timestamp,
            is_admin_echo=True,
        ),
        conversation_id=conversation.id,
        extra={"trigger": "admin_command"},
    )


async def persist_inbound_message(inbound: InboundMessage) -> InboundPersistResult:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            repo = PostgresConversationRepository(conn)
            events = EventService(repo)
            conversations = ConversationService(repo, events)
            messages = MessageService(repo)

            conversation = await conversations.find_or_create(
                channel=inbound.channel,
                channel_account_id=inbound.channel_account_id,
                external_user_id=inbound.external_user_id,
                metadata={"source": "facebook"},
            )
            await repo.lock_conversation(conversation.id)

            existing = await repo.find_message_by_external_id(inbound.channel, inbound.external_message_id)
            if existing:
                await _log("db_duplicate_ignored", inbound, conversation.id)
                return InboundPersistResult()

            if conversation.status == ConversationStatus.CLOSED:
                conversation = await conversations.reopen(
                    conversation,
                    actor_type=SenderType.CUSTOMER,
                    actor_id=inbound.external_user_id,
                )

            await messages.create_inbound(
                conversation_id=conversation.id,
                channel=inbound.channel,
                external_message_id=inbound.external_message_id,
                sender_id=inbound.external_user_id,
                content=inbound.text,
                correlation_id=inbound.external_message_id,
                metadata={
                    "channel_account_id": inbound.channel_account_id,
                    "timestamp": inbound.timestamp,
                },
            )
            await conversations.touch_customer_message(conversation.id)

            if await state_store.consume_expired_handover(inbound.external_user_id):
                await _log("handover_expired", inbound, conversation.id)

            legacy_human_mode = await state_store.is_human_mode(inbound.external_user_id)
            customer_resume = settings.enable_customer_resume_bot and is_customer_resume_command(inbound.text)
            if customer_resume:
                if conversation.status != ConversationStatus.BOT_ACTIVE:
                    await conversations.return_to_bot(
                        conversation,
                        actor_type=SenderType.CUSTOMER,
                        actor_id=inbound.external_user_id,
                        reason="customer_resume_command",
                    )
                await state_store.disable_human_mode(inbound.external_user_id)
                await realtime.broadcast("conversation.updated", {"conversation_id": conversation.id})
                return InboundPersistResult(conversation.id, customer_resume=True)

            if legacy_human_mode:
                if conversation.status == ConversationStatus.BOT_ACTIVE:
                    await conversations.mark_waiting_agent(
                        conversation,
                        reason="legacy_redis_human_mode",
                        actor_type=SenderType.SYSTEM,
                        actor_id="legacy-redis",
                    )
                await state_store.disable_human_mode(inbound.external_user_id)
                await _log("legacy_human_mode_synced", inbound, conversation.id)
                await realtime.broadcast("message.created", {"conversation_id": conversation.id})
                return InboundPersistResult()

            if not conversations.can_process_by_bot(conversation):
                await _log("agent_mode_inbound_saved", inbound, conversation.id, extra={"status": conversation.status.value})
                await realtime.broadcast("message.created", {"conversation_id": conversation.id})
                return InboundPersistResult()

            await _log("inbound_saved", inbound, conversation.id, extra={"status": conversation.status.value})
            return InboundPersistResult(conversation.id, process_bot=True)


async def send_customer_resume_notice(conversation_id: str, inbound: InboundMessage) -> None:
    pool = await get_pool()
    repo = PostgresConversationRepository(pool)
    conversation = await repo.get_conversation(conversation_id)
    if not conversation:
        return

    messages = MessageService(repo)
    outbound = await messages.create_outbound(
        conversation_id=conversation.id,
        channel=conversation.channel,
        sender_type=SenderType.SYSTEM,
        sender_id="system",
        content=RESUME_BOT_MESSAGE,
        status=MessageStatus.PROCESSING,
        correlation_id=inbound.external_message_id,
    )
    try:
        await facebook_adapter.send_message(conversation.external_user_id, RESUME_BOT_MESSAGE)
    except Exception as exc:
        await messages.mark_failed(outbound.id, str(exc))
        await _log(
            "resume_bot_customer_failed",
            inbound,
            conversation.id,
            extra={"error": str(exc)},
        )
        return

    await messages.mark_sent(outbound.id)
    await ConversationService(repo).touch_bot_message(conversation.id)
    await EventService(repo).create_event(
        conversation_id=conversation.id,
        event_type="RESUME_BOT_CUSTOMER_NOTICE_SENT",
        actor_type=SenderType.SYSTEM,
        actor_id="system",
    )
    await _log(
        "resume_bot_customer",
        inbound,
        conversation.id,
        bot_response=RESUME_BOT_MESSAGE,
        extra={"trigger": "customer_command"},
    )


async def process_bot_reply(conversation_id: str, text: str, correlation_id: str) -> None:
    pool = await get_pool()
    repo = PostgresConversationRepository(pool)
    conversation = await repo.get_conversation(conversation_id)
    if not conversation or conversation.status != ConversationStatus.BOT_ACTIVE:
        return

    bot_result = await BotOrchestrator().process_customer_message(conversation=conversation, message=text)
    reply = HANDOVER_MESSAGE if bot_result.handover else (bot_result.reply or "Em chưa có câu trả lời phù hợp lúc này.")

    async with pool.acquire() as conn:
        async with conn.transaction():
            tx_repo = PostgresConversationRepository(conn)
            await tx_repo.lock_conversation(conversation_id)
            conversation = await tx_repo.get_conversation(conversation_id)
            if not conversation or conversation.status != ConversationStatus.BOT_ACTIVE:
                return

            conversations = ConversationService(tx_repo)
            messages = MessageService(tx_repo)
            if bot_result.handover:
                conversation = await conversations.mark_waiting_agent(
                    conversation,
                    reason=_handover_reason(bot_result),
                    actor_type=SenderType.BOT,
                    actor_id="bot",
                    payload={
                        "intent": bot_result.intent,
                        "confidence": bot_result.confidence,
                        "escalation": bot_result.escalation,
                    },
                )

            outbound = await messages.create_outbound(
                conversation_id=conversation.id,
                channel=conversation.channel,
                sender_type=SenderType.BOT,
                sender_id="bot",
                content=reply,
                payload=_first_payload(bot_result.messages),
                intent=bot_result.intent,
                confidence=bot_result.confidence,
                status=MessageStatus.PROCESSING,
                correlation_id=correlation_id,
                metadata=bot_result.metadata,
            )

    try:
        if bot_result.handover:
            await facebook_adapter.send_message(conversation.external_user_id, reply)
        else:
            await facebook_adapter.send_bot_messages(conversation.external_user_id, reply, bot_result.messages)
    except Exception as exc:
        await MessageService(repo).mark_failed(outbound.id, str(exc))
        await _log(
            event="outbound_failed",
            inbound=InboundMessage(
                channel=conversation.channel,
                channel_account_id=conversation.channel_account_id,
                external_user_id=conversation.external_user_id,
                external_message_id=correlation_id,
                text=text,
            ),
            conversation_id=conversation.id,
            extra={"error": str(exc), "intent": bot_result.intent, "confidence": bot_result.confidence},
        )
        return

    await MessageService(repo).mark_sent(outbound.id)
    await ConversationService(repo).touch_bot_message(conversation.id)
    await EventService(repo).create_event(
        conversation_id=conversation.id,
        event_type="BOT_MESSAGE_SENT" if not bot_result.handover else "HANDOVER_MESSAGE_SENT",
        actor_type=SenderType.BOT,
        actor_id="bot",
        payload={"intent": bot_result.intent, "confidence": bot_result.confidence},
    )
    await realtime.broadcast("message.created", {"conversation_id": conversation.id})
    await _log(
        event="handover_start" if bot_result.handover else "bot_replied",
        inbound=InboundMessage(
            channel=conversation.channel,
            channel_account_id=conversation.channel_account_id,
            external_user_id=conversation.external_user_id,
            external_message_id=correlation_id,
            text=text,
        ),
        conversation_id=conversation.id,
        bot_response=reply,
        extra={"intent": bot_result.intent, "confidence": bot_result.confidence, "status": conversation.status.value},
    )


def _handover_reason(bot_result) -> str:
    if bot_result.escalation and bot_result.escalation.get("reason"):
        return str(bot_result.escalation["reason"])
    if bot_result.intent:
        return str(bot_result.intent)
    return "bot_handover"


def _first_payload(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for message in messages:
        payload = message.get("payload")
        if isinstance(payload, dict):
            return payload
    return None


async def _log(
    event: str,
    inbound: InboundMessage,
    conversation_id: str | None,
    *,
    bot_response: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    log_facebook_event(
        psid=inbound.external_user_id,
        user_message=inbound.text,
        bot_response=bot_response,
        message_id=inbound.external_message_id,
        event=event,
        extra={
            "correlation_id": inbound.external_message_id,
            "channel": inbound.channel,
            "channel_account_id": inbound.channel_account_id,
            "external_user_id": inbound.external_user_id,
            "external_message_id": inbound.external_message_id,
            "conversation_id": conversation_id,
            **(extra or {}),
        },
    )
