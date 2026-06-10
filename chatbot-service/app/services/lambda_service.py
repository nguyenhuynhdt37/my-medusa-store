from __future__ import annotations

from typing import Any


async def call_bot(
    *,
    user_id: str,
    message: str,
    page_id: str | None,
    lex_client: Any | None = None,
) -> dict[str, Any]:
    from app.api.chat_gateway import AIProcessRequest, process_ai_request
    from app.clients.gemini_client import get_gemini_client
    from app.clients.lex_runtime import LexRuntimeClient

    client = lex_client or LexRuntimeClient()
    gemini = get_gemini_client()
    request = AIProcessRequest(
        conversationId=f"messenger:{page_id or 'page'}:{user_id}",
        message=message,
        customer_context={
            "channel": "MESSENGER",
            "external_user_id": user_id,
            "page_id": page_id,
        },
        session_context={},
    )
    return await process_ai_request(request, authorization=None, lex_client=client, gemini_client=gemini)

