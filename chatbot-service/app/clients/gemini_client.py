from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, wait_exponential, stop_after_attempt

from app.core.config import settings
from app.core.exceptions import GeminiAPIError


@dataclass(frozen=True)
class GeminiTextResult:
    text: str
    usage_metadata: dict[str, Any] | None = None


class GeminiClient:
    def __init__(
        self,
        api_key: str | None,
        model: str = "gemini-2.5-flash",
        timeout_seconds: float = 10.0,
        enabled: bool = True,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = httpx.Timeout(timeout_seconds)
        self.enabled = enabled

    def is_enabled(self) -> bool:
        return bool(self.enabled and self.api_key)

    async def rewrite_customer_reply(
        self,
        *,
        intent: str,
        user_text: str | None,
        draft_reply: str,
        session_parameters: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        if not self.is_enabled():
            return draft_reply

        prompt = build_rewrite_prompt(
            intent=intent,
            user_text=user_text,
            draft_reply=draft_reply,
            session_parameters=session_parameters,
            payload=payload,
        )
        data = await self._generate_text(prompt)
        return data.strip() or draft_reply

    async def rewrite_customer_reply_with_usage(
        self,
        *,
        intent: str,
        user_text: str | None,
        draft_reply: str,
        session_parameters: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> GeminiTextResult:
        if not self.is_enabled():
            return GeminiTextResult(text=draft_reply)

        prompt = build_rewrite_prompt(
            intent=intent,
            user_text=user_text,
            draft_reply=draft_reply,
            session_parameters=session_parameters,
            payload=payload,
        )
        result = await self._generate_text_with_usage(prompt)
        return GeminiTextResult(text=result.text.strip() or draft_reply, usage_metadata=result.usage_metadata)

    async def resolve_customer_intent(
        self,
        *,
        lex_intent: str,
        user_text: str | None,
        session_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_enabled():
            return {}

        prompt = build_intent_resolution_prompt(
            lex_intent=lex_intent,
            user_text=user_text,
            session_parameters=session_parameters,
        )
        data = await self._generate_text(prompt, response_mime_type="application/json", max_output_tokens=400)
        try:
            parsed = json.loads(strip_json_code_fence(data))
        except json.JSONDecodeError as exc:
            raise GeminiAPIError(f"Gemini returned invalid intent JSON: {data}") from exc
        return parsed if isinstance(parsed, dict) else {}

    async def resolve_customer_intent_with_usage(
        self,
        *,
        lex_intent: str,
        user_text: str | None,
        session_parameters: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if not self.is_enabled():
            return {}, None

        prompt = build_intent_resolution_prompt(
            lex_intent=lex_intent,
            user_text=user_text,
            session_parameters=session_parameters,
        )
        result = await self._generate_text_with_usage(
            prompt,
            response_mime_type="application/json",
            max_output_tokens=400,
        )
        try:
            parsed = json.loads(strip_json_code_fence(result.text))
        except json.JSONDecodeError as exc:
            raise GeminiAPIError(f"Gemini returned invalid intent JSON: {result.text}") from exc
        return parsed if isinstance(parsed, dict) else {}, result.usage_metadata

    async def _generate_text(
        self,
        prompt: str,
        *,
        response_mime_type: str = "text/plain",
        max_output_tokens: int = 1200,
    ) -> str:
        result = await self._generate_text_with_usage(
            prompt,
            response_mime_type=response_mime_type,
            max_output_tokens=max_output_tokens,
        )
        return result.text

    @retry(
        retry=retry_if_exception(lambda exc: isinstance(exc, GeminiAPIError) and "429" in str(exc)),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _generate_text_with_usage(
        self,
        prompt: str,
        *,
        response_mime_type: str = "text/plain",
        max_output_tokens: int = 1200,
    ) -> GeminiTextResult:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        system_text = (
            "You are a Vietnamese ecommerce customer-support copywriter for a fashion storefront. "
            "Rewrite only the final customer-facing answer into polished Vietnamese. "
            "Use Markdown with clear spacing, short bullets, bold labels, and a friendly call to action when useful. "
            "Do not simply copy the draft; improve its wording, flow, and scanability. "
            "Use the provided facts exactly. Do not invent prices, discounts, URLs, order status, stock, shipping, sizes, colors, or policies. "
            "Preserve Markdown links, image Markdown, product names, order codes, numbers, currencies, and URLs exactly. "
            "For product list or recommendation responses, do not add Markdown links in the text; links are shown through the custom payload cards. "
            "Do not add greetings unless the intent is greeting or human handover. "
            "Return only the rewritten answer, without explanations."
        )
        if response_mime_type == "application/json":
            system_text = (
                "You are a strict Vietnamese ecommerce NLU classifier. "
                "Return only valid JSON. Do not write customer-facing prose."
            )

        body = {
            "system_instruction": {
                "parts": [
                    {
                        "text": system_text
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.35,
                "topP": 0.9,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": response_mime_type,
                "thinkingConfig": {
                    "thinkingBudget": 0,
                },
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": self.api_key or "",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise GeminiAPIError(f"Gemini API request failed: {exc}") from exc

        candidates = data.get("candidates") or []
        if not candidates:
            raise GeminiAPIError("Gemini API returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", []) or []
        text = "".join(str(part.get("text", "")) for part in parts)
        if not text:
            raise GeminiAPIError("Gemini API returned an empty response")
        return GeminiTextResult(text=text, usage_metadata=data.get("usageMetadata"))


    async def normalize_user_query_with_usage(
        self,
        *,
        user_text: str,
        session_parameters: dict[str, Any] | None = None,
    ) -> GeminiTextResult:
        if not self.is_enabled() or not user_text:
            return GeminiTextResult(text=user_text)

        prompt = build_query_normalization_prompt(
            user_text=user_text,
            session_parameters=session_parameters,
        )
        result = await self._generate_text_with_usage(
            prompt,
            response_mime_type="text/plain",
            max_output_tokens=200,
        )
        return result


def build_rewrite_prompt(
    *,
    intent: str,
    user_text: str | None,
    draft_reply: str,
    session_parameters: dict[str, Any] | None,
    payload: dict[str, Any] | None,
) -> str:
    facts = {
        "intent": intent,
        "user_text": user_text,
        "session_parameters": session_parameters or {},
        "payload": payload or {},
        "draft_reply": draft_reply,
    }
    return (
        "Rewrite this webhook reply in natural Vietnamese for an ecommerce customer.\n"
        "Style requirements:\n"
        "- Make the answer easy to scan in Dialogflow Messenger.\n"
        "- Product detail: add one short lead sentence, then keep product title, image Markdown, price, promotion, sizes, material, variant prices, and product link.\n"
        "- Product list or recommendation: use a compact plain Markdown bullet list with title, price, and promotion only. Do not include links in the text.\n"
        "- Promotion not found: answer naturally and suggest asking for a specific product price.\n"
        "- Order answers: keep order code, status, total, and dates exactly as provided.\n"
        "- Keep it concise; avoid long explanations.\n"
        "- CRITICAL ANTI-HALLUCINATION RULE: Do NOT invent facts, product specs, operating systems (e.g., iPhones run iOS, not Android/AI), prices, or promotions. Only describe information EXACTLY as provided in the facts payload. If a fact is missing, omit it.\n\n"
        f"{json.dumps(facts, ensure_ascii=False, default=str)}"
    )


def build_intent_resolution_prompt(
    *,
    lex_intent: str,
    user_text: str | None,
    session_parameters: dict[str, Any] | None,
) -> str:
    facts = {
        "lex_intent": lex_intent,
        "user_text": user_text,
        "session_parameters": session_parameters or {},
        "allowed_intents": [
            "greeting",
            "product_search",
            "product_price",
            "product_recommendation",
            "bonus",
            "inventory",
            "product_compare",
            "warranty_policy",
            "shipping_policy",
            "order_tracking",
            "order_list",
            "human_handover",
            "fallback",
        ],
    }
    return (
        "Resolve the Vietnamese ecommerce customer message into structured JSON only.\n"
        "Use session context to fill missing entities for short follow-up questions.\n"
        "Do not answer the customer. Do not invent product names unless they are present in session context or user text.\n"
        "Return exactly this JSON shape:\n"
        '{"intent":"one_allowed_intent","product_name":null,"product_b_name":null,"order_code":null,"confidence":0.0}\n\n'
        f"{json.dumps(facts, ensure_ascii=False, default=str)}"
    )


def build_query_normalization_prompt(
    *,
    user_text: str,
    session_parameters: dict[str, Any] | None = None,
) -> str:
    facts = {
        "user_text": user_text,
        "session_parameters": session_parameters or {},
    }
    return (
        "You are a Vietnamese text normalizer for an ecommerce chatbot NLU system.\n"
        "The user typed an informal, abbreviated, or unclear Vietnamese message.\n"
        "Your job: rewrite it into a clean, standard Vietnamese sentence that a chatbot can understand.\n\n"
        "Rules:\n"
        "1. Fix abbreviations: 'ip' → 'iPhone', 'ss' → 'Samsung', 'bn/bnh' → 'bao nhiêu', 'đt' → 'điện thoại', 'sp' → 'sản phẩm', 'k/ko/kg' → 'không'\n"
        "2. Expand slang: 'giá sao' → 'giá bao nhiêu', 'thì sao' → 'giá bao nhiêu', 'bn' → 'bao nhiêu'\n"
        "3. Keep product names and model numbers intact (e.g. 'ip 15' → 'iPhone 15', 'ip14 plus' → 'iPhone 14 Plus')\n"
        "4. If the message is a short follow-up (e.g., '17 pro thì sao', 'có màu trắng không'), use the session_parameters context to fill in the missing entity (e.g., 'iPhone 17 Pro giá bao nhiêu', 'iPhone 15 có màu trắng không').\n"
        "5. Make the sentence a clear question or statement\n"
        "6. Return ONLY the rewritten sentence, nothing else\n"
        "7. If the message is already clear, return it as-is\n"
        "8. Do NOT add any explanation or prefix\n\n"
        f"{json.dumps(facts, ensure_ascii=False, default=str)}\n"
        "Rewritten:"
    )

def build_fallback_prompt(
    *,
    user_text: str | None,
    session_parameters: dict[str, Any] | None,
) -> str:
    facts = {
        "user_text": user_text,
        "session_parameters": session_parameters or {},
    }
    return (
        "You are an intelligent Vietnamese ecommerce assistant for a phone shop. The user's query could not be resolved to a specific intent.\n"
        "Your task is to handle general shopping questions or ask one clarifying question.\n"
        "Rules:\n"
        "1. Do not invent prices, promotions, stock, order status, or shop policies. If asked about these without context, ask to clarify.\n"
        "2. CRITICAL ANTI-HALLUCINATION RULE: Do NOT hallucinate facts or product features. iPhones run iOS, not Android. Only provide generally accepted public knowledge or strictly what is in the context.\n"
        "3. If the user asks general shopping advice (e.g. 'what phone to buy for mom?'), answer generally, be helpful, and suggest they ask for specific product prices.\n"
        "4. If missing a product name or order code for a specific query, ask ONE short clarifying question.\n"
        "5. If the query is smalltalk, a compliment, or completely outside the scope of a phone shop, reply briefly and steer back to products, prices, promotions, shipping, or orders.\n"
        "6. Set action='handover' ONLY when the user explicitly asks for a human/admin/nhân viên or uses /h. Never handover just because the message is unclear, off-topic, or low confidence.\n"
        "7. If you answer, set action='answer' and put the response in 'answer'. If you clarify, set action='clarify' and put the response in 'clarifying_question'.\n"
        "Return EXACTLY this JSON shape:\n"
        '{"action":"answer|clarify|handover","answer":"...","clarifying_question":"...","confidence":0.0}\n\n'
        f"{json.dumps(facts, ensure_ascii=False, default=str)}"
    )

def strip_json_code_fence(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    return stripped.strip()


def get_gemini_client() -> GeminiClient:
    return GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        enabled=settings.gemini_enabled,
    )
