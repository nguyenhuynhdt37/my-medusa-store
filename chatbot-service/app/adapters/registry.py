from __future__ import annotations

from app.adapters.base import ChannelAdapter
from app.adapters.facebook import FACEBOOK_CHANNEL, FacebookAdapter


def get_channel_adapter(channel: str) -> ChannelAdapter:
    if channel == FACEBOOK_CHANNEL:
        return FacebookAdapter()
    raise ValueError(f"Unsupported chat channel: {channel}")
