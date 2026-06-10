import json

import pytest

from app.api.chat_gateway import AIProcessRequest, process_ai_request


class FakeLexClient:
    def __init__(self):
        self.called = False

    async def recognize_text(self, **kwargs):
        self.called = True
        return {}


class FakeFallbackLexClient:
    async def recognize_text(self, **kwargs):
        return {
            "sessionState": {
                "intent": {"name": "FallbackIntent"},
                "sessionAttributes": {
                    "resolved_intent": "fallback",
                    "ai_confidence": "0.5",
                },
            },
            "messages": [
                {
                    "contentType": "PlainText",
                    "content": "Mình chưa hiểu rõ yêu cầu của bạn. Bạn có muốn gặp nhân viên hỗ trợ không?",
                },
                {
                    "contentType": "CustomPayload",
                    "content": json.dumps(
                        {
                            "handover_prompt": {
                                "actions": [
                                    {"label": "Có", "value": "gặp nhân viên"},
                                    {"label": "Không", "value": "continue_bot"},
                                ]
                            }
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }


@pytest.mark.asyncio
async def test_handover_keyword_returns_waiting_message_without_calling_lex():
    lex_client = FakeLexClient()
    request = AIProcessRequest(
        conversationId="conv_1",
        message="Cho tôi gặp nhân viên",
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
    )

    response = await process_ai_request(request, authorization=None, lex_client=lex_client)

    assert lex_client.called is False
    assert response["intent"] == "HumanHandover"
    assert response["escalation"]["escalate"] is True
    assert response["messages"]
    assert "chuyển bạn đến nhân viên" in response["messages"][0]["text"]


@pytest.mark.asyncio
async def test_fallback_prompts_for_handover_without_auto_escalating():
    request = AIProcessRequest(
        conversationId="conv_1",
        message="ủa",
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
    )

    response = await process_ai_request(request, authorization=None, lex_client=FakeFallbackLexClient())

    assert response["intent"] == "fallback"
    assert response["escalation"]["escalate"] is False
    assert response["escalation"]["reason"] == "fallback_prompt"
    assert response["messages"][0]["payload"]["handover_prompt"]["actions"] == [
        {"label": "Có", "value": "gặp nhân viên"},
        {"label": "Không", "value": "continue_bot"},
    ]


@pytest.mark.asyncio
async def test_abusive_language_is_blocked_without_calling_lex_or_handover():
    lex_client = FakeLexClient()
    request = AIProcessRequest(
        conversationId="conv_1",
        message="địt mẹ",
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
    )

    response = await process_ai_request(request, authorization=None, lex_client=lex_client)

    assert lex_client.called is False
    assert response["intent"] == "BlockedAbusiveLanguage"
    assert response["escalation"]["escalate"] is False
    assert response["escalation"]["reason"] == "abusive_language"
    assert "giữ cuộc trò chuyện lịch sự" in response["messages"][0]["text"]
