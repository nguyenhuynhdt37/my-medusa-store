import pytest

from app.api.chat_gateway import AIProcessRequest, process_ai_request
from app.services.bot_orchestrator import BotOrchestrator


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
                    "content": "Mình chưa hiểu rõ yêu cầu của bạn. Bạn có thể hỏi về sản phẩm, giá, ưu đãi, giao hàng hoặc đơn hàng để mình hỗ trợ nhé.",
                },
            ],
        }


class FakeHumanMisclassifiedLexClient:
    async def recognize_text(self, **kwargs):
        return {
            "sessionState": {
                "intent": {"name": "HumanHandoverIntent"},
                "sessionAttributes": {
                    "ai_confidence": "0.95",
                },
            },
            "messages": [
                {
                    "contentType": "PlainText",
                    "content": "Mình sẽ chuyển bạn sang nhân viên hỗ trợ.",
                },
            ],
        }


class FakeStaleBotFinalMessageLexClient:
    async def recognize_text(self, **kwargs):
        return {
            "sessionState": {
                "intent": {"name": "FallbackIntent"},
                "sessionAttributes": {
                    "resolved_intent": "smalltalk_compliment",
                    "ai_confidence": "1.0",
                    "bot_final_message": "Gợi ý sản phẩm\n- iPhone 17: 22.990.000 VNĐ",
                },
            },
            "messages": [
                {
                    "contentType": "PlainText",
                    "content": "Cảm ơn bạn nha. Mình là trợ lý ảo của shop, mình có thể hỗ trợ bạn xem sản phẩm, giá, ưu đãi hoặc đơn hàng nhé!",
                },
            ],
        }


class FakeStaleFallbackProductReplyLexClient:
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
                    "content": "Sản phẩm phù hợp\n- iPhone 17: 22.990.000 VNĐ",
                },
            ],
        }


class FakeRateLimitedGeminiClient:
    def __init__(self):
        self.called = False

    def is_enabled(self):
        return True

    async def normalize_user_query_with_usage(self, **kwargs):
        self.called = True
        raise RuntimeError("429 Too Many Requests")


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
async def test_fallback_steers_back_to_bot_scope_without_auto_escalating():
    request = AIProcessRequest(
        conversationId="conv_1",
        message="ủa",
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
    )

    response = await process_ai_request(request, authorization=None, lex_client=FakeFallbackLexClient())

    assert response["intent"] == "fallback"
    assert response["escalation"]["escalate"] is False
    assert response["escalation"]["reason"] == "fallback_prompt"
    assert "sản phẩm" in response["reply"]
    assert all(message.get("payload") is None for message in response["messages"])


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


def test_bot_orchestrator_does_not_handover_fallback_or_low_confidence():
    orchestrator = BotOrchestrator()

    assert orchestrator.should_handover(
        {"intent": "fallback", "confidence": 0.2, "escalation": {"escalate": False}}
    ) is False
    assert orchestrator.should_handover(
        {"intent": "HumanHandover", "confidence": 0.99, "escalation": {"escalate": False}},
        message="bạn đjp zai quá",
    ) is False


def test_bot_orchestrator_only_handovers_explicit_human_or_escalation():
    orchestrator = BotOrchestrator()

    assert orchestrator.should_handover({"intent": "HumanHandover", "confidence": 1.0}, message="cho tôi gặp nhân viên") is True
    assert orchestrator.should_handover({"intent": "fallback", "escalation": {"escalate": True}}) is True


@pytest.mark.asyncio
async def test_smalltalk_compliment_overrides_misclassified_human_intent():
    request = AIProcessRequest(
        conversationId="conv_1",
        message="bạn đjp zai quá",
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
    )

    response = await process_ai_request(request, authorization=None, lex_client=FakeHumanMisclassifiedLexClient())

    assert response["intent"] == "smalltalk_compliment"
    assert "chuyển" not in response["reply"].lower()
    assert "Cảm ơn" in response["reply"]
    assert response["escalation"]["escalate"] is False


@pytest.mark.asyncio
async def test_fresh_message_wins_over_stale_bot_final_message_attribute():
    request = AIProcessRequest(
        conversationId="conv_1",
        message="bot dễ thương ghê",
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
    )

    response = await process_ai_request(request, authorization=None, lex_client=FakeStaleBotFinalMessageLexClient())

    assert response["intent"] == "smalltalk_compliment"
    assert "Cảm ơn" in response["reply"]
    assert "iPhone 17" not in response["reply"]
    assert response["escalation"]["escalate"] is False


@pytest.mark.asyncio
async def test_fallback_intent_sanitizes_stale_product_reply():
    request = AIProcessRequest(
        conversationId="conv_1",
        message="F8 học lập trình để đi làm",
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
    )

    response = await process_ai_request(request, authorization=None, lex_client=FakeStaleFallbackProductReplyLexClient())

    assert response["intent"] == "fallback"
    assert "Mình chưa hiểu rõ" in response["reply"]
    assert "iPhone 17" not in response["reply"]
    assert response["escalation"]["escalate"] is False


@pytest.mark.asyncio
async def test_ok_with_vocative_is_smalltalk_when_gemini_rate_limited():
    gemini_client = FakeRateLimitedGeminiClient()
    request = AIProcessRequest(
        conversationId="conv_1",
        message="Ok cậu",
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
    )

    response = await process_ai_request(
        request,
        authorization=None,
        lex_client=FakeFallbackLexClient(),
        gemini_client=gemini_client,
    )

    assert gemini_client.called is False
    assert response["intent"] == "smalltalk_affirmation"
    assert response["confidence"] == 1.0
    assert response["escalation"]["escalate"] is False
    assert "Dạ vâng" in response["reply"]


@pytest.mark.asyncio
async def test_smalltalk_compliment_short_circuits_lex_context_bleed():
    lex_client = FakeLexClient()
    request = AIProcessRequest(
        conversationId="conv_1",
        message="Bạn đẹp giai quá",
        customer_context={"guest_id": "guest_1", "channel": "WEB"},
        session_context={"current_product_name": "iPhone 12"},
    )

    response = await process_ai_request(request, authorization=None, lex_client=lex_client)

    assert lex_client.called is False
    assert response["intent"] == "smalltalk_compliment"
    assert "Cảm ơn" in response["reply"]
    assert "iPhone 12" not in response["reply"]
    assert response["escalation"]["escalate"] is False
