import pytest
from fastapi import HTTPException

from app.api.chat_gateway import AIProcessRequest, process_ai_request
from app.services.bot_orchestrator import BotOrchestrator


class FakeLexClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = []

    async def recognize_text(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def request(message: str = "giá iPhone 17 Pro Max") -> AIProcessRequest:
    return AIProcessRequest(
        conversationId="conv_1",
        message=message,
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
    )


def successful_lex_response() -> dict:
    return {
        "sessionState": {
            "intent": {"name": "ProductPriceIntent", "state": "Fulfilled"},
            "sessionAttributes": {
                "resolved_intent": "product_price",
                "resolution_source": "lex",
                "ai_confidence": "1.0",
            },
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": "iPhone 17 Pro Max có giá từ 34.990.000 VNĐ.",
            }
        ],
    }


@pytest.mark.asyncio
async def test_success_returns_lex_response_without_rewriting():
    lex_client = FakeLexClient(successful_lex_response())

    response = await process_ai_request(request(), authorization=None, lex_client=lex_client)

    assert len(lex_client.calls) == 1
    assert lex_client.calls[0]["text"] == "giá iPhone 17 Pro Max"
    assert response["intent"] == "product_price"
    assert response["reply"] == "iPhone 17 Pro Max có giá từ 34.990.000 VNĐ."


@pytest.mark.asyncio
async def test_cart_id_is_forwarded_to_lex_request_attributes():
    lex_client = FakeLexClient(successful_lex_response())
    body = request()
    body.customer_context["cart_id"] = "cart_123"

    await process_ai_request(body, authorization=None, lex_client=lex_client)

    assert lex_client.calls[0]["request_attributes"]["cart_id"] == "cart_123"


@pytest.mark.asyncio
async def test_fallback_intent_returns_200():
    lex_client = FakeLexClient(
        {
            "sessionState": {
                "intent": {"name": "FallbackIntent", "state": "Fulfilled"},
                "sessionAttributes": {
                    "resolved_intent": "fallback",
                    "resolution_source": "gemini",
                },
            },
            "messages": [{"contentType": "PlainText", "content": "Fallback response"}],
        }
    )

    response = await process_ai_request(request("không rõ"), authorization=None, lex_client=lex_client)
    assert response["intent"] == "fallback"
    assert response["reply"] == "Fallback response"
    assert len(lex_client.calls) == 1


@pytest.mark.asyncio
async def test_gemini_resolved_fallback_is_accepted():
    lex_client = FakeLexClient(
        {
            "sessionState": {
                "intent": {"name": "FallbackIntent", "state": "Fulfilled"},
                "sessionAttributes": {
                    "resolved_intent": "product_recommendation",
                    "resolution_source": "gemini",
                    "ai_confidence": "0.83",
                },
            },
            "messages": [
                {
                    "contentType": "PlainText",
                    "content": "Mình gợi ý các mẫu pin tốt trong tầm giá của bạn.",
                }
            ],
        }
    )

    response = await process_ai_request(
        request("máy nào pin tốt cho mẹ"),
        authorization=None,
        lex_client=lex_client,
    )

    assert response["intent"] == "product_recommendation"
    assert response["reply"] == "Mình gợi ý các mẫu pin tốt trong tầm giá của bạn."


@pytest.mark.asyncio
async def test_query_is_preprocessed_before_lex():
    lex_client = FakeLexClient(successful_lex_response())

    await process_ai_request(request("  ip15   giá bao nhiêu "), authorization=None, lex_client=lex_client)

    assert lex_client.calls[0]["text"] == "iPhone 15 giá bao nhiêu"
    assert lex_client.calls[0]["request_attributes"]["original_text"] == "ip15   giá bao nhiêu"


@pytest.mark.asyncio
async def test_failed_fulfillment_returns_502():
    lex_client = FakeLexClient(
        {
            "sessionState": {
                "intent": {"name": "ProductPriceIntent", "state": "Failed"},
                "sessionAttributes": {},
            },
            "messages": [],
        }
    )

    with pytest.raises(HTTPException, match="fulfillment failed") as exc_info:
        await process_ai_request(request(), authorization=None, lex_client=lex_client)

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_missing_lex_message_returns_502():
    lex_client = FakeLexClient(
        {
            "sessionState": {
                "intent": {"name": "ProductPriceIntent", "state": "Fulfilled"},
                "sessionAttributes": {},
            },
            "messages": [],
        }
    )

    with pytest.raises(HTTPException, match="no message") as exc_info:
        await process_ai_request(request(), authorization=None, lex_client=lex_client)

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_lex_exception_returns_502():
    lex_client = FakeLexClient(error=RuntimeError("Lambda dependency failed"))

    with pytest.raises(HTTPException, match="Lex request failed") as exc_info:
        await process_ai_request(request(), authorization=None, lex_client=lex_client)

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_normal_smalltalk_is_sent_to_lex():
    response = successful_lex_response()
    response["sessionState"]["intent"]["name"] = "GreetingIntent"
    response["sessionState"]["sessionAttributes"]["resolved_intent"] = "greeting"
    response["messages"][0]["content"] = "Xin chào!"
    lex_client = FakeLexClient(response)

    result = await process_ai_request(request("xin chào"), authorization=None, lex_client=lex_client)

    assert len(lex_client.calls) == 1
    assert result["reply"] == "Xin chào!"


@pytest.mark.asyncio
async def test_handover_keyword_returns_waiting_message_without_calling_lex():
    lex_client = FakeLexClient(successful_lex_response())

    response = await process_ai_request(
        request("Cho tôi gặp nhân viên"),
        authorization=None,
        lex_client=lex_client,
    )

    assert lex_client.calls == []
    assert response["intent"] == "HumanHandover"
    assert response["escalation"]["escalate"] is True


@pytest.mark.asyncio
async def test_abusive_language_is_blocked_without_calling_lex():
    lex_client = FakeLexClient(successful_lex_response())

    response = await process_ai_request(
        request("địt mẹ"),
        authorization=None,
        lex_client=lex_client,
    )

    assert lex_client.calls == []
    assert response["intent"] == "BlockedAbusiveLanguage"
    assert response["escalation"]["escalate"] is False


def test_bot_orchestrator_only_handovers_explicit_human_or_escalation():
    orchestrator = BotOrchestrator()

    assert orchestrator.should_handover(
        {"intent": "HumanHandover", "confidence": 1.0},
        message="cho tôi gặp nhân viên",
    ) is True
    assert orchestrator.should_handover(
        {"intent": "fallback", "escalation": {"escalate": True}}
    ) is True
