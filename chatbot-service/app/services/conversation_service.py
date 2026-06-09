from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain import (
    AssignmentStatus,
    Conversation,
    ConversationOwner,
    ConversationStatus,
    SenderType,
)
from app.repositories import ConversationRepository
from app.services.event_service import EventService


class InvalidConversationTransition(RuntimeError):
    pass


class ConversationService:
    def __init__(self, repository: ConversationRepository, event_service: EventService | None = None) -> None:
        self.repository = repository
        self.events = event_service or EventService(repository)

    async def find_or_create(
        self,
        *,
        channel: str,
        channel_account_id: str,
        external_user_id: str,
        external_conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        conversation = await self.repository.find_conversation(channel, channel_account_id, external_user_id)
        if conversation:
            return conversation
        conversation = await self.repository.create_conversation(
            channel=channel,
            channel_account_id=channel_account_id,
            external_user_id=external_user_id,
            external_conversation_id=external_conversation_id,
            metadata=metadata,
        )
        await self.events.create_event(
            conversation_id=conversation.id,
            event_type="CONVERSATION_CREATED",
            actor_type=SenderType.SYSTEM,
            to_status=conversation.status,
        )
        return conversation

    def can_process_by_bot(self, conversation: Conversation) -> bool:
        return conversation.status == ConversationStatus.BOT_ACTIVE

    async def touch_customer_message(self, conversation_id: str) -> Conversation:
        now = datetime.now(timezone.utc)
        return await self.repository.update_conversation(
            conversation_id,
            last_message_at=now,
            last_customer_message_at=now,
        )

    async def touch_bot_message(self, conversation_id: str) -> Conversation:
        now = datetime.now(timezone.utc)
        return await self.repository.update_conversation(
            conversation_id,
            last_message_at=now,
            last_bot_message_at=now,
        )

    async def touch_agent_message(self, conversation_id: str) -> Conversation:
        now = datetime.now(timezone.utc)
        return await self.repository.update_conversation(
            conversation_id,
            last_message_at=now,
            last_agent_message_at=now,
        )

    async def mark_waiting_agent(
        self,
        conversation: Conversation,
        *,
        reason: str,
        actor_type: SenderType = SenderType.BOT,
        actor_id: str | None = "bot",
        payload: dict[str, Any] | None = None,
    ) -> Conversation:
        if conversation.status == ConversationStatus.CLOSED:
            raise InvalidConversationTransition("Closed conversation cannot move directly to WAITING_AGENT.")
        now = datetime.now(timezone.utc)
        updated = await self.repository.update_conversation(
            conversation.id,
            status=ConversationStatus.WAITING_AGENT.value,
            current_owner=ConversationOwner.AGENT.value,
            handover_reason=reason,
            handover_at=now,
            closed_at=None,
        )
        await self.events.create_event(
            conversation_id=conversation.id,
            event_type="HANDOVER_STARTED",
            actor_type=actor_type,
            actor_id=actor_id,
            from_status=conversation.status,
            to_status=ConversationStatus.WAITING_AGENT,
            reason=reason,
            payload=payload,
        )
        return updated

    async def assign_agent(
        self,
        conversation: Conversation,
        *,
        agent_id: str,
        assigned_by: str | None = None,
        activate: bool = False,
    ) -> Conversation:
        if conversation.status not in {
            ConversationStatus.WAITING_AGENT,
            ConversationStatus.AGENT_ASSIGNED,
            ConversationStatus.AGENT_ACTIVE,
        }:
            raise InvalidConversationTransition("Conversation is not available for agent assignment.")

        active = await self.repository.get_active_assignment(conversation.id)
        if active and active.agent_id != agent_id:
            raise InvalidConversationTransition("Conversation is already assigned to another agent.")
        if not active:
            await self.repository.create_assignment(
                conversation_id=conversation.id,
                agent_id=agent_id,
                assigned_by=assigned_by,
                status=AssignmentStatus.ACTIVE.value,
            )

        next_status = ConversationStatus.AGENT_ACTIVE if activate else ConversationStatus.AGENT_ASSIGNED
        updated = await self.repository.update_conversation(
            conversation.id,
            status=next_status.value,
            current_owner=ConversationOwner.AGENT.value,
            assigned_agent_id=agent_id,
        )
        await self.events.create_event(
            conversation_id=conversation.id,
            event_type="AGENT_ASSIGNED" if not activate else "AGENT_ACTIVE",
            actor_type=SenderType.AGENT,
            actor_id=agent_id,
            from_status=conversation.status,
            to_status=next_status,
        )
        return updated

    async def return_to_bot(
        self,
        conversation: Conversation,
        *,
        actor_id: str | None = None,
        actor_type: SenderType | None = None,
        reason: str | None = None,
    ) -> Conversation:
        await self.repository.release_active_assignments(conversation.id)
        updated = await self.repository.update_conversation(
            conversation.id,
            status=ConversationStatus.BOT_ACTIVE.value,
            current_owner=ConversationOwner.BOT.value,
            assigned_agent_id=None,
            returned_to_bot_at=datetime.now(timezone.utc),
            closed_at=None,
        )
        await self.events.create_event(
            conversation_id=conversation.id,
            event_type="RETURNED_TO_BOT",
            actor_type=actor_type or (SenderType.AGENT if actor_id else SenderType.SYSTEM),
            actor_id=actor_id,
            from_status=conversation.status,
            to_status=ConversationStatus.BOT_ACTIVE,
            reason=reason,
        )
        return updated

    async def close(
        self,
        conversation: Conversation,
        *,
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> Conversation:
        updated = await self.repository.update_conversation(
            conversation.id,
            status=ConversationStatus.CLOSED.value,
            current_owner=ConversationOwner.SYSTEM.value,
            closed_at=datetime.now(timezone.utc),
        )
        await self.events.create_event(
            conversation_id=conversation.id,
            event_type="CONVERSATION_CLOSED",
            actor_type=SenderType.AGENT if actor_id else SenderType.SYSTEM,
            actor_id=actor_id,
            from_status=conversation.status,
            to_status=ConversationStatus.CLOSED,
            reason=reason,
        )
        return updated

    async def reopen(self, conversation: Conversation, *, actor_type: SenderType, actor_id: str | None = None) -> Conversation:
        updated = await self.repository.update_conversation(
            conversation.id,
            status=ConversationStatus.BOT_ACTIVE.value,
            current_owner=ConversationOwner.BOT.value,
            closed_at=None,
        )
        await self.events.create_event(
            conversation_id=conversation.id,
            event_type="CONVERSATION_REOPENED",
            actor_type=actor_type,
            actor_id=actor_id,
            from_status=conversation.status,
            to_status=ConversationStatus.BOT_ACTIVE,
        )
        return updated
