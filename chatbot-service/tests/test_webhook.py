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
