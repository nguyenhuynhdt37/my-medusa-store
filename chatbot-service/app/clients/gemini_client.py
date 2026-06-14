from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.core.debug_log import trace
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
        rate_limit_cooldown_seconds: float = 60.0,
        enabled: bool = True,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = httpx.Timeout(timeout_seconds)
        self.rate_limit_cooldown_seconds = rate_limit_cooldown_seconds
        self.rate_limited_until = 0.0
        self.enabled = enabled

    def is_enabled(self) -> bool:
        return bool(self.enabled and self.api_key and time.monotonic() >= self.rate_limited_until)

    def _mark_rate_limited(self) -> None:
        self.rate_limited_until = time.monotonic() + self.rate_limit_cooldown_seconds
        trace(
            "GEMINI_RATE_LIMIT_COOLDOWN",
            {
                "model": self.model,
                "cooldown_seconds": self.rate_limit_cooldown_seconds,
                "rate_limited_until_monotonic": self.rate_limited_until,
            },
        )

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

    async def generate_product_recommendation(
        self,
        user_text: str,
        products: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.is_enabled():
            return {}

        # Prepare products context for Gemini
        products_context = []
        for p in products:
            meta = p.get("metadata") or {}
            variants = p.get("variants") or []
            prices = []
            for variant in variants:
                calc_price = variant.get("calculated_price")
                if isinstance(calc_price, dict) and calc_price.get("calculated_amount") is not None:
                    prices.append(float(calc_price["calculated_amount"]))
                elif variant.get("prices"):
                    for vp in variant["prices"]:
                        if vp.get("amount") is not None:
                            prices.append(float(vp["amount"]))
            price_str = f"{int(min(prices)):,} VNĐ" if prices else "Chưa cập nhật"
            
            p_desc = (
                f"- ID: {p.get('id')}\n"
                f"  Title: {p.get('title')}\n"
                f"  Price from: {price_str}\n"
                f"  Chip: {meta.get('chip', 'Chưa cập nhật')}\n"
                f"  Camera: {meta.get('camera', 'Chưa cập nhật')}\n"
                f"  Battery: {meta.get('battery', 'Chưa cập nhật')}\n"
                f"  Rating: {meta.get('rating', 'Chưa cập nhật')}\n"
                f"  Sold count: {meta.get('sold_count', 'Chưa cập nhật')}\n"
            )
            products_context.append(p_desc)
            
        products_text = "\n".join(products_context)
        
        prompt = (
            "You are an expert Vietnamese e-commerce shopping assistant.\n"
            "Based on the user's recommendation request, select up to 4 most relevant products from the catalog list below.\n"
            "Format the recommendation explanation in Vietnamese with clear spacing and bullet points. Mention key features matching the user's needs.\n\n"
            "### Catalog List:\n"
            f"{products_text}\n\n"
            "### User Request:\n"
            f"\"{user_text}\"\n\n"
            "Return exactly this JSON format:\n"
            "{\n"
            "  \"recommended_product_ids\": [\"prod_id1\", \"prod_id2\"],\n"
            "  \"recommendation_message\": \"Friendly explanation in Vietnamese...\"\n"
            "}"
        )
        
        data = await self._generate_text(prompt, response_mime_type="application/json", max_output_tokens=1000)
        try:
            parsed = json.loads(strip_json_code_fence(data))
        except Exception:
            parsed = {}
        return parsed

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
                trace(
                    "GEMINI_GENERATE_REQUEST",
                    {
                        "model": self.model,
                        "url": url,
                        "response_mime_type": response_mime_type,
                        "max_output_tokens": max_output_tokens,
                        "prompt": prompt,
                        "body": body,
                    },
                )
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
                trace(
                    "GEMINI_GENERATE_RESPONSE",
                    {
                        "model": self.model,
                        "status_code": response.status_code,
                        "usage_metadata": data.get("usageMetadata"),
                        "response": data,
                    },
                )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 429:
                self._mark_rate_limited()
            body = exc.response.text[:500]
            trace(
                "GEMINI_GENERATE_HTTP_ERROR",
                {
                    "model": self.model,
                    "status_code": status_code,
                    "response_body": exc.response.text,
                    "prompt": prompt,
                },
            )
            raise GeminiAPIError(
                f"Gemini API request failed with status {status_code} for model {self.model}: {body}"
            ) from exc
        except httpx.HTTPError as exc:
            trace(
                "GEMINI_GENERATE_TRANSPORT_ERROR",
                {
                    "model": self.model,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                    "prompt": prompt,
                },
            )
            raise GeminiAPIError(f"Gemini API request failed: {exc}") from exc

        candidates = data.get("candidates") or []
        if not candidates:
            raise GeminiAPIError("Gemini API returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", []) or []
        text = "".join(str(part.get("text", "")) for part in parts)
        if not text:
            raise GeminiAPIError("Gemini API returned an empty response")
        return GeminiTextResult(text=text, usage_metadata=data.get("usageMetadata"))

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
        rate_limit_cooldown_seconds=settings.gemini_rate_limit_cooldown_seconds,
        enabled=settings.gemini_enabled,
    )
