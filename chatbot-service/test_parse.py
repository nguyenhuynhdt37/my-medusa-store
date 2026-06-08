from app.schemas.lexv2 import LexV2Request
import json

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
print("LexV2Request session_state:", req.session_state)
df_req = req.to_dialogflow_request()
print("DialogflowCXRequest session_info:", df_req.session_info)
print("get_parameter current_product_name:", df_req.get_parameter(["current_product_name"]))
