from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.adapters.registry import get_channel_adapter
from app.core.database import get_pool
from app.repositories import PostgresConversationRepository
from app.services.agent_service import AgentService

router = APIRouter(prefix="/admin/conversations", tags=["admin-conversations"])


class AgentMessageRequest(BaseModel):
    text: str = Field(min_length=1)


def agent_id(value: str | None) -> str:
    return value or "dev-agent"


async def repo() -> PostgresConversationRepository:
    return PostgresConversationRepository(await get_pool())


async def agent_service_for_conversation(conversation_id: str) -> AgentService:
    repository = await repo()
    conversation = await repository.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    try:
        adapter = get_channel_adapter(conversation.channel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentService(repository, adapter)


@router.get("")
async def list_conversations(
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    assigned_agent_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
):
    repository = await repo()
    items = await repository.list_conversations(
        status=status,
        channel=channel,
        assigned_agent_id=assigned_agent_id,
        limit=limit,
        offset=(page - 1) * limit,
    )
    return {"items": [item.model_dump() for item in items], "page": page, "limit": limit}


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    repository = await repo()
    conversation = await repository.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation.model_dump()


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
):
    repository = await repo()
    return {
        "items": [
            item.model_dump()
            for item in await repository.list_messages(
                conversation_id,
                limit=limit,
                offset=(page - 1) * limit,
            )
        ],
        "page": page,
        "limit": limit,
    }


@router.get("/{conversation_id}/events")
async def list_events(
    conversation_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
):
    repository = await repo()
    return {
        "items": [
            item.model_dump()
            for item in await repository.list_events(
                conversation_id,
                limit=limit,
                offset=(page - 1) * limit,
            )
        ],
        "page": page,
        "limit": limit,
    }


@router.post("/{conversation_id}/take")
async def take_conversation(
    conversation_id: str,
    x_agent_id: str | None = Header(default=None),
):
    service = await agent_service_for_conversation(conversation_id)
    try:
        conversation = await service.take_conversation(conversation_id, agent_id=agent_id(x_agent_id), assigned_by=agent_id(x_agent_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found.") from None
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return conversation.model_dump()


@router.post("/{conversation_id}/messages")
async def send_agent_message(
    conversation_id: str,
    body: AgentMessageRequest,
    x_agent_id: str | None = Header(default=None),
):
    service = await agent_service_for_conversation(conversation_id)
    try:
        message = await service.send_agent_message(conversation_id, agent_id=agent_id(x_agent_id), text=body.text)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found.") from None
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return message.model_dump()


@router.post("/{conversation_id}/return-to-bot")
async def return_to_bot(
    conversation_id: str,
    x_agent_id: str | None = Header(default=None),
):
    service = await agent_service_for_conversation(conversation_id)
    try:
        conversation = await service.return_to_bot(conversation_id, agent_id=agent_id(x_agent_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found.") from None
    return conversation.model_dump()


@router.post("/{conversation_id}/close")
async def close_conversation(
    conversation_id: str,
    x_agent_id: str | None = Header(default=None),
):
    service = await agent_service_for_conversation(conversation_id)
    try:
        conversation = await service.close_conversation(conversation_id, agent_id=agent_id(x_agent_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found.") from None
    return conversation.model_dump()


@router.post("/{conversation_id}/reopen")
async def reopen_conversation(
    conversation_id: str,
    x_agent_id: str | None = Header(default=None),
):
    service = await agent_service_for_conversation(conversation_id)
    try:
        conversation = await service.reopen_conversation(conversation_id, agent_id=agent_id(x_agent_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found.") from None
    return conversation.model_dump()
