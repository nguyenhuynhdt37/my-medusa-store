import httpx
import pytest
from fastapi import FastAPI

from app.api.storefront_proxy import router


@pytest.mark.asyncio
async def test_proxy_forwards_server_action_post(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = await request.aread()
        captured["next_action"] = request.headers.get("next-action")
        return httpx.Response(
            200,
            content=b"action-response",
            headers={"content-type": "text/x-component"},
        )

    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(client, *args, **kwargs):
        if not isinstance(kwargs.get("transport"), httpx.ASGITransport):
            kwargs["transport"] = transport
        original_init(client, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    app = FastAPI()
    app.include_router(router)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/vn/account?_rsc=action",
            content=b"server-action-body",
            headers={"next-action": "action-id"},
        )

    assert response.status_code == 200
    assert response.content == b"action-response"
    assert captured == {
        "method": "POST",
        "url": "http://localhost:8000/vn/account?_rsc=action",
        "body": b"server-action-body",
        "next_action": "action-id",
    }
