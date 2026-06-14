from fastapi.testclient import TestClient

from app.main import app


def test_greeting_webhook():
    client = TestClient(app)
    response = client.post(
        "/lexv2/webhook",
        json={
            "sessionState": {
                "intent": {
                    "name": "Greeting",
                    "slots": {},
                }
            },
            "inputTranscript": "hello",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sessionState"]["dialogAction"]["type"] == "Close"
    assert body["sessionState"]["intent"]["state"] == "Fulfilled"
    message = body["messages"][0]["content"]
    assert "hỗ trợ" in message or "giúp" in message


def test_lexv2_shipping_webhook():
    client = TestClient(app)
    response = client.post(
        "/lexv2/webhook",
        json={
            "sessionState": {
                "intent": {
                    "name": "ShippingPolicyIntent",
                    "slots": {},
                }
            },
            "inputTranscript": "phí ship bao nhiêu",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sessionState"]["dialogAction"]["type"] == "Close"
    assert body["sessionState"]["intent"]["state"] == "Fulfilled"
    assert "Giao hàng tiêu chuẩn" in body["messages"][0]["content"]


def test_lexv2_followup_reads_session_attributes():
    client = TestClient(app)
    response = client.post(
        "/lexv2/webhook",
        json={
            "sessionState": {
                "intent": {
                    "name": "ShippingPolicyIntent",
                    "slots": {},
                },
                "sessionAttributes": {
                    "current_product_name": "iPhone 17 Pro Max",
                },
            },
            "inputTranscript": "phí ship bao nhiêu",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sessionState"]["dialogAction"]["type"] == "Close"
    assert body["sessionState"]["sessionAttributes"]["current_product_name"] == "iPhone 17 Pro Max"
    assert "Giao hàng tiêu chuẩn" in body["messages"][0]["content"]


def test_recommendation_webhook_with_gemini():
    from app.clients.medusa_client import get_medusa_client
    from app.clients.gemini_client import get_gemini_client
    from tests.test_intent_service import FakeRecommendationGeminiClient

    class CustomFakeMedusaClient:
        async def list_products(self, query=None, limit=150):
            return [
                {
                    "id": "prod_1",
                    "title": "iPhone 15 Pro",
                    "handle": "iphone-15-pro",
                    "metadata": {
                        "chip": "A17 Pro",
                    },
                    "variants": [
                        {
                            "title": "Default",
                            "calculated_price": {
                                "calculated_amount": 25000000,
                                "currency_code": "vnd",
                            }
                        }
                    ]
                }
            ]

    fake_medusa = CustomFakeMedusaClient()
    fake_gemini = FakeRecommendationGeminiClient()

    app.dependency_overrides[get_medusa_client] = lambda: fake_medusa
    app.dependency_overrides[get_gemini_client] = lambda: fake_gemini

    try:
        client = TestClient(app)
        response = client.post(
            "/lexv2/webhook",
            json={
                "sessionState": {
                    "intent": {
                        "name": "ProductRecommendation",
                        "slots": {},
                    }
                },
                "inputTranscript": "máy nào quay phim đẹp",
            },
        )

        assert response.status_code == 200
        body = response.json()
        
        # Verify dialogAction and intent state
        assert body["sessionState"]["dialogAction"]["type"] == "Close"
        assert body["sessionState"]["intent"]["state"] == "Fulfilled"
        
        # Verify that Gemini recommendation was called and used
        assert fake_gemini.recommendation_called is True
        assert fake_gemini.last_user_text == "máy nào quay phim đẹp"
        
        # Verify the returned message content contains the custom message from Gemini
        message = body["messages"][0]["content"]
        assert "Đây là gợi ý của Gemini dành cho mẹ của bạn." in message
        assert "iPhone 15 Pro" in message
        assert body["sessionState"]["sessionAttributes"]["search_status"] == "recommendation_success"
    finally:
        app.dependency_overrides.clear()


def test_fallback_webhook_does_not_call_gemini():
    from app.clients.medusa_client import get_medusa_client
    from app.clients.gemini_client import get_gemini_client
    from tests.test_intent_service import FakeIntentResolvingGeminiClient, FakeMedusaClient

    fake_medusa = FakeMedusaClient()
    fake_gemini = FakeIntentResolvingGeminiClient()

    app.dependency_overrides[get_medusa_client] = lambda: fake_medusa
    app.dependency_overrides[get_gemini_client] = lambda: fake_gemini

    try:
        client = TestClient(app)
        response = client.post(
            "/lexv2/webhook",
            json={
                "sessionState": {
                    "intent": {
                        "name": "FallbackIntent",
                        "slots": {},
                    }
                },
                "inputTranscript": "kể chuyện ma đi",
            },
        )

        assert response.status_code == 200
        body = response.json()
        
        # Verify that Gemini was NOT called
        assert fake_gemini.resolve_called is False
        
        # Verify response message and resolved intent
        message = body["messages"][0]["content"]
        assert "Mình chưa hiểu rõ yêu cầu của bạn." in message
        assert body["sessionState"]["sessionAttributes"]["resolved_intent"] == "fallback"
        assert body["sessionState"]["sessionAttributes"]["resolution_source"] == "local_nlu"
    finally:
        app.dependency_overrides.clear()

