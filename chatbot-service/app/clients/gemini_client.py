from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import GeminiAPIError


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

    async def _generate_text(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {
            "system_instruction": {
                "parts": [
                    {
                        "text": (
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
                "maxOutputTokens": 1200,
                "responseMimeType": "text/plain",
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
        return text


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
        "- Keep it concise; avoid long explanations.\n\n"
        f"{json.dumps(facts, ensure_ascii=False, default=str)}"
    )


def get_gemini_client() -> GeminiClient:
    return GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        enabled=settings.gemini_enabled,
    )
