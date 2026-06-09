from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.schemas.facebook import FacebookMessagingEvent, FacebookWebhookPayload


HANDOVER_MESSAGE = "Em chưa chắc về thông tin này. Anh/chị vui lòng chờ trong giây lát, quản trị viên sẽ hỗ trợ trực tiếp."


@dataclass(frozen=True)
class MessengerTextMessage:
    psid: str
    page_id: str | None
    message_id: str
    text: str
    timestamp: int | None = None


class InMemoryFacebookStateStore:
    def __init__(self) -> None:
        self._processed_messages: dict[str, float] = {}
        self._human_mode: dict[str, float] = {}

    async def is_duplicate(self, message_id: str) -> bool:
        self._cleanup()
        return message_id in self._processed_messages

    async def mark_processed(self, message_id: str) -> None:
        self._processed_messages[message_id] = time.time() + settings.webhook_dedupe_ttl_seconds

    async def is_human_mode(self, psid: str) -> bool:
        self._cleanup()
        expires_at = self._human_mode.get(psid)
        return bool(expires_at and expires_at > time.time())

    async def enable_human_mode(self, psid: str) -> None:
        self._human_mode[psid] = time.time() + settings.human_handover_ttl_seconds

    def _cleanup(self) -> None:
        now = time.time()
        self._processed_messages = {
            key: expires_at
            for key, expires_at in self._processed_messages.items()
            if expires_at > now
        }
        self._human_mode = {
            key: expires_at
            for key, expires_at in self._human_mode.items()
            if expires_at > now
        }


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
        await self._redis.set(
            self._human_key(psid),
            "1",
            ex=settings.human_handover_ttl_seconds,
        )

    @staticmethod
    def _dedupe_key(message_id: str) -> str:
        return f"fb:dedupe:{message_id}"

    @staticmethod
    def _human_key(psid: str) -> str:
        return f"fb:human_mode:{psid}"


def build_state_store() -> InMemoryFacebookStateStore | RedisFacebookStateStore:
    if not settings.redis_url:
        return InMemoryFacebookStateStore()
    try:
        return RedisFacebookStateStore(settings.redis_url)
    except ImportError:
        print(
            "[FACEBOOK_STATE_STORE]",
            {"event": "redis_package_missing", "fallback": "memory"},
            flush=True,
        )
        return InMemoryFacebookStateStore()


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


def should_handover(bot_result: dict[str, Any]) -> bool:
    if not settings.enable_human_handover:
        return False

    escalation = bot_result.get("escalation") or {}
    if escalation.get("escalate"):
        return True

    intent = str(bot_result.get("intent") or "").lower()
    if "fallback" in intent or "unknown" in intent:
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
