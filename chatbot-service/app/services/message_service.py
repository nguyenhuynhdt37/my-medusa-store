from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain import MessageDirection, MessageStatus, SenderType
from app.repositories import ConversationRepository


class MessageService:
    def __init__(self, repository: ConversationRepository) -> None:
        self.repository = repository

    async def create_inbound(
        self,
        *,
        conversation_id: str,
        channel: str,
        external_message_id: str | None,
        sender_id: str | None,
        content: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        return await self.repository.create_message(
            conversation_id=conversation_id,
            channel=channel,
            external_message_id=external_message_id,
            direction=MessageDirection.INBOUND.value,
            sender_type=SenderType.CUSTOMER.value,
            sender_id=sender_id,
            content=content,
            payload=payload,
            status=MessageStatus.RECEIVED.value,
            correlation_id=correlation_id,
            metadata=metadata,
        )

    async def create_outbound(
        self,
        *,
        conversation_id: str,
        channel: str,
        sender_type: SenderType,
        sender_id: str | None,
        content: str,
        payload: dict[str, Any] | None = None,
        intent: str | None = None,
        confidence: float | None = None,
        status: MessageStatus = MessageStatus.PROCESSING,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        return await self.repository.create_message(
            conversation_id=conversation_id,
            channel=channel,
            direction=MessageDirection.OUTBOUND.value,
            sender_type=sender_type.value,
            sender_id=sender_id,
            content=content,
            payload=payload,
            intent=intent,
            confidence=confidence,
            status=status.value,
            correlation_id=correlation_id,
            metadata=metadata,
        )

    async def mark_sent(self, message_id: str):
        return await self.repository.update_message(
            message_id,
            status=MessageStatus.SENT.value,
            sent_at=datetime.now(timezone.utc),
        )

    async def mark_failed(self, message_id: str, error_message: str):
        return await self.repository.update_message(
            message_id,
            status=MessageStatus.FAILED.value,
            error_message=error_message,
        )
