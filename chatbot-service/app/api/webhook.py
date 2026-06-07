from fastapi import APIRouter, Depends, Header

from app.clients.gemini_client import GeminiClient, get_gemini_client
from app.clients.medusa_client import MedusaClient, get_medusa_client
from app.schemas.dialogflow import DialogflowCXRequest, DialogflowCXResponse
from app.schemas.lexv2 import LexV2Request, dialogflow_response_to_lexv2
from app.services.intent_service import IntentService

router = APIRouter()


@router.post(
    "/webhook",
    response_model=DialogflowCXResponse,
    response_model_exclude_none=True,
)
async def dialogflow_webhook(
    request: DialogflowCXRequest,
    authorization: str | None = Header(default=None),
    medusa_client: MedusaClient = Depends(get_medusa_client),
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> DialogflowCXResponse:
    service = IntentService(medusa_client, gemini_client=gemini_client)
    return await service.handle(request, authorization_header=authorization)


@router.post("/lexv2/webhook")
async def lexv2_webhook(
    request: LexV2Request,
    authorization: str | None = Header(default=None),
    medusa_client: MedusaClient = Depends(get_medusa_client),
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> dict:
    service = IntentService(medusa_client, gemini_client=gemini_client)
    response = await service.handle(
        request.to_dialogflow_request(),
        authorization_header=authorization,
    )
    return dialogflow_response_to_lexv2(request, response)
