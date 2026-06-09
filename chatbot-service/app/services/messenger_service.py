from __future__ import annotations

import re
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
    return await send_messenger_message(psid, {"text": text})


async def send_messenger_message(psid: str, message: dict[str, Any]) -> dict[str, Any]:
    token = page_access_token()
    if not token:
        raise MessengerAPIError("Facebook page access token is not configured.")

    url = f"https://graph.facebook.com/{graph_version()}/me/messages"
    body = {
        "recipient": {"id": psid},
        "message": message,
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


async def send_bot_messages(psid: str, text: str, messages: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    payload = first_payload(messages or [])
    elements = generic_template_elements(payload)
    sent: list[dict[str, Any]] = []

    text_to_send = messenger_plain_text(text, has_template=bool(elements))
    if text_to_send:
        sent.append(await send_text_message(psid, text_to_send))

    for chunk in chunked(elements, 10):
        sent.append(await send_generic_template(psid, chunk))

    return sent


async def send_generic_template(psid: str, elements: list[dict[str, Any]]) -> dict[str, Any]:
    return await send_messenger_message(
        psid,
        {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements,
                },
            }
        },
    )


def first_payload(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for message in messages:
        payload = message.get("payload")
        if isinstance(payload, dict):
            return payload
    return None


def generic_template_elements(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []

    products = payload.get("products")
    if not isinstance(products, list) or not products:
        product = payload.get("product")
        products = [product] if isinstance(product, dict) else []

    elements: list[dict[str, Any]] = []
    for product in products:
        if not isinstance(product, dict):
            continue
        title = str(product.get("title") or "Sản phẩm")[:80]
        url = product.get("url")
        image_url = product.get("image")
        subtitle_parts = []
        if product.get("price_from"):
            subtitle_parts.append(f"Giá từ {product['price_from']}")
        if product.get("discount"):
            subtitle_parts.append(f"Ưu đãi: {product['discount']}")

        element: dict[str, Any] = {
            "title": title,
            "subtitle": "\n".join(subtitle_parts)[:80] or "Xem thông tin sản phẩm",
        }
        if isinstance(image_url, str) and image_url.startswith("https://"):
            element["image_url"] = image_url
        if isinstance(url, str) and url.startswith("https://"):
            element["default_action"] = {
                "type": "web_url",
                "url": url,
                "webview_height_ratio": "tall",
            }
            element["buttons"] = [
                {
                    "type": "web_url",
                    "url": url,
                    "title": "Xem chi tiết",
                    "webview_height_ratio": "tall",
                }
            ]
        elements.append(element)

    return elements


def messenger_plain_text(text: str, *, has_template: bool = False) -> str:
    clean = re.sub(r"!\[[^\]]*]\([^)]+\)", "", text or "")
    clean = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", clean)
    clean = clean.replace("###", "").replace("**", "").replace("*   ", "- ")
    lines = [line.strip() for line in clean.splitlines()]
    lines = [line for line in lines if line]
    if has_template:
        lines = [line for line in lines if not line.startswith("- ")]
    return "\n".join(lines).strip()[:1900]


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index:index + size] for index in range(0, len(items), size)]
