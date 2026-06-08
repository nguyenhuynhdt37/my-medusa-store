from fastapi import APIRouter, Depends, Header

from app.clients.gemini_client import GeminiClient, get_gemini_client
from app.clients.medusa_client import MedusaClient, get_medusa_client
from app.schemas.lexv2 import LexV2Request, LexV2Response
from app.services.intent_service import IntentService

router = APIRouter()


@router.post("/lexv2/webhook", response_model=LexV2Response)
async def lexv2_webhook(
    request: LexV2Request,
    authorization: str | None = Header(default=None),
    medusa_client: MedusaClient = Depends(get_medusa_client),
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> LexV2Response:
    service = IntentService(medusa_client, gemini_client=gemini_client)
    return await service.handle(
        request,
        authorization_header=authorization,
    )
