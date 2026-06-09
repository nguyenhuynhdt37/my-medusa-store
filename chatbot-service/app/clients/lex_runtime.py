from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import settings


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

        def call() -> dict[str, Any]:
            return self.client.recognize_text(
                botId=settings.lex_bot_id,
                botAliasId=settings.lex_bot_alias_id,
                localeId=settings.lex_locale_id,
                sessionId=session_id,
                text=text,
                requestAttributes=request_attributes or {},
            )

        return await asyncio.to_thread(call)


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
