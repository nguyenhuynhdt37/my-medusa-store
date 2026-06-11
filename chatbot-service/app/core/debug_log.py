from __future__ import annotations

import json
from typing import Any

from app.core.config import settings


SENSITIVE_KEY_PARTS = (
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "secret",
    "password",
    "x-goog-api-key",
)


def trace(event: str, payload: dict[str, Any] | None = None) -> None:
    if not settings.chatbot_trace_enabled:
        return

    record = {
        "event": event,
        "payload": _redact(payload or {}),
    }
    print(f"[CHATBOT_TRACE] {json.dumps(record, ensure_ascii=False, default=str)}", flush=True)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in SENSITIVE_KEY_PARTS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    if isinstance(value, str) and len(value) > settings.chatbot_trace_max_string_chars:
        limit = settings.chatbot_trace_max_string_chars
        return f"{value[:limit]}... [truncated {len(value) - limit} chars]"
    return value
