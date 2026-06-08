import requests
import json

URL = "http://localhost:8080/lexv2/webhook"

payload1 = {
    "sessionState": {
        "intent": {
            "name": "ProductPriceIntent",
            "slots": {
                "product_name": {"value": {"interpretedValue": "iPhone 17 Pro Max"}}
            }
        }
    },
    "inputTranscript": "giá iphone 17 pro max"
}

r1 = requests.post(URL, json=payload1)
body1 = r1.json()
print("R1:", body1["messages"][0]["content"] if "messages" in body1 else body1)

session_attrs = body1.get("sessionState", {}).get("sessionAttributes", {})
print("Session Attributes:", session_attrs)

payload2 = {
    "sessionState": {
        "sessionAttributes": session_attrs,
        "intent": {
            "name": "InventoryIntent",
            "slots": {}
        }
    },
    "inputTranscript": "còn hàng không?"
}

r2 = requests.post(URL, json=payload2)
body2 = r2.json()
print("R2:", body2["messages"][0]["content"] if "messages" in body2 else body2)
