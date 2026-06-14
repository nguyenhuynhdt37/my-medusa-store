from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.clients.lex_runtime import LexRuntimeClient, get_lex_runtime_client, normalize_lex_messages
from app.core.debug_log import trace
from app.services.ai_usage_service import record_lex_usage
from app.services.escalation import should_escalate_to_admin
from app.services.moderation import ABUSIVE_LANGUAGE_MESSAGE, moderate_customer_message
from app.services.query_preprocessor import prepare_text_for_lex

router = APIRouter()


def _validate_lex_response(response: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    session_state = response.get("sessionState") or {}
    intent = session_state.get("intent") or {}
    session_attributes = session_state.get("sessionAttributes") or {}
    intent_name = str(session_attributes.get("resolved_intent") or intent.get("name") or "").strip()
    resolution_source = str(session_attributes.get("resolution_source") or "lex").strip()
    raw_messages = response.get("messages") or []
    has_message = any(
        message.get("contentType") == "PlainText"
        and str(message.get("content") or "").strip()
        for message in raw_messages
    )

    if not intent_name:
        raise HTTPException(status_code=502, detail="Lex returned no intent.")
    if intent.get("state") == "Failed":
        raise HTTPException(status_code=502, detail=f"Lex fulfillment failed for intent {intent_name}.")
    if resolution_source not in {"lex", "local_nlu", "gemini"}:
        raise HTTPException(status_code=502, detail=f"Lex returned invalid resolution source {resolution_source}.")
    if not has_message:
        raise HTTPException(status_code=502, detail=f"Lex returned no message for intent {intent_name}.")

    return intent_name, session_attributes


HANDOVER_MESSAGE = (
    "Mình đang chuyển bạn đến nhân viên hỗ trợ. "
    "Bạn chờ trong giây lát, nhân viên sẽ tiếp nhận cuộc trò chuyện này ngay khi có thể."
)


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
    moderation = moderate_customer_message(text)
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
    trace(
        "CHAT_GATEWAY_REQUEST",
        {
            "conversation_id": body.conversation_id,
            "message": text,
            "channel": channel,
            "customer_context": body.customer_context,
            "session_context": body.session_context,
            "has_authorization": bool(authorization),
        },
    )

    if moderation.blocked:
        trace(
            "CHAT_GATEWAY_MODERATION_BLOCKED",
            {
                "conversation_id": body.conversation_id,
                "message": text,
                "reason": moderation.reason,
            },
        )
        return {
            "reply": ABUSIVE_LANGUAGE_MESSAGE,
            "messages": [{"text": ABUSIVE_LANGUAGE_MESSAGE}],
            "intent": "BlockedAbusiveLanguage",
            "confidence": 1.0,
            "escalation": {
                "escalate": False,
                "reason": moderation.reason,
                "confidence": 1.0,
            },
            "metadata": {
                "ai": {
                    "intent": "BlockedAbusiveLanguage",
                    "moderation": {
                        "blocked": True,
                        "reason": moderation.reason,
                    },
                }
            },
        }

    if pre_escalation.escalate:
        trace(
            "CHAT_GATEWAY_PRE_ESCALATION",
            {
                "conversation_id": body.conversation_id,
                "message": text,
                "escalation": pre_escalation.__dict__,
            },
        )
        return {
            "reply": HANDOVER_MESSAGE,
            "messages": [{"text": HANDOVER_MESSAGE}],
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
    lex_text = prepare_text_for_lex(text)

    try:
        response = await lex_client.recognize_text(
            session_id=session_id,
            text=lex_text,
            request_attributes={
                **({"Authorization": authorization} if authorization else {}),
                "conversation_id": body.conversation_id,
                "customer_id": str(body.customer_context.get("customer_id") or ""),
                "guest_id": str(body.customer_context.get("guest_id") or ""),
                "external_user_id": str(external_user_id or ""),
                "channel": channel,
                "session_id": session_id,
                "original_text": text,
            },
        )
    except Exception as exc:
        trace(
            "CHAT_GATEWAY_LEX_ERROR",
            {
                "conversation_id": body.conversation_id,
                "session_id": session_id,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=502, detail=f"Lex request failed: {exc}") from exc

    trace(
        "CHAT_GATEWAY_LEX_RESPONSE",
        {
            "conversation_id": body.conversation_id,
            "session_id": session_id,
            "response": response,
        },
    )

    intent_name, session_attributes = _validate_lex_response(response)
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

    escalation = should_escalate_to_admin(
        message=text,
        intent=intent_name,
        confidence=confidence,
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

    result = {
        "reply": reply,
        "messages": messages,
        "intent": intent_name,
        "confidence": confidence,
        "escalation": escalation.__dict__,
        "metadata": metadata,
    }
    trace(
        "CHAT_GATEWAY_RESPONSE",
        {
            "conversation_id": body.conversation_id,
            "response": result,
        },
    )
    return result


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
