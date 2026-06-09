from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import settings
from app.schemas.facebook import FacebookMessagingEvent, FacebookWebhookPayload
from app.services.chat_constants import HANDOVER_MESSAGE, RESUME_BOT_MESSAGE


ADMIN_RESUME_COMMANDS = {"#bot", "/bot"}
CUSTOMER_RESUME_COMMANDS = {"#bot", "/bot", "bot ơi", "bot oi", "gọi bot", "goi bot"}


@dataclass(frozen=True)
class MessengerTextMessage:
    psid: str
    page_id: str | None
    message_id: str
    text: str
    timestamp: int | None = None


@dataclass(frozen=True)
class MessengerAdminCommand:
    psid: str
    page_id: str | None
    message_id: str
    text: str
    timestamp: int | None = None


class FacebookStateStore(Protocol):
    async def is_duplicate(self, message_id: str) -> bool:
        ...

    async def mark_processed(self, message_id: str) -> None:
        ...

    async def is_human_mode(self, psid: str) -> bool:
        ...

    async def enable_human_mode(self, psid: str) -> None:
        ...

    async def disable_human_mode(self, psid: str) -> None:
        ...

    async def consume_expired_handover(self, psid: str) -> bool:
        ...


class RedisFacebookStateStore:
    def __init__(self, redis_url: str) -> None:
        from redis.asyncio import Redis

        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def is_duplicate(self, message_id: str) -> bool:
        return bool(await self._redis.exists(self._dedupe_key(message_id)))

    async def mark_processed(self, message_id: str) -> None:
        await self._redis.set(
            self._dedupe_key(message_id),
            "1",
            ex=settings.webhook_dedupe_ttl_seconds,
        )

    async def is_human_mode(self, psid: str) -> bool:
        return bool(await self._redis.exists(self._human_key(psid)))

    async def enable_human_mode(self, psid: str) -> None:
        ttl = settings.human_handover_ttl_seconds
        await self._redis.set(self._human_key(psid), "1", ex=ttl)
        await self._redis.set(self._handover_marker_key(psid), "1", ex=ttl + settings.webhook_dedupe_ttl_seconds)

    async def disable_human_mode(self, psid: str) -> None:
        await self._redis.delete(self._human_key(psid), self._handover_marker_key(psid))

    async def consume_expired_handover(self, psid: str) -> bool:
        human_key = self._human_key(psid)
        marker_key = self._handover_marker_key(psid)
        if await self._redis.exists(human_key):
            return False
        if not await self._redis.exists(marker_key):
            return False
        await self._redis.delete(marker_key)
        return True

    @staticmethod
    def _dedupe_key(message_id: str) -> str:
        return f"fb:dedupe:{message_id}"

    @staticmethod
    def _human_key(psid: str) -> str:
        return f"fb:human_mode:{psid}"

    @staticmethod
    def _handover_marker_key(psid: str) -> str:
        return f"fb:human_mode_seen:{psid}"


def build_state_store() -> RedisFacebookStateStore:
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for Facebook handover state.")
    return RedisFacebookStateStore(settings.redis_url)


state_store = build_state_store()


def facebook_verify_token() -> str | None:
    return settings.facebook_verify_token or settings.fb_verify_token


def facebook_app_secret() -> str | None:
    return settings.facebook_app_secret or settings.fb_app_secret


def verify_webhook_challenge(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    if mode == "subscribe" and token and token == facebook_verify_token():
        return challenge or ""
    return None


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    secret = facebook_app_secret()
    if not secret:
        return settings.environment == "development"
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def parse_payload(raw_body: bytes) -> FacebookWebhookPayload:
    data = json.loads(raw_body.decode("utf-8"))
    return FacebookWebhookPayload.model_validate(data)


def extract_text_messages(payload: FacebookWebhookPayload) -> list[MessengerTextMessage]:
    messages: list[MessengerTextMessage] = []
    if payload.object != "page":
        return messages

    for entry in payload.entry:
        for event in entry.messaging:
            message = _extract_text_message(entry.id, event)
            if message:
                messages.append(message)
    return messages


def extract_admin_commands(payload: FacebookWebhookPayload) -> list[MessengerAdminCommand]:
    commands: list[MessengerAdminCommand] = []
    if payload.object != "page":
        return commands

    for entry in payload.entry:
        for event in entry.messaging:
            command = _extract_admin_command(entry.id, event)
            if command:
                commands.append(command)
    return commands


def _extract_text_message(page_id: str | None, event: FacebookMessagingEvent) -> MessengerTextMessage | None:
    if event.delivery or event.read or event.reaction:
        return None
    if not event.sender or not event.message:
        return None
    if event.message.is_echo:
        return None
    if not event.message.text or not event.message.mid:
        return None

    return MessengerTextMessage(
        psid=event.sender.id,
        page_id=page_id or (event.recipient.id if event.recipient else None),
        message_id=event.message.mid,
        text=event.message.text.strip(),
        timestamp=event.timestamp,
    )


def _extract_admin_command(page_id: str | None, event: FacebookMessagingEvent) -> MessengerAdminCommand | None:
    if event.delivery or event.read or event.reaction:
        return None
    if not event.recipient or not event.message:
        return None
    if not event.message.is_echo:
        return None
    if not event.message.text or not event.message.mid:
        return None
    if normalize_command(event.message.text) not in ADMIN_RESUME_COMMANDS:
        return None

    return MessengerAdminCommand(
        psid=event.recipient.id,
        page_id=page_id or (event.sender.id if event.sender else None),
        message_id=event.message.mid,
        text=event.message.text.strip(),
        timestamp=event.timestamp,
    )


def is_customer_resume_command(text: str) -> bool:
    return normalize_command(text) in CUSTOMER_RESUME_COMMANDS


def normalize_command(text: str) -> str:
    return " ".join(text.strip().lower().split())


def should_handover(bot_result: dict[str, Any]) -> bool:
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


def log_facebook_event(
    *,
    psid: str,
    user_message: str,
    bot_response: str | None,
    message_id: str,
    event: str,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "event": event,
        "psid": psid,
        "message_id": message_id,
        "user_message": user_message,
        "bot_response": bot_response,
        "timestamp": int(time.time()),
        **(extra or {}),
    }
    print("[FACEBOOK_WEBHOOK]", payload, flush=True)
