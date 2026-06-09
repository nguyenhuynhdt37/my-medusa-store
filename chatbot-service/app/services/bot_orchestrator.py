from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.domain import BotReplyResult, Conversation
from app.services.lambda_service import call_bot


class BotOrchestrator:
    async def process_customer_message(
        self,
        *,
        conversation: Conversation,
        message: str,
    ) -> BotReplyResult:
        result = await call_bot(
            user_id=conversation.external_user_id,
            message=message,
            page_id=conversation.channel_account_id,
        )
        fallback = self.should_handover(result)
        return BotReplyResult(
            reply=result.get("reply"),
            messages=result.get("messages") or [],
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            fallback=fallback,
            handover=fallback,
            escalation=result.get("escalation"),
            metadata=result.get("metadata"),
        )

    def should_handover(self, bot_result: dict[str, Any]) -> bool:
        if not settings.enable_human_handover:
            return False

        escalation = bot_result.get("escalation") or {}
        if escalation.get("escalate"):
            return True

        intent = str(bot_result.get("intent") or "").lower()
        if "fallback" in intent or "unknown" in intent or "handover" in intent or "human" in intent:
            return True

        confidence = bot_result.get("confidence")
        try:
            return confidence is not None and float(confidence) < settings.human_handover_confidence_threshold
        except (TypeError, ValueError):
            return False
