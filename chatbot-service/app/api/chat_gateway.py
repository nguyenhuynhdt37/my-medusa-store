from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from app.clients.lex_runtime import LexRuntimeClient, get_lex_runtime_client, normalize_lex_messages
from app.services.ai_usage_service import record_lex_usage
from app.services.escalation import should_escalate_to_admin

router = APIRouter()


class AIProcessRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    message: str
    customer_context: dict[str, Any] = Field(default_factory=dict)
    session_context: dict[str, Any] = Field(default_factory=dict)


async def process_ai_request(
    body: AIProcessRequest,
    authorization: str | None,
    lex_client: LexRuntimeClient,
) -> dict[str, Any]:
    text = body.message.strip()
    channel = str(body.customer_context.get("channel") or "WEB").upper()
    external_user_id = body.customer_context.get("external_user_id")
    pre_escalation = should_escalate_to_admin(message=text)

    print(
        "[AI_SERVICE_REQUEST]",
        {
            "conversation_id": body.conversation_id,
            "channel": channel,
            "content_length": len(text),
        },
        flush=True,
    )

    if pre_escalation.escalate:
        return {
            "reply": None,
            "messages": [],
            "intent": "HumanHandover",
            "confidence": pre_escalation.confidence,
            "escalation": pre_escalation.__dict__,
            "metadata": {
                "ai": {
                    "intent": "HumanHandover",
                    "confidence": pre_escalation.confidence,
                    "escalation": pre_escalation.__dict__,
                }
            },
        }

    session_id = (
        f"fb_{external_user_id}"
        if channel == "MESSENGER" and external_user_id
        else body.conversation_id
    )
    response = await lex_client.recognize_text(
        session_id=session_id,
        text=text,
        request_attributes={
            **({"Authorization": authorization} if authorization else {}),
            "conversation_id": body.conversation_id,
            "customer_id": str(body.customer_context.get("customer_id") or ""),
            "guest_id": str(body.customer_context.get("guest_id") or ""),
            "external_user_id": str(external_user_id or ""),
            "channel": channel,
            "session_id": session_id,
        },
    )
    session_state = response.get("sessionState") or {}
    session_attributes = session_state.get("sessionAttributes") or {}
    intent_name = (
        session_attributes.get("resolved_intent")
        or (session_state.get("intent") or {}).get("name")
        or "FallbackIntent"
    )
    confidence = session_attributes.get("ai_confidence")
    try:
        confidence = (
            float(confidence)
            if confidence is not None
            else (response.get("interpretations") or [{}])[0].get("nluConfidence", {}).get("score")
        )
    except (TypeError, ValueError):
        confidence = None

    await record_lex_usage(
        conversation_id=body.conversation_id,
        customer_id=str(body.customer_context.get("customer_id") or "") or None,
        guest_id=str(body.customer_context.get("guest_id") or "") or None,
        external_user_id=str(external_user_id or "") or None,
        channel=channel,
        intent=str(intent_name) if intent_name else None,
        session_id=session_id,
        request_count=1,
    )

    failed_response_count = 1 if "fallback" in str(intent_name).lower() else 0
    escalation = should_escalate_to_admin(
        message=text,
        intent=intent_name,
        confidence=confidence,
        failed_response_count=failed_response_count,
    )

    normalized_messages = normalize_lex_messages(response.get("messages") or [])
    messages: list[dict[str, Any]] = []
    for bot_message in normalized_messages:
        payload = None
        if bot_message.get("payload"):
            try:
                payload = json.loads(bot_message["payload"])
            except Exception:
                payload = bot_message["payload"]

        messages.append({
            "text": bot_message.get("text") or "",
            "payload": payload,
        })

    reply = "\n".join(message["text"] for message in messages if message.get("text")).strip() or None
    metadata = {
        "ai": {
            "intent": intent_name,
            "confidence": confidence,
            "escalation": escalation.__dict__,
        },
        "session": {
            "attributes": session_attributes,
        },
    }

    print(
        "[INTENT]",
        {
            "conversation_id": body.conversation_id,
            "intent_name": intent_name,
            "confidence": confidence,
            "escalate": escalation.escalate,
        },
        flush=True,
    )

    return {
        "reply": reply,
        "messages": messages,
        "intent": intent_name,
        "confidence": confidence,
        "escalation": escalation.__dict__,
        "metadata": metadata,
    }


@router.post("/ai/process")
async def process_ai(
    body: AIProcessRequest,
    authorization: str | None = Header(default=None),
    lex_client: LexRuntimeClient = Depends(get_lex_runtime_client),
) -> dict[str, Any]:
    return await process_ai_request(body, authorization, lex_client)


@router.post("/chat/process")
async def process_chat_compat(
    body: AIProcessRequest,
    authorization: str | None = Header(default=None),
    lex_client: LexRuntimeClient = Depends(get_lex_runtime_client),
) -> dict[str, Any]:
    return await process_ai_request(body, authorization, lex_client)
