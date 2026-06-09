import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_facebook_webhook_verification(monkeypatch):
    monkeypatch.setattr(settings, "facebook_verify_token", "verify-token")

    response = TestClient(app).get(
        "/facebook/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-token",
            "hub.challenge": "challenge-value",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-value"


def test_facebook_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(settings, "facebook_app_secret", "secret")

    response = TestClient(app).post(
        "/facebook/webhook",
        content=b'{"object":"page","entry":[]}',
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )

    assert response.status_code == 403


def test_facebook_webhook_ignores_echo_message(monkeypatch):
    monkeypatch.setattr(settings, "facebook_app_secret", "secret")
    body = {
        "object": "page",
        "entry": [
            {
                "id": "page_1",
                "messaging": [
                    {
                        "sender": {"id": "psid_1"},
                        "recipient": {"id": "page_1"},
                        "timestamp": 1,
                        "message": {
                            "mid": "mid_1",
                            "text": "hello",
                            "is_echo": True,
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(body).encode("utf-8")
    signature = hmac.new(b"secret", raw_body, hashlib.sha256).hexdigest()

    response = TestClient(app).post(
        "/facebook/webhook",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
