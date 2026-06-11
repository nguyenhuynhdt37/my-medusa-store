import httpx
import pytest

from app.clients.gemini_client import GeminiClient


class FakeResponse:
    status_code = 200
    text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "{\"intent\":\"product_price\",\"confidence\":0.9}"}],
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


class FakeRateLimitResponse:
    status_code = 429
    text = '{"error":"quota exceeded"}'

    def raise_for_status(self):
        request = httpx.Request("POST", "https://generativelanguage.googleapis.com")
        response = httpx.Response(self.status_code, request=request, text=self.text)
        raise httpx.HTTPStatusError("Too Many Requests", request=request, response=response)


class FakeRateLimitAsyncClient(FakeAsyncClient):
    async def post(self, *args, **kwargs):
        return FakeRateLimitResponse()


@pytest.mark.asyncio
async def test_gemini_generation_exposes_usage_metadata(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    client = GeminiClient(api_key="key", model="gemini-2.0-flash")

    resolution, usage = await client.resolve_customer_intent_with_usage(
        lex_intent="FallbackIntent",
        user_text="iPhone giá bao nhiêu",
    )

    assert resolution == {"intent": "product_price", "confidence": 0.9}
    assert usage == {
        "promptTokenCount": 123,
        "candidatesTokenCount": 45,
        "totalTokenCount": 168,
    }


@pytest.mark.asyncio
async def test_gemini_429_starts_cooldown(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", FakeRateLimitAsyncClient)
    client = GeminiClient(api_key="key", model="gemini-2.5-flash", rate_limit_cooldown_seconds=60)

    with pytest.raises(Exception, match="429"):
        await client.resolve_customer_intent_with_usage(
            lex_intent="FallbackIntent",
            user_text="hello",
        )

    assert client.is_enabled() is False
