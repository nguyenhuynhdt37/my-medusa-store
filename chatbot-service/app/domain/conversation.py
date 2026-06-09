from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConversationStatus(str, Enum):
    BOT_ACTIVE = "BOT_ACTIVE"
    WAITING_AGENT = "WAITING_AGENT"
    AGENT_ASSIGNED = "AGENT_ASSIGNED"
    AGENT_ACTIVE = "AGENT_ACTIVE"
    CLOSED = "CLOSED"


class ConversationOwner(str, Enum):
    BOT = "BOT"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class MessageDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class SenderType(str, Enum):
    CUSTOMER = "CUSTOMER"
    BOT = "BOT"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class MessageStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    SENT = "SENT"
    FAILED = "FAILED"


class AssignmentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    TRANSFERRED = "TRANSFERRED"


class Conversation(BaseModel):
    id: str
    channel: str
    channel_account_id: str
    external_user_id: str
    external_conversation_id: str | None = None
    customer_id: str | None = None
    guest_id: str | None = None
    status: ConversationStatus
    current_owner: ConversationOwner
    assigned_agent_id: str | None = None
    last_message_at: str | None = None
    last_customer_message_at: str | None = None
    last_agent_message_at: str | None = None
    last_bot_message_at: str | None = None
    handover_reason: str | None = None
    handover_at: str | None = None
    returned_to_bot_at: str | None = None
    closed_at: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class Message(BaseModel):
    id: str
    conversation_id: str
    channel: str
    external_message_id: str | None = None
    direction: MessageDirection
    sender_type: SenderType
    sender_id: str | None = None
    content_type: str = "text"
    content: str | None = None
    payload: dict[str, Any] | None = None
    intent: str | None = None
    confidence: float | None = None
    status: MessageStatus
    error_message: str | None = None
    correlation_id: str | None = None
    created_at: str
    sent_at: str | None = None
    metadata: dict[str, Any] | None = None


class ConversationAssignment(BaseModel):
    id: str
    conversation_id: str
    agent_id: str
    assigned_by: str | None = None
    status: AssignmentStatus
    assigned_at: str
    released_at: str | None = None
    metadata: dict[str, Any] | None = None


class ConversationEvent(BaseModel):
    id: str
    conversation_id: str
    event_type: str
    actor_type: SenderType
    actor_id: str | None = None
    from_status: ConversationStatus | None = None
    to_status: ConversationStatus | None = None
    reason: str | None = None
    payload: dict[str, Any] | None = None
    created_at: str


class BotReplyResult(BaseModel):
    reply: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    intent: str | None = None
    confidence: float | None = None
    fallback: bool = False
    handover: bool = False
    escalation: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
