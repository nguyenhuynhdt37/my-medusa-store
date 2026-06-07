from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DialogflowParameterValue(BaseModel):
    original_value: str | None = Field(default=None, alias="originalValue")
    resolved_value: Any | None = Field(default=None, alias="resolvedValue")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FulfillmentInfo(BaseModel):
    tag: str | None = None

    model_config = ConfigDict(extra="allow")


class IntentInfo(BaseModel):
    display_name: str | None = Field(default=None, alias="displayName")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SessionInfo(BaseModel):
    parameters: dict[str, DialogflowParameterValue | Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class DialogflowCXRequest(BaseModel):
    fulfillment_info: FulfillmentInfo | None = Field(default=None, alias="fulfillmentInfo")
    intent_info: IntentInfo | None = Field(default=None, alias="intentInfo")
    session_info: SessionInfo | None = Field(default=None, alias="sessionInfo")
    payload: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def intent_name(self) -> str:
        tag = self.fulfillment_info.tag if self.fulfillment_info else None
        display_name = self.intent_info.display_name if self.intent_info else None
        return (tag or display_name or "Fallback").strip()

    def get_parameter(self, names: list[str]) -> str | None:
        if not self.session_info:
            return self.get_payload_value(names)

        for name in names:
            value = self.session_info.parameters.get(name)
            if isinstance(value, DialogflowParameterValue):
                resolved = value.resolved_value or value.original_value
            elif isinstance(value, dict):
                resolved = value.get("resolvedValue") or value.get("originalValue")
            else:
                resolved = value

            if resolved is None:
                continue
            if isinstance(resolved, list):
                resolved = " ".join(str(item) for item in resolved)
            text = str(resolved).strip()
            if text:
                return text
        return self.get_payload_value(names)

    def get_payload_value(self, names: list[str]) -> str | None:
        for name in names:
            value = self.payload.get(name)
            if isinstance(value, dict):
                value = value.get("token") or value.get("value") or value.get("authorization")
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None


class TextMessage(BaseModel):
    text: list[str]


class ResponseMessage(BaseModel):
    text: TextMessage | None = None
    payload: dict[str, Any] | None = None


class FulfillmentResponse(BaseModel):
    messages: list[ResponseMessage]


class DialogflowCXResponse(BaseModel):
    fulfillment_response: FulfillmentResponse = Field(alias="fulfillmentResponse")
    session_info: SessionInfo | None = Field(default=None, alias="sessionInfo")

    model_config = ConfigDict(populate_by_name=True)
