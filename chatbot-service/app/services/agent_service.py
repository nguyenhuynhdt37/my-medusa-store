from __future__ import annotations

from app.adapters.base import ChannelAdapter
from app.domain import ConversationStatus, MessageStatus, SenderType
from app.repositories import ConversationRepository
from app.services.chat_constants import RESUME_BOT_MESSAGE
from app.services.conversation_service import ConversationService, InvalidConversationTransition
from app.services.event_service import EventService
from app.services.message_service import MessageService


class AgentService:
    def __init__(
        self,
        repository: ConversationRepository,
        channel_adapter: ChannelAdapter,
    ) -> None:
        self.repository = repository
        self.channel_adapter = channel_adapter
        self.events = EventService(repository)
        self.conversations = ConversationService(repository, self.events)
        self.messages = MessageService(repository)

    async def take_conversation(self, conversation_id: str, *, agent_id: str, assigned_by: str | None = None):
        conversation = await self._get(conversation_id)
        return await self.conversations.assign_agent(conversation, agent_id=agent_id, assigned_by=assigned_by)

    async def send_agent_message(self, conversation_id: str, *, agent_id: str, text: str):
        conversation = await self._get(conversation_id)
        if conversation.status not in {
            ConversationStatus.WAITING_AGENT,
            ConversationStatus.AGENT_ASSIGNED,
            ConversationStatus.AGENT_ACTIVE,
        }:
            raise InvalidConversationTransition("Agent can only message conversations waiting for or assigned to agents.")

        if conversation.status == ConversationStatus.WAITING_AGENT:
            conversation = await self.conversations.assign_agent(conversation, agent_id=agent_id, assigned_by=agent_id, activate=True)
        elif conversation.status == ConversationStatus.AGENT_ASSIGNED:
            previous_status = conversation.status
            conversation = await self.repository.update_conversation(
                conversation.id,
                status=ConversationStatus.AGENT_ACTIVE.value,
            )
            await self.events.create_event(
                conversation_id=conversation.id,
                event_type="AGENT_ACTIVE",
                actor_type=SenderType.AGENT,
                actor_id=agent_id,
                from_status=previous_status,
                to_status=ConversationStatus.AGENT_ACTIVE,
            )

        message = await self.messages.create_outbound(
            conversation_id=conversation.id,
            channel=conversation.channel,
            sender_type=SenderType.AGENT,
            sender_id=agent_id,
            content=text,
            status=MessageStatus.PROCESSING,
        )
        try:
            await self.channel_adapter.send_message(conversation.external_user_id, text)
        except Exception as exc:
            await self.messages.mark_failed(message.id, str(exc))
            await self.events.create_event(
                conversation_id=conversation.id,
                event_type="AGENT_MESSAGE_FAILED",
                actor_type=SenderType.AGENT,
                actor_id=agent_id,
                reason=str(exc),
            )
            raise

        sent = await self.messages.mark_sent(message.id)
        await self.conversations.touch_agent_message(conversation.id)
        await self.events.create_event(
            conversation_id=conversation.id,
            event_type="AGENT_MESSAGE_SENT",
            actor_type=SenderType.AGENT,
            actor_id=agent_id,
        )
        return sent

    async def return_to_bot(self, conversation_id: str, *, agent_id: str):
        conversation = await self._get(conversation_id)
        updated = await self.conversations.return_to_bot(conversation, actor_id=agent_id)
        message = await self.messages.create_outbound(
            conversation_id=conversation.id,
            channel=conversation.channel,
            sender_type=SenderType.SYSTEM,
            sender_id="system",
            content=RESUME_BOT_MESSAGE,
            status=MessageStatus.PROCESSING,
        )
        try:
            await self.channel_adapter.send_message(conversation.external_user_id, message.content or "")
        except Exception as exc:
            await self.messages.mark_failed(message.id, str(exc))
            raise
        await self.messages.mark_sent(message.id)
        await self.conversations.touch_bot_message(conversation.id)
        return updated

    async def close_conversation(self, conversation_id: str, *, agent_id: str):
        conversation = await self._get(conversation_id)
        return await self.conversations.close(conversation, actor_id=agent_id)

    async def reopen_conversation(self, conversation_id: str, *, agent_id: str):
        conversation = await self._get(conversation_id)
        return await self.conversations.reopen(conversation, actor_type=SenderType.AGENT, actor_id=agent_id)

    async def _get(self, conversation_id: str):
        conversation = await self.repository.get_conversation(conversation_id)
        if not conversation:
            raise KeyError(f"Conversation not found: {conversation_id}")
        return conversation
