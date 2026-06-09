from __future__ import annotations

from app.adapters.base import InboundMessage
from app.schemas.facebook import FacebookWebhookPayload
from app.services.facebook_service import (
    MessengerAdminCommand,
    extract_admin_commands,
    extract_text_messages,
    parse_payload,
    verify_signature,
    verify_webhook_challenge,
)
from app.services.messenger_service import send_bot_messages, send_text_message

FACEBOOK_CHANNEL = "MESSENGER"


class FacebookAdapter:
    def verify_challenge(self, mode: str | None, token: str | None, challenge: str | None) -> str | None:
        return verify_webhook_challenge(mode, token, challenge)

    def verify_signature(self, raw_body: bytes, signature_header: str | None) -> bool:
        return verify_signature(raw_body, signature_header)

    def parse_webhook_payload(self, raw_body: bytes) -> FacebookWebhookPayload:
        return parse_payload(raw_body)

    def parse_inbound_event(self, payload: FacebookWebhookPayload) -> list[InboundMessage]:
        return [
            InboundMessage(
                channel=FACEBOOK_CHANNEL,
                channel_account_id=message.page_id or "default",
                external_user_id=message.psid,
                external_message_id=message.message_id,
                text=message.text,
                timestamp=message.timestamp,
            )
            for message in extract_text_messages(payload)
        ]

    def parse_admin_commands(self, payload: FacebookWebhookPayload) -> list[MessengerAdminCommand]:
        return extract_admin_commands(payload)

    async def send_message(self, external_user_id: str, text: str) -> dict:
        return await send_text_message(external_user_id, text)

    async def send_bot_messages(self, external_user_id: str, text: str, messages: list[dict] | None = None) -> list[dict]:
        return await send_bot_messages(external_user_id, text, messages)
