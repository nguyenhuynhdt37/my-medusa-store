from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InboundMessage:
    channel: str
    channel_account_id: str
    external_user_id: str
    external_message_id: str
    text: str
    timestamp: int | None = None
    is_admin_echo: bool = False


class ChannelAdapter(Protocol):
    async def send_message(self, external_user_id: str, text: str) -> dict:
        ...
