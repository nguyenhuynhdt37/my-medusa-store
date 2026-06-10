import httpx
import pytest

from app.clients.gemini_client import GeminiClient


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Đã viết lại"}],
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 123,
                "candidatesTokenCount": 45,
                "totalTokenCount": 168,
            },
        }


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return FakeResponse()


@pytest.mark.asyncio
async def test_gemini_generation_exposes_usage_metadata(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    client = GeminiClient(api_key="key", model="gemini-2.0-flash")

    result = await client.rewrite_customer_reply_with_usage(
        intent="product_price",
        user_text="iPhone giá bao nhiêu",
        draft_reply="iPhone giá 22.990.000 VNĐ",
    )

    assert result.text == "Đã viết lại"
    assert result.usage_metadata == {
        "promptTokenCount": 123,
        "candidatesTokenCount": 45,
        "totalTokenCount": 168,
    }
