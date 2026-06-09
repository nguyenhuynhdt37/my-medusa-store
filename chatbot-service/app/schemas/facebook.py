from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FacebookUserRef(BaseModel):
    id: str


class FacebookMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    mid: str | None = None
    text: str | None = None
    is_echo: bool = False


class FacebookMessagingEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    sender: FacebookUserRef | None = None
    recipient: FacebookUserRef | None = None
    timestamp: int | None = None
    message: FacebookMessage | None = None
    delivery: dict[str, Any] | None = None
    read: dict[str, Any] | None = None
    reaction: dict[str, Any] | None = None
    postback: dict[str, Any] | None = None


class FacebookEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    time: int | None = None
    messaging: list[FacebookMessagingEvent] = Field(default_factory=list)


class FacebookWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    object: str
    entry: list[FacebookEntry] = Field(default_factory=list)
