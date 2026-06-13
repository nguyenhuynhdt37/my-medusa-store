import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 8


def lambda_handler(event, context):
    webhook_url = get_webhook_url()
    if not webhook_url:
        return close_response(
            event,
            "Failed",
            "Lambda chưa cấu hình CHATBOT_LEXV2_WEBHOOK_URL hoặc CHATBOT_SERVICE_URL.",
        )

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "aws-lexv2-medusa-lambda/1.0",
    }
    authorization = extract_authorization(event)
    if authorization:
        headers["Authorization"] = authorization

    request = Request(
        webhook_url,
        data=json.dumps(event).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=get_timeout_seconds()) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"Chatbot webhook returned HTTP {exc.code}: {detail}")
        return close_response(
            event,
            "Failed",
            "Mình chưa thể kết nối hệ thống chatbot lúc này. Bạn vui lòng thử lại sau.",
        )
    except (OSError, URLError) as exc:
        print(f"Chatbot webhook request failed: {exc}")
        return close_response(
            event,
            "Failed",
            "Mình chưa thể kết nối hệ thống chatbot lúc này. Bạn vui lòng thử lại sau.",
        )

    try:
        lex_response = json.loads(body)
    except json.JSONDecodeError:
        print(f"Chatbot webhook returned invalid JSON: {body[:500]}")
        return close_response(
            event,
            "Failed",
            "Hệ thống chatbot trả về phản hồi không hợp lệ. Bạn vui lòng thử lại sau.",
        )

    if not is_valid_lex_response(lex_response):
        print(f"Chatbot webhook returned non-Lex response: {json.dumps(lex_response)[:500]}")
        return close_response(
            event,
            "Failed",
            "Hệ thống chatbot trả về phản hồi không đúng định dạng Lex.",
        )

    return lex_response


def get_webhook_url():
    explicit_url = os.environ.get("CHATBOT_LEXV2_WEBHOOK_URL")
    if explicit_url:
        return explicit_url.strip()

    service_url = os.environ.get("CHATBOT_SERVICE_URL")
    if not service_url:
        return None

    service_url = service_url.strip()
    if service_url.endswith("/lexv2/webhook"):
        return service_url
    if service_url.endswith("/webhook"):
        return service_url[: -len("/webhook")] + "/lexv2/webhook"

    return urljoin(service_url.rstrip("/") + "/", "lexv2/webhook")


def get_timeout_seconds():
    raw_timeout = os.environ.get("CHATBOT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        return max(1, float(raw_timeout))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def extract_authorization(event):
    request_attributes = event.get("requestAttributes") or {}
    session_state = event.get("sessionState") or {}
    session_attributes = session_state.get("sessionAttributes") or {}

    for attributes in (request_attributes, session_attributes):
        for key in (
            "Authorization",
            "authorization",
            "customer_access_token",
            "customerAccessToken",
            "access_token",
            "accessToken",
        ):
            value = attributes.get(key)
            if value:
                return format_bearer_token(str(value))

    return None


def format_bearer_token(token):
    token = token.strip()
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


def is_valid_lex_response(response):
    if not isinstance(response, dict):
        return False

    session_state = response.get("sessionState")
    if not isinstance(session_state, dict):
        return False

    dialog_action = session_state.get("dialogAction")
    intent = session_state.get("intent")
    return isinstance(dialog_action, dict) and isinstance(intent, dict)


def close_response(event, intent_state, message):
    session_state = event.get("sessionState") or {}
    intent = session_state.get("intent") or {}
    intent_name = intent.get("name") or "FallbackIntent"

    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {
                **intent,
                "name": intent_name,
                "state": intent_state,
            },
            "sessionAttributes": session_state.get("sessionAttributes") or {},
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": message,
            }
        ],
    }
