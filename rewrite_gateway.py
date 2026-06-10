import re

with open("chatbot-service/app/api/chat_gateway.py", "r") as f:
    content = f.read()

# 1. Add missing imports
imports_to_add = """
from app.clients.gemini_client import GeminiClient, get_gemini_client
from app.services.ai_usage_service import record_gemini_usage
from app.services.intent_nlu import infer_intent_from_text
"""
content = content.replace("from app.services.escalation import should_escalate_to_admin", imports_to_add.strip() + "\nfrom app.services.escalation import should_escalate_to_admin")

# 2. Add SMALLTALK constants and _is_fallback_response
helpers = """
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
    intent_name = (session_state.get("intent") or {}).get("name") or ""
    if "fallback" in intent_name.lower(): return True
    messages = response.get("messages") or []
    for msg in messages:
        if (msg.get("content") or "").strip() in _LEX_FALLBACK_TEXTS: return True
    return False

def _canonical_messages_for_intent(intent_name: str | None, messages: list) -> list:
    normalized_intent = str(intent_name or "").lower()
    if normalized_intent == "smalltalk_compliment": return [{"text": SMALLTALK_COMPLIMENT_MESSAGE, "payload": None}]
    if normalized_intent == "smalltalk_affirmation": return [{"text": SMALLTALK_AFFIRMATION_MESSAGE, "payload": None}]
    if normalized_intent == "smalltalk_negation": return [{"text": SMALLTALK_NEGATION_MESSAGE, "payload": None}]
    return messages
"""
content = content.replace("HANDOVER_MESSAGE = (\n", helpers + "\nHANDOVER_MESSAGE = (\n")

# 3. Update process_ai_request signature
content = content.replace(
    "    lex_client: LexRuntimeClient,\n) -> dict[str, Any]:",
    "    lex_client: LexRuntimeClient,\n    gemini_client: GeminiClient | None = None,\n) -> dict[str, Any]:"
)

# 4. Insert Gemini logic after the first Lex call
lex_call = """
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
"""

gemini_logic = """
    local_intent = infer_intent_from_text(text)
    is_fallback = _is_fallback_response(response)
    has_gemini = gemini_client is not None and gemini_client.is_enabled()
    
    if is_fallback and has_gemini and local_intent not in _SMALLTALK_INTENTS:
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
            
            # --- LOCAL FALLBACK EXECUTION FIX ---
            if _is_fallback_response(response) and local_intent and local_intent not in {"fallback", "FallbackIntent"}:
                from app.clients.medusa_client import get_medusa_client
                from app.services.intent_service import IntentService
                from app.schemas.lexv2 import LexV2Request
                intent_service = IntentService(get_medusa_client(), gemini_client)
                mock_request = LexV2Request(
                    sessionId=session_id,
                    inputTranscript=normalized_text or text,
                    requestAttributes=response.get("requestAttributes") or {},
                    sessionState={
                        "intent": {"name": "FallbackIntent", "state": "Fulfilled"},
                        "sessionAttributes": lex_session_attributes,
                    },
                )
                dialogflow_response = await intent_service.handle(mock_request, authorization_header=authorization)
                response = dialogflow_response.model_dump(by_alias=True)
                
        except Exception as e:
            print(f"[GATEWAY] Gemini rewrite error: {e}", flush=True)

    if _is_fallback_response(response) and local_intent in _SMALLTALK_INTENTS:
        response["sessionState"] = response.get("sessionState") or {}
        response["sessionState"]["intent"] = {"name": local_intent}
"""
content = content.replace(lex_call, lex_call + gemini_logic)

# 5. Fix normalize_lex_messages usage
content = content.replace("    normalized_messages = normalize_lex_messages(response.get(\"messages\") or [])", 
                          "    normalized_messages = normalize_lex_messages(response.get(\"messages\") or [])\n    normalized_messages = _canonical_messages_for_intent(intent_name, normalized_messages)")

# 6. Fix endpoint injection
content = content.replace("    lex_client: LexRuntimeClient = Depends(get_lex_runtime_client),\n) -> dict[str, Any]:\n    return await process_ai_request(body, authorization, lex_client)",
                          "    lex_client: LexRuntimeClient = Depends(get_lex_runtime_client),\n    gemini_client: GeminiClient = Depends(get_gemini_client),\n) -> dict[str, Any]:\n    return await process_ai_request(body, authorization, lex_client, gemini_client)")

with open("chatbot-service/app/api/chat_gateway.py", "w") as f:
    f.write(content)
