from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from app.clients.lex_runtime import LexRuntimeClient, get_lex_runtime_client, normalize_lex_messages
from app.services.ai_usage_service import record_lex_usage
from app.clients.gemini_client import GeminiClient, get_gemini_client
from app.services.ai_usage_service import record_gemini_usage
from app.services.intent_nlu import infer_intent_from_text
from app.services.escalation import should_escalate_to_admin
from app.services.moderation import ABUSIVE_LANGUAGE_MESSAGE, moderate_customer_message

router = APIRouter()


SMALLTALK_COMPLIMENT_MESSAGE = (
    "Cảm ơn bạn nha. Mình là trợ lý ảo của shop, mình có thể hỗ trợ bạn xem sản phẩm, "
    "giá, ưu đãi hoặc đơn hàng nhé!"
)
SMALLTALK_AFFIRMATION_MESSAGE = "Dạ vâng, mình ở đây. Bạn cần hỗ trợ thông tin gì về sản phẩm, giá cả hay ưu đãi không ạ?"
SMALLTALK_NEGATION_MESSAGE = "Dạ vâng. Vậy nếu bạn cần tìm hiểu sản phẩm hay có thắc mắc nào khác thì cứ nhắn cho mình nhé!"

_LEX_FALLBACK_TEXTS = {
    "Mình chưa nhận được phản hồi phù hợp. Bạn thử hỏi lại giúp mình nhé.",
}
_SMALLTALK_INTENTS = {"smalltalk_affirmation", "smalltalk_negation", "smalltalk_compliment"}

def _is_fallback_response(response: dict) -> bool:
    session_state = response.get("sessionState") or {}
    intent = session_state.get("intent") or {}
    intent_name = intent.get("name") or ""
    if "fallback" in intent_name.lower(): return True
    if intent.get("state") == "Failed": return True
    
    messages = response.get("messages") or []
    for msg in messages:
        if (msg.get("content") or "").strip() in _LEX_FALLBACK_TEXTS: return True
    return False

def _canonical_messages_for_intent(intent_name: str | None, messages: list) -> list:
    normalized_intent = str(intent_name or "").lower()
    if normalized_intent == "smalltalk_compliment": return [{"text": SMALLTALK_COMPLIMENT_MESSAGE, "payload": None}]
    if normalized_intent == "smalltalk_affirmation": return [{"text": SMALLTALK_AFFIRMATION_MESSAGE, "payload": None}]
    if normalized_intent == "smalltalk_negation": return [{"text": SMALLTALK_NEGATION_MESSAGE, "payload": None}]
    if normalized_intent in {"fallback", "fallbackintent"}:
        return [{"text": "Mình chưa hiểu rõ yêu cầu của bạn. Bạn có thể hỏi về sản phẩm, giá, ưu đãi, giao hàng hoặc đơn hàng để mình hỗ trợ nhé.", "payload": None}]
    return messages

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
    gemini_client: GeminiClient | None = None,
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

    if moderation.blocked:
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

    local_intent = infer_intent_from_text(text)

    session_id = (
        f"fb_{external_user_id}"
        if channel == "MESSENGER" and external_user_id
        else body.conversation_id
    )

    if local_intent in _SMALLTALK_INTENTS:
        response = {
            "sessionState": {
                "intent": {"name": local_intent},
                "sessionAttributes": {
                    "resolved_intent": local_intent,
                    "ai_confidence": "1.0",
                },
            },
            "messages": [],
        }
    else:
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

    is_fallback = _is_fallback_response(response)
    has_gemini = gemini_client is not None and gemini_client.is_enabled()
    has_local_specific_intent = local_intent and local_intent not in {"fallback", "FallbackIntent"}
    
    if is_fallback and has_gemini and not has_local_specific_intent and local_intent not in _SMALLTALK_INTENTS:
        normalized_text = None
        try:
            lex_session_attributes = response.get("sessionState", {}).get("sessionAttributes", {})
            result = await gemini_client.normalize_user_query_with_usage(
                user_text=text,
                session_parameters=lex_session_attributes,
            )
            normalized_text = result.text.strip()
            if normalized_text and normalized_text.lower() != text.lower():
                response = await lex_client.recognize_text(
                    session_id=session_id,
                    text=normalized_text,
                    request_attributes=response.get("requestAttributes") or {},
                )
                is_fallback = _is_fallback_response(response)
        except Exception as e:
            print(f"[GATEWAY] Gemini query rewrite error: {e}", flush=True)

    # --- LOCAL FALLBACK EXECUTION FIX ---
    # Running outside the Gemini block so that local intents run even if Gemini is disabled or rate-limited.
    if is_fallback and has_local_specific_intent:
        try:
            from app.clients.medusa_client import get_medusa_client
            from app.services.intent_service import IntentService
            from app.schemas.lexv2 import LexV2Request
            lex_session_attributes = response.get("sessionState", {}).get("sessionAttributes", {})
            intent_service = IntentService(get_medusa_client(), gemini_client)
            mock_request = LexV2Request(
                sessionId=session_id,
                inputTranscript=text,
                requestAttributes=response.get("requestAttributes") or {},
                sessionState={
                    "intent": {"name": "FallbackIntent", "state": "Failed"},
                    "sessionAttributes": lex_session_attributes,
                },
            )
            dialogflow_response = await intent_service.handle(mock_request, authorization_header=authorization)
            response = dialogflow_response.model_dump(by_alias=True)
            is_fallback = _is_fallback_response(response)
        except Exception as e:
            print(f"[GATEWAY] Local fallback execution error: {e}", flush=True)

    if is_fallback and local_intent in _SMALLTALK_INTENTS:
        response["sessionState"] = response.get("sessionState") or {}
        response["sessionState"]["intent"] = {"name": local_intent}
        if "sessionAttributes" not in response["sessionState"]:
            response["sessionState"]["sessionAttributes"] = {}
        response["sessionState"]["sessionAttributes"]["resolved_intent"] = local_intent
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
    normalized_messages = _canonical_messages_for_intent(intent_name, normalized_messages)
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
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> dict[str, Any]:
    return await process_ai_request(body, authorization, lex_client, gemini_client)


@router.post("/chat/process")
async def process_chat_compat(
    body: AIProcessRequest,
    authorization: str | None = Header(default=None),
    lex_client: LexRuntimeClient = Depends(get_lex_runtime_client),
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> dict[str, Any]:
    return await process_ai_request(body, authorization, lex_client, gemini_client)
