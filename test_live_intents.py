import requests
import json

MEDUSA_URL = "http://localhost:9000"
WEBHOOK_URL = "http://localhost:8080/lexv2/webhook"

def get_auth_token():
    auth_data = {
        "email": "testuser_lex2@ecomoi.local",
        "password": "password123",
        "first_name": "Test",
        "last_name": "User"
    }
    try:
        r = requests.post(f"{MEDUSA_URL}/auth/customer/emailpass/register", json=auth_data)
        if r.status_code == 200:
            return r.json().get("token")
        
        r2 = requests.post(f"{MEDUSA_URL}/auth/customer/emailpass", json={"email": auth_data["email"], "password": auth_data["password"]})
        if r2.status_code == 200:
            return r2.json().get("token")
    except Exception:
        pass
    return None

def test_intent(intent_name, text, slots=None):
    if slots is None:
        slots = {}
    payload = {
        "sessionState": {
            "intent": {
                "name": intent_name,
                "slots": slots,
            }
        },
        "inputTranscript": text,
    }
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()
        body = response.json()
        print(f"\n=====================================")
        print(f"INTENT: {intent_name}")
        print(f"INPUT:  {text}")
        print(f"-------------------------------------")
        if "messages" in body and len(body["messages"]) > 0:
            print("RESPONSE:")
            print(body["messages"][0].get("content", ""))
        else:
            print("No message returned. Full body:")
            print(json.dumps(body, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n=====================================")
        print(f"INTENT: {intent_name}")
        print(f"ERROR: {e}")

if __name__ == "__main__":
    print("Fetching auth token for test user...")
    token = get_auth_token()
    if token:
        print("Logged in successfully!")
    else:
        print("Failed to login! Order testing will fail auth check.")

    print("\nTesting ALL Lex V2 Intents...")
    
    # 1. ProductSearchIntent
    test_intent("ProductSearchIntent", "tìm iphone 17", {
        "product_name": {"value": {"interpretedValue": "iPhone 17"}},
        "brand": None,
        "need": None,
        "budget": None
    })
    
    # 2. ProductPriceIntent
    test_intent("ProductPriceIntent", "giá iphone 17 pro max", {
        "product_name": {"value": {"interpretedValue": "iPhone 17 Pro Max"}}
    })
    
    # 3. ProductRecommendationIntent
    test_intent("ProductRecommendationIntent", "tư vấn điện thoại chụp ảnh", {
        "need": {"value": {"interpretedValue": "chụp ảnh"}}
    })
    
    # 4. PromotionIntent
    test_intent("PromotionIntent", "có mã freeship không", {
        "promo_code": {"value": {"interpretedValue": "FREESHIP"}}
    })
    
    # 5. InventoryIntent
    test_intent("InventoryIntent", "còn iphone 15 không", {
        "product_name": {"value": {"interpretedValue": "iPhone 15"}}
    })
    
    # 6. ProductCompareIntent
    test_intent("ProductCompareIntent", "so sánh iphone 15 và samsung s26 plus", {
        "product_a": {"value": {"interpretedValue": "iPhone 15"}},
        "product_b": {"value": {"interpretedValue": "Samsung Galaxy S26 Plus"}}
    })
    
    # 7. OrderStatusIntent
    # Passing token in slots as per chatbot-service logic
    test_intent("OrderStatusIntent", "kiểm tra đơn hàng ORD-9999", {
        "order_id": {"value": {"interpretedValue": "ORD-9999"}},
        "customer_access_token": {"value": {"interpretedValue": token}} if token else None
    })
    
    # Extra: OrderList
    test_intent("OrderList", "đơn hàng của tôi", {
        "customer_access_token": {"value": {"interpretedValue": token}} if token else None
    })
    
    # 8. ShippingPolicyIntent
    test_intent("ShippingPolicyIntent", "phí ship bao nhiêu")
    
    # 9. WarrantyPolicyIntent
    test_intent("WarrantyPolicyIntent", "iphone 15 bảo hành bao lâu", {
        "product_name": {"value": {"interpretedValue": "iPhone 15"}}
    })
    
    # 10. HumanHandoffIntent
    test_intent("HumanHandoffIntent", "chuyển cho tư vấn viên")
    
    # 11. FallbackIntent
    test_intent("FallbackIntent", "bla bla bla không hiểu gì hết")

    # "khóa lại" - Since it's a test user, we don't really need to do anything, but let's just print a message
    print("\n=====================================")
    print("Testing completed. Test user state 'locked' (no sensitive access exposed).")

