from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.services.facebook_service import (
    HANDOVER_MESSAGE,
    MessengerTextMessage,
    extract_text_messages,
    log_facebook_event,
    parse_payload,
    should_handover,
    state_store,
    verify_signature,
    verify_webhook_challenge,
)
from app.services.lambda_service import call_bot
from app.services.messenger_service import MessengerAPIError, send_text_message

router = APIRouter(prefix="/facebook", tags=["facebook"])


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_facebook_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    verified_challenge = verify_webhook_challenge(mode, token, challenge)
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
    if not verify_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid Facebook signature.")

    payload = parse_payload(raw_body)
    for message in extract_text_messages(payload):
        if await state_store.is_duplicate(message.message_id):
            log_facebook_event(
                psid=message.psid,
                user_message=message.text,
                bot_response=None,
                message_id=message.message_id,
                event="duplicate_ignored",
            )
            continue

        await state_store.mark_processed(message.message_id)
        if await state_store.is_human_mode(message.psid):
            log_facebook_event(
                psid=message.psid,
                user_message=message.text,
                bot_response=None,
                message_id=message.message_id,
                event="human_mode_ignored",
            )
            continue

        background_tasks.add_task(process_messenger_message, message)

    return {"status": "ok"}


async def process_messenger_message(message: MessengerTextMessage) -> None:
    try:
        bot_result = await call_bot(
            user_id=message.psid,
            message=message.text,
            page_id=message.page_id,
        )
        if should_handover(bot_result):
            await state_store.enable_human_mode(message.psid)
            await send_text_message(message.psid, HANDOVER_MESSAGE)
            log_facebook_event(
                psid=message.psid,
                user_message=message.text,
                bot_response=HANDOVER_MESSAGE,
                message_id=message.message_id,
                event="handover_enabled",
                extra={
                    "intent": bot_result.get("intent"),
                    "confidence": bot_result.get("confidence"),
                },
            )
            return

        reply = bot_result.get("reply") or "Em chưa có câu trả lời phù hợp lúc này."
        await send_text_message(message.psid, reply)
        log_facebook_event(
            psid=message.psid,
            user_message=message.text,
            bot_response=reply,
            message_id=message.message_id,
            event="bot_replied",
            extra={
                "intent": bot_result.get("intent"),
                "confidence": bot_result.get("confidence"),
            },
        )
    except MessengerAPIError as exc:
        log_facebook_event(
            psid=message.psid,
            user_message=message.text,
            bot_response=None,
            message_id=message.message_id,
            event="graph_api_error",
            extra={"error": str(exc)},
        )
    except Exception as exc:
        log_facebook_event(
            psid=message.psid,
            user_message=message.text,
            bot_response=None,
            message_id=message.message_id,
            event="bot_processing_error",
            extra={"error": str(exc)},
        )
