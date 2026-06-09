from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.database import get_pool
from app.repositories.ai_usage_repository import AIUsageRepository


def lex_cost(request_count: int = 1) -> float:
    return round(request_count * settings.lex_text_request_price_usd, 8)


def gemini_cost(prompt_tokens: int | None, completion_tokens: int | None) -> float:
    input_cost = ((prompt_tokens or 0) / 1_000_000) * settings.gemini_input_price_per_1m_tokens_usd
    output_cost = ((completion_tokens or 0) / 1_000_000) * settings.gemini_output_price_per_1m_tokens_usd
    return round(input_cost + output_cost, 8)


def lambda_cost(duration_ms: float, memory_mb: int | None = None, request_count: int = 1) -> float:
    memory = memory_mb or settings.lambda_memory_size_mb
    request_cost = (request_count / 1_000_000) * settings.lambda_request_price_per_1m_usd
    gb_seconds = (duration_ms / 1000) * (memory / 1024)
    duration_cost = gb_seconds * settings.lambda_duration_price_per_gb_second_usd
    return round(request_cost + duration_cost, 8)


async def record_lex_usage(
    *,
    conversation_id: str | None,
    customer_id: str | None,
    guest_id: str | None,
    external_user_id: str | None,
    channel: str,
    intent: str | None,
    session_id: str,
    request_count: int = 1,
) -> None:
    if not _can_record():
        return
    try:
        await AIUsageRepository(await get_pool()).create_usage(
            conversation_id=_blank_to_none(conversation_id),
            customer_id=_blank_to_none(customer_id),
            guest_id=_blank_to_none(guest_id),
            external_user_id=_blank_to_none(external_user_id),
            channel=channel,
            provider="LEX",
            model="lex-v2-runtime",
            operation="recognize_text",
            intent=intent,
            request_count=request_count,
            estimated_cost_usd=lex_cost(request_count),
            unit_prices={"text_request_usd": settings.lex_text_request_price_usd},
            metadata={"session_id": session_id, "billing_unit": "text_request"},
        )
    except Exception as exc:
        print("[AI_USAGE_RECORD_FAILED]", {"provider": "LEX", "error": str(exc)}, flush=True)


async def record_gemini_usage(
    *,
    cost_context: dict[str, Any] | None,
    operation: str,
    model: str,
    intent: str | None,
    usage_metadata: dict[str, Any] | None,
) -> None:
    if not _can_record() or not usage_metadata:
        return

    prompt_tokens = _int(usage_metadata.get("promptTokenCount"))
    completion_tokens = _int(
        usage_metadata.get("candidatesTokenCount")
        or usage_metadata.get("completionTokenCount")
    )
    total_tokens = _int(usage_metadata.get("totalTokenCount"))
    context = cost_context or {}
    try:
        await AIUsageRepository(await get_pool()).create_usage(
            conversation_id=_blank_to_none(context.get("conversation_id")),
            customer_id=_blank_to_none(context.get("customer_id")),
            guest_id=_blank_to_none(context.get("guest_id")),
            external_user_id=_blank_to_none(context.get("external_user_id")),
            channel=str(context.get("channel") or "WEB").upper(),
            provider="GEMINI",
            model=model,
            operation=operation,
            intent=intent,
            request_count=1,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=gemini_cost(prompt_tokens, completion_tokens),
            unit_prices={
                "input_per_1m_tokens_usd": settings.gemini_input_price_per_1m_tokens_usd,
                "output_per_1m_tokens_usd": settings.gemini_output_price_per_1m_tokens_usd,
            },
            metadata={
                "session_id": context.get("session_id"),
                "operation": operation,
                "usage_metadata": usage_metadata,
            },
        )
    except Exception as exc:
        print("[AI_USAGE_RECORD_FAILED]", {"provider": "GEMINI", "error": str(exc)}, flush=True)


async def record_lambda_usage(
    *,
    cost_context: dict[str, Any] | None,
    operation: str,
    intent: str | None,
    duration_ms: float,
    memory_mb: int | None = None,
    request_count: int = 1,
) -> None:
    if not _can_record():
        return

    context = cost_context or {}
    memory = memory_mb or settings.lambda_memory_size_mb
    try:
        await AIUsageRepository(await get_pool()).create_usage(
            conversation_id=_blank_to_none(context.get("conversation_id")),
            customer_id=_blank_to_none(context.get("customer_id")),
            guest_id=_blank_to_none(context.get("guest_id")),
            external_user_id=_blank_to_none(context.get("external_user_id")),
            channel=str(context.get("channel") or "WEB").upper(),
            provider="LAMBDA",
            model="aws-lambda",
            operation=operation,
            intent=intent,
            request_count=request_count,
            duration_ms=round(duration_ms, 3),
            memory_mb=memory,
            estimated_cost_usd=lambda_cost(duration_ms, memory, request_count),
            unit_prices={
                "request_per_1m_usd": settings.lambda_request_price_per_1m_usd,
                "duration_per_gb_second_usd": settings.lambda_duration_price_per_gb_second_usd,
            },
            metadata={
                "session_id": context.get("session_id"),
                "operation": operation,
                "billing_unit": "request_plus_gb_second",
            },
        )
    except Exception as exc:
        print("[AI_USAGE_RECORD_FAILED]", {"provider": "LAMBDA", "error": str(exc)}, flush=True)


def cost_context_from_request_attributes(
    request_attributes: dict[str, Any] | None,
    *,
    fallback_session_id: str | None = None,
) -> dict[str, Any]:
    attrs = request_attributes or {}
    session_id = str(attrs.get("session_id") or fallback_session_id or "")
    external_user_id = attrs.get("external_user_id")
    channel = attrs.get("channel")
    if not external_user_id and session_id.startswith("fb_"):
        external_user_id = session_id[3:]
        channel = channel or "MESSENGER"
    return {
        "conversation_id": attrs.get("conversation_id"),
        "customer_id": attrs.get("customer_id"),
        "guest_id": attrs.get("guest_id"),
        "external_user_id": external_user_id,
        "channel": channel or "WEB",
        "session_id": session_id or None,
    }


def _can_record() -> bool:
    return bool(settings.ai_cost_tracking_enabled and settings.database_url)


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
