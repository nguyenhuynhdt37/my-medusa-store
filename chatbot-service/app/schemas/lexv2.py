from __future__ import annotations

import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class LexV2Message(BaseModel):
    contentType: str
    content: str


class LexV2Intent(BaseModel):
    name: str
    state: str = "Fulfilled"


class LexV2DialogAction(BaseModel):
    type: str = "Close"


class LexV2SessionState(BaseModel):
    dialogAction: LexV2DialogAction = Field(default_factory=LexV2DialogAction)
    intent: LexV2Intent
    sessionAttributes: dict[str, Any] = Field(default_factory=dict)


class SessionInfoMock:
    def __init__(self, parameters: dict[str, Any] = None):
        self.parameters = parameters if parameters is not None else {}


class TextListCompat(list):
    def __init__(self, msg: LexV2Message):
        super().__init__([msg.content])
        self._msg = msg

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        if index == 0 or index == -1:
            self._msg.content = value


class TextMessageCompat:
    def __init__(self, parent_msg: LexV2Message):
        self._msg = parent_msg

    @property
    def text(self) -> TextListCompat:
        return TextListCompat(self._msg)

    @text.setter
    def text(self, val: list[str]):
        if val:
            self._msg.content = val[0]


class MessageCompat:
    def __init__(self, lex_msg: LexV2Message):
        self._msg = lex_msg

    @property
    def text(self) -> TextMessageCompat | None:
        if self._msg.contentType == "PlainText":
            return TextMessageCompat(self._msg)
        return None

    @property
    def payload(self) -> dict[str, Any] | None:
        if self._msg.contentType == "CustomPayload":
            try:
                return json.loads(self._msg.content)
            except Exception:
                return {}
        return None


class FulfillmentResponseCompat:
    def __init__(self, response: LexV2Response):
        self._res = response

    @property
    def messages(self) -> list[MessageCompat]:
        return [MessageCompat(m) for m in self._res.messages]


class LexV2Response(BaseModel):
    sessionState: LexV2SessionState
    messages: list[LexV2Message]

    model_config = ConfigDict(populate_by_name=True)

    # Dialogflow Compatibility Layer for IntentService / Tests
    @property
    def session_info(self) -> SessionInfoMock:
        return SessionInfoMock(self.sessionState.sessionAttributes)

    @session_info.setter
    def session_info(self, val: Any):
        if hasattr(val, "parameters"):
            self.sessionState.sessionAttributes = val.parameters
        else:
            self.sessionState.sessionAttributes = val

    @property
    def fulfillment_response(self) -> FulfillmentResponseCompat:
        return FulfillmentResponseCompat(self)


class LexV2Request(BaseModel):
    session_state: dict[str, Any] = Field(default_factory=dict, alias="sessionState")
    input_transcript: str | None = Field(default=None, alias="inputTranscript")
    invocation_source: str | None = Field(default=None, alias="invocationSource")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @property
    def text(self) -> str | None:
        return self.input_transcript

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

    def get_parameter(self, names: list[str]) -> str | None:
        # Check sessionAttributes first
        session_attributes = self.session_state.get("sessionAttributes") or {}
        for name in names:
            if name in session_attributes and session_attributes[name] is not None:
                return str(session_attributes[name]).strip()

        # Check slots (intent parameters)
        slots = self.slot_parameters()
        for name in names:
            if name in slots and slots[name] is not None:
                return str(slots[name]).strip()

        return None

    @property
    def session_info(self) -> SessionInfoMock:
        if not hasattr(self, "_session_info_mock"):
            attrs = self.session_state.setdefault("sessionAttributes", {})
            self._session_info_mock = SessionInfoMock(attrs)
        return self._session_info_mock

    @session_info.setter
    def session_info(self, val: Any):
        if hasattr(val, "parameters"):
            self.session_state["sessionAttributes"] = val.parameters
        else:
            self.session_state["sessionAttributes"] = val
        self._session_info_mock = SessionInfoMock(self.session_state["sessionAttributes"])


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


def text_response(message: str, parameters: dict | None = None) -> LexV2Response:
    return LexV2Response(
        sessionState=LexV2SessionState(
            intent=LexV2Intent(name=""),
            sessionAttributes=parameters or {},
        ),
        messages=[
            LexV2Message(
                contentType="PlainText",
                content=message,
            )
        ]
    )


def rich_response(markdown: str, payload: dict, parameters: dict | None = None) -> LexV2Response:
    return LexV2Response(
        sessionState=LexV2SessionState(
            intent=LexV2Intent(name=""),
            sessionAttributes=parameters or {},
        ),
        messages=[
            LexV2Message(
                contentType="PlainText",
                content=markdown,
            ),
            LexV2Message(
                contentType="CustomPayload",
                content=json.dumps(payload),
            )
        ]
    )


# Mocks for Dialogflow Compatibility
class DialogflowParameterValueMock:
    pass

DialogflowParameterValue = DialogflowParameterValueMock
SessionInfo = SessionInfoMock
DialogflowCXRequest = LexV2Request
DialogflowCXResponse = LexV2Response
