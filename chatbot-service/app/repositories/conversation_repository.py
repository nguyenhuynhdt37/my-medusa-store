from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import uuid4

import asyncpg

from app.domain import (
    AssignmentStatus,
    Conversation,
    ConversationAssignment,
    ConversationEvent,
    ConversationOwner,
    ConversationStatus,
    Message,
    MessageDirection,
    MessageStatus,
    SenderType,
)


class ConversationRepository(Protocol):
    async def find_conversation(self, channel: str, channel_account_id: str, external_user_id: str) -> Conversation | None:
        ...

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        ...

    async def list_conversations(
        self,
        *,
        status: str | None = None,
        channel: str | None = None,
        assigned_agent_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        ...

    async def create_conversation(
        self,
        *,
        channel: str,
        channel_account_id: str,
        external_user_id: str,
        external_conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        ...

    async def update_conversation(self, conversation_id: str, **fields: Any) -> Conversation:
        ...

    async def find_message_by_external_id(self, channel: str, external_message_id: str) -> Message | None:
        ...

    async def create_message(self, **fields: Any) -> Message:
        ...

    async def update_message(self, message_id: str, **fields: Any) -> Message:
        ...

    async def list_messages(self, conversation_id: str, *, limit: int = 100, offset: int = 0) -> list[Message]:
        ...

    async def create_event(self, **fields: Any) -> ConversationEvent:
        ...

    async def list_events(self, conversation_id: str, *, limit: int = 100, offset: int = 0) -> list[ConversationEvent]:
        ...

    async def get_active_assignment(self, conversation_id: str) -> ConversationAssignment | None:
        ...

    async def create_assignment(self, **fields: Any) -> ConversationAssignment:
        ...

    async def release_active_assignments(self, conversation_id: str) -> None:
        ...

    async def lock_conversation(self, conversation_id: str) -> None:
        ...


class PostgresConversationRepository:
    def __init__(self, pool_or_conn: asyncpg.Pool | asyncpg.Connection) -> None:
        self.db = pool_or_conn

    async def find_conversation(self, channel: str, channel_account_id: str, external_user_id: str) -> Conversation | None:
        row = await self._fetchrow(
            """
            SELECT * FROM conversations
            WHERE channel = $1 AND channel_account_id = $2 AND external_user_id = $3
            """,
            channel,
            channel_account_id,
            external_user_id,
        )
        return _conversation(row) if row else None

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        row = await self._fetchrow("SELECT * FROM conversations WHERE id = $1", conversation_id)
        return _conversation(row) if row else None

    async def list_conversations(
        self,
        *,
        status: str | None = None,
        channel: str | None = None,
        assigned_agent_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        clauses: list[str] = []
        values: list[Any] = []
        if status:
            values.append(status)
            clauses.append(f"status = ${len(values)}")
        if channel:
            values.append(channel)
            clauses.append(f"channel = ${len(values)}")
        if assigned_agent_id:
            values.append(assigned_agent_id)
            clauses.append(f"assigned_agent_id = ${len(values)}")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.extend([limit, offset])
        rows = await self._fetch(
            f"""
            SELECT * FROM conversations
            {where}
            ORDER BY last_message_at DESC NULLS LAST, updated_at DESC
            LIMIT ${len(values)-1} OFFSET ${len(values)}
            """,
            *values,
        )
        return [_conversation(row) for row in rows]

    async def create_conversation(
        self,
        *,
        channel: str,
        channel_account_id: str,
        external_user_id: str,
        external_conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        row = await self._fetchrow(
            """
            INSERT INTO conversations (
              id, channel, channel_account_id, external_user_id, external_conversation_id,
              status, current_owner, metadata
            )
            VALUES ($1, $2, $3, $4, $5, 'BOT_ACTIVE', 'BOT', $6::jsonb)
            ON CONFLICT (channel, channel_account_id, external_user_id)
            DO UPDATE SET updated_at = now()
            RETURNING *
            """,
            _id("conv"),
            channel,
            channel_account_id,
            external_user_id,
            external_conversation_id,
            _json(metadata),
        )
        return _conversation(row)

    async def update_conversation(self, conversation_id: str, **fields: Any) -> Conversation:
        assignments = []
        values: list[Any] = []
        for key, value in fields.items():
            values.append(_value(value))
            cast = "::jsonb" if key in {"metadata"} else ""
            assignments.append(f"{key} = ${len(values)}{cast}")
        values.append(conversation_id)
        row = await self._fetchrow(
            f"""
            UPDATE conversations
            SET {', '.join(assignments)}, updated_at = now()
            WHERE id = ${len(values)}
            RETURNING *
            """,
            *values,
        )
        return _conversation(row)

    async def find_message_by_external_id(self, channel: str, external_message_id: str) -> Message | None:
        row = await self._fetchrow(
            "SELECT * FROM messages WHERE channel = $1 AND external_message_id = $2",
            channel,
            external_message_id,
        )
        return _message(row) if row else None

    async def create_message(self, **fields: Any) -> Message:
        data = {
            "id": fields.get("id") or _id("msg"),
            "conversation_id": fields["conversation_id"],
            "channel": fields["channel"],
            "external_message_id": fields.get("external_message_id"),
            "direction": fields["direction"],
            "sender_type": fields["sender_type"],
            "sender_id": fields.get("sender_id"),
            "content_type": fields.get("content_type") or "text",
            "content": fields.get("content"),
            "payload": _json(fields.get("payload")),
            "intent": fields.get("intent"),
            "confidence": fields.get("confidence"),
            "status": fields["status"],
            "error_message": fields.get("error_message"),
            "correlation_id": fields.get("correlation_id"),
            "metadata": _json(fields.get("metadata")),
        }
        row = await self._fetchrow(
            """
            INSERT INTO messages (
              id, conversation_id, channel, external_message_id, direction, sender_type,
              sender_id, content_type, content, payload, intent, confidence, status,
              error_message, correlation_id, metadata
            )
            VALUES (
              $1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12, $13, $14, $15, $16::jsonb
            )
            ON CONFLICT (channel, external_message_id) WHERE external_message_id IS NOT NULL
            DO UPDATE SET status = messages.status
            RETURNING *
            """,
            *data.values(),
        )
        return _message(row)

    async def update_message(self, message_id: str, **fields: Any) -> Message:
        assignments = []
        values: list[Any] = []
        for key, value in fields.items():
            values.append(_value(value))
            cast = "::jsonb" if key in {"payload", "metadata"} else ""
            assignments.append(f"{key} = ${len(values)}{cast}")
        values.append(message_id)
        row = await self._fetchrow(
            f"""
            UPDATE messages
            SET {', '.join(assignments)}
            WHERE id = ${len(values)}
            RETURNING *
            """,
            *values,
        )
        return _message(row)

    async def list_messages(self, conversation_id: str, *, limit: int = 100, offset: int = 0) -> list[Message]:
        rows = await self._fetch(
            """
            SELECT * FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            LIMIT $2 OFFSET $3
            """,
            conversation_id,
            limit,
            offset,
        )
        return [_message(row) for row in rows]

    async def create_event(self, **fields: Any) -> ConversationEvent:
        row = await self._fetchrow(
            """
            INSERT INTO conversation_events (
              id, conversation_id, event_type, actor_type, actor_id, from_status,
              to_status, reason, payload
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
            RETURNING *
            """,
            fields.get("id") or _id("evt"),
            fields["conversation_id"],
            fields["event_type"],
            fields["actor_type"],
            fields.get("actor_id"),
            fields.get("from_status"),
            fields.get("to_status"),
            fields.get("reason"),
            _json(fields.get("payload")),
        )
        return _event(row)

    async def list_events(self, conversation_id: str, *, limit: int = 100, offset: int = 0) -> list[ConversationEvent]:
        rows = await self._fetch(
            """
            SELECT * FROM conversation_events
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            LIMIT $2 OFFSET $3
            """,
            conversation_id,
            limit,
            offset,
        )
        return [_event(row) for row in rows]

    async def get_active_assignment(self, conversation_id: str) -> ConversationAssignment | None:
        row = await self._fetchrow(
            """
            SELECT * FROM conversation_assignments
            WHERE conversation_id = $1 AND status = 'ACTIVE'
            ORDER BY assigned_at DESC
            LIMIT 1
            """,
            conversation_id,
        )
        return _assignment(row) if row else None

    async def create_assignment(self, **fields: Any) -> ConversationAssignment:
        row = await self._fetchrow(
            """
            INSERT INTO conversation_assignments (
              id, conversation_id, agent_id, assigned_by, status, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING *
            """,
            fields.get("id") or _id("asgn"),
            fields["conversation_id"],
            fields["agent_id"],
            fields.get("assigned_by"),
            fields.get("status") or AssignmentStatus.ACTIVE.value,
            _json(fields.get("metadata")),
        )
        return _assignment(row)

    async def release_active_assignments(self, conversation_id: str) -> None:
        await self._execute(
            """
            UPDATE conversation_assignments
            SET status = 'RELEASED', released_at = now()
            WHERE conversation_id = $1 AND status = 'ACTIVE'
            """,
            conversation_id,
        )

    async def lock_conversation(self, conversation_id: str) -> None:
        await self._fetchrow("SELECT id FROM conversations WHERE id = $1 FOR UPDATE", conversation_id)

    async def _fetchrow(self, query: str, *args: Any) -> asyncpg.Record:
        if isinstance(self.db, asyncpg.Pool):
            async with self.db.acquire() as conn:
                return await conn.fetchrow(query, *args)
        return await self.db.fetchrow(query, *args)

    async def _fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        if isinstance(self.db, asyncpg.Pool):
            async with self.db.acquire() as conn:
                return await conn.fetch(query, *args)
        return await self.db.fetch(query, *args)

    async def _execute(self, query: str, *args: Any) -> str:
        if isinstance(self.db, asyncpg.Pool):
            async with self.db.acquire() as conn:
                return await conn.execute(query, *args)
        return await self.db.execute(query, *args)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _value(value: Any) -> Any:
    if isinstance(value, dict):
        return _json(value)
    if hasattr(value, "value"):
        return value.value
    return value


def _record(row: asyncpg.Record) -> dict[str, Any]:
    data = dict(row)
    for key, value in list(data.items()):
        if key.endswith("_at") and value is not None:
            data[key] = value.isoformat()
        if key in {"metadata", "payload"} and isinstance(value, str):
            data[key] = json.loads(value)
    return data


def _conversation(row: asyncpg.Record) -> Conversation:
    return Conversation.model_validate(_record(row))


def _message(row: asyncpg.Record) -> Message:
    return Message.model_validate(_record(row))


def _assignment(row: asyncpg.Record) -> ConversationAssignment:
    return ConversationAssignment.model_validate(_record(row))


def _event(row: asyncpg.Record) -> ConversationEvent:
    return ConversationEvent.model_validate(_record(row))
