from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class MessengerAPIError(RuntimeError):
    pass


def page_access_token() -> str | None:
    return settings.facebook_page_access_token or settings.fb_page_access_token


def graph_version() -> str:
    return settings.facebook_graph_version or settings.fb_graph_version


async def send_text_message(psid: str, text: str) -> dict[str, Any]:
    token = page_access_token()
    if not token:
        raise MessengerAPIError("Facebook page access token is not configured.")

    url = f"https://graph.facebook.com/{graph_version()}/me/messages"
    body = {
        "recipient": {"id": psid},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    params = {"access_token": token}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.post(url, params=params, json=body)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise MessengerAPIError(
            f"Facebook Graph API returned HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise MessengerAPIError(f"Facebook Graph API request failed: {exc}") from exc

    return data
