import asyncio
import json
import traceback
from app.core.config import settings
from app.services.intent_service import IntentService
from app.clients.medusa_client import get_medusa_client
from app.clients.gemini_client import get_gemini_client
from app.schemas.lexv2 import LexV2Request

async def main():
    try:
        medusa = get_medusa_client()
        gemini = get_gemini_client()
        service = IntentService(medusa_client=medusa, gemini_client=gemini)
        
        req = LexV2Request(
            sessionState={"intent": {"name": "FallbackIntent"}},
            inputTranscript="Iphone 7 giá sao",
            sessionId="test_123"
        )
        res = await service.handle(req)
        print("SUCCESS:")
        print(res.model_dump_json(indent=2))
    except Exception as e:
        print("ERROR:")
        traceback.print_exc()

asyncio.run(main())
