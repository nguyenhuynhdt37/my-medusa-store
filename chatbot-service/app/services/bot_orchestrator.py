from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.domain import BotReplyResult, Conversation
from app.services.escalation import is_explicit_handoff_request
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
        fallback = self.should_handover(result, message=message)
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

    def should_handover(self, bot_result: dict[str, Any], message: str | None = None) -> bool:
        if not settings.enable_human_handover:
            return False

        escalation = bot_result.get("escalation") or {}
        if escalation.get("escalate"):
            return True

        intent = str(bot_result.get("intent") or "").lower()
        if ("human" in intent or "handover" in intent) and is_explicit_handoff_request(message):
            return True

        return False
