from time import perf_counter

from fastapi import APIRouter, Depends, Header

from app.clients.gemini_client import GeminiClient, get_gemini_client
from app.clients.medusa_client import MedusaClient, get_medusa_client
from app.core.config import settings
from app.schemas.lexv2 import LexV2Request, LexV2Response
from app.services.ai_usage_service import cost_context_from_request_attributes, record_lambda_usage
from app.services.intent_service import IntentService

router = APIRouter()


@router.post("/lexv2/webhook", response_model=LexV2Response)
async def lexv2_webhook(
    request: LexV2Request,
    authorization: str | None = Header(default=None),
    medusa_client: MedusaClient = Depends(get_medusa_client),
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> LexV2Response:
    started_at = perf_counter()
    response: LexV2Response | None = None
    cost_context = cost_context_from_request_attributes(
        request.request_attributes,
        fallback_session_id=request.session_id,
    )
    service = IntentService(medusa_client, gemini_client=gemini_client)
    try:
        response = await service.handle(
            request,
            authorization_header=authorization,
        )
        return response
    finally:
        duration_ms = (perf_counter() - started_at) * 1000
        intent = None
        if response and response.session_info:
            intent = response.session_info.parameters.get("resolved_intent")
        await record_lambda_usage(
            cost_context=cost_context,
            operation="lex_fulfillment_webhook",
            intent=intent,
            duration_ms=duration_ms,
            memory_mb=settings.lambda_memory_size_mb,
            request_count=1,
        )
