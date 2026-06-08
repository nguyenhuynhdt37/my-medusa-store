import asyncio
from app.schemas.lexv2 import LexV2Request
from app.services.intent_service import IntentService
from app.clients.medusa_client import MedusaClient

async def main():
    payload2 = {
        "sessionState": {
            "sessionAttributes": {
                "current_product_name": "iPhone 17 Pro Max"
            },
            "intent": {
                "name": "InventoryIntent",
                "slots": {}
            }
        },
        "inputTranscript": "còn hàng không?"
    }

    req = LexV2Request.model_validate(payload2)
    df_req = req.to_dialogflow_request()
    
    medusa = MedusaClient(base_url="http://localhost:9000")
    service = IntentService(medusa)
    
    try:
        response = await service.inventory_status(df_req)
        print("SUCCESS:", response)
    except Exception as e:
        print("ERROR:", repr(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
