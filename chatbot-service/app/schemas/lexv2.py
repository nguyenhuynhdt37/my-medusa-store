from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dialogflow import DialogflowCXRequest, DialogflowCXResponse


class LexV2Request(BaseModel):
    session_state: dict[str, Any] = Field(default_factory=dict, alias="sessionState")
    input_transcript: str | None = Field(default=None, alias="inputTranscript")
    invocation_source: str | None = Field(default=None, alias="invocationSource")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def intent_name(self) -> str:
        intent = self.session_state.get("intent") or {}
        return str(intent.get("name") or "FallbackIntent")

    def slot_parameters(self) -> dict[str, str]:
        intent = self.session_state.get("intent") or {}
        slots = intent.get("slots") or {}
        parameters: dict[str, str] = {}

        for name, slot in slots.items():
            value = extract_lex_slot_value(slot)
            if value:
                parameters[name] = value

        return parameters

    def to_dialogflow_request(self) -> DialogflowCXRequest:
        return DialogflowCXRequest.model_validate(
            {
                "intentInfo": {"displayName": self.intent_name()},
                "sessionInfo": {
                    "parameters": {
                        key: {"resolvedValue": value}
                        for key, value in self.slot_parameters().items()
                    }
                },
                "text": self.input_transcript,
            }
        )


def extract_lex_slot_value(slot: Any) -> str | None:
    if not slot:
        return None
    if isinstance(slot, str):
        return slot.strip() or None
    if not isinstance(slot, dict):
        return str(slot).strip() or None

    value = slot.get("value") or {}
    if isinstance(value, dict):
        for key in ("interpretedValue", "resolvedValues", "originalValue"):
            resolved = value.get(key)
            if isinstance(resolved, list):
                resolved = resolved[0] if resolved else None
            if resolved:
                return str(resolved).strip()

    return None


def dialogflow_response_to_lexv2(
    request: LexV2Request,
    response: DialogflowCXResponse,
) -> dict[str, Any]:
    text = "Mình đã xử lý yêu cầu của bạn."
    if response.fulfillment_response.messages:
        message = response.fulfillment_response.messages[0]
        if message.text and message.text.text:
            text = message.text.text[0]

    session_attributes = {}
    if response.session_info:
        session_attributes = {
            key: str(value)
            for key, value in response.session_info.parameters.items()
            if value is not None
        }

    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {
                "name": request.intent_name(),
                "state": "Fulfilled",
            },
            "sessionAttributes": session_attributes,
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": text,
            }
        ],
    }
