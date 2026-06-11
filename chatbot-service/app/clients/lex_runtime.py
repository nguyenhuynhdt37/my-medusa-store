from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import settings
from app.core.debug_log import trace

_session_locks: dict[str, asyncio.Lock] = {}


class LexRuntimeClient:
    def __init__(self) -> None:
        import boto3

        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        self.client = boto3.client("lexv2-runtime", **kwargs)

    async def recognize_text(
        self,
        *,
        session_id: str,
        text: str,
        request_attributes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not settings.lex_bot_id or not settings.lex_bot_alias_id:
            raise RuntimeError("AWS Lex is not configured on FastAPI Chat Service.")

        trace(
            "LEX_RECOGNIZE_REQUEST",
            {
                "session_id": session_id,
                "text": text,
                "request_attributes": request_attributes or {},
                "bot_id": settings.lex_bot_id,
                "bot_alias_id": settings.lex_bot_alias_id,
                "locale_id": settings.lex_locale_id,
            },
        )
        lock = _session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return await self._recognize_text_with_retry(
                session_id=session_id,
                text=text,
                request_attributes=request_attributes,
            )

    async def _recognize_text_with_retry(
        self,
        *,
        session_id: str,
        text: str,
        request_attributes: dict[str, str] | None,
    ) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            return self.client.recognize_text(
                botId=settings.lex_bot_id,
                botAliasId=settings.lex_bot_alias_id,
                localeId=settings.lex_locale_id,
                sessionId=session_id,
                text=text,
                requestAttributes=request_attributes or {},
            )

        for attempt in range(3):
            try:
                response = await asyncio.to_thread(call)
                trace(
                    "LEX_RECOGNIZE_RESPONSE",
                    {
                        "session_id": session_id,
                        "attempt": attempt + 1,
                        "response": response,
                    },
                )
                return response
            except Exception as exc:
                trace(
                    "LEX_RECOGNIZE_ERROR",
                    {
                        "session_id": session_id,
                        "attempt": attempt + 1,
                        "error_type": exc.__class__.__name__,
                        "error": str(exc),
                        "will_retry": _is_lex_conflict(exc) and attempt < 2,
                    },
                )
                if not _is_lex_conflict(exc) or attempt == 2:
                    raise
                await asyncio.sleep(0.15 * (attempt + 1))

        raise RuntimeError("Lex recognize_text retry loop exited unexpectedly.")


def _is_lex_conflict(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = ((response.get("Error") or {}).get("Code") or "").lower()
        if code == "conflictexception":
            return True
    return exc.__class__.__name__ == "ConflictException"


def normalize_lex_messages(messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    pending_text = ""

    for message in messages or []:
        if message.get("contentType") == "PlainText":
            content = message.get("content") or ""
            pending_text = f"{pending_text}\n{content}" if pending_text else content
        elif message.get("contentType") == "CustomPayload":
            normalized.append({"text": pending_text, "payload": message.get("content")})
            pending_text = ""

    if pending_text or not normalized:
        normalized.append({
            "text": pending_text or "Mình chưa nhận được phản hồi phù hợp. Bạn thử hỏi lại giúp mình nhé."
        })

    return normalized


def get_lex_runtime_client() -> LexRuntimeClient:
    return LexRuntimeClient()
