from __future__ import annotations

from typing import Any

from app.domain import ConversationStatus, SenderType
from app.repositories import ConversationRepository


class EventService:
    def __init__(self, repository: ConversationRepository) -> None:
        self.repository = repository

    async def create_event(
        self,
        *,
        conversation_id: str,
        event_type: str,
        actor_type: SenderType,
        actor_id: str | None = None,
        from_status: ConversationStatus | str | None = None,
        to_status: ConversationStatus | str | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ):
        return await self.repository.create_event(
            conversation_id=conversation_id,
            event_type=event_type,
            actor_type=actor_type.value if hasattr(actor_type, "value") else actor_type,
            actor_id=actor_id,
            from_status=from_status.value if hasattr(from_status, "value") else from_status,
            to_status=to_status.value if hasattr(to_status, "value") else to_status,
            reason=reason,
            payload=payload,
        )
