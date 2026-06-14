import pytest
from app.schemas.lexv2 import LexV2Request
from app.services.intent_service import IntentService


class ProductionFakeMedusaClient:
    def __init__(self):
        self.products = [
            {
                "id": "prod_iphone17pm",
                "title": "iPhone 17 Pro Max",
                "handle": "iphone-17-pro-max",
                "thumbnail": "https://example.com/iphone17pm.jpg",
                "material": "Titanium",
                "metadata": {
                    "warranty_months": 12,
                    "chip": "Apple A19 Pro",
                    "camera": "48MP main camera",
                    "battery": "pin trâu 4500mAh",
                    "charging": "sạc nhanh 45W",
                    "sold_count": 500,
                    "rating": 4.9,
                    "promo_hint": "Giảm ngay 1 triệu khi thanh toán qua Momo",
                },
                "variants": [
                    {
                        "title": "256GB / Titan Tự Nhiên",
                        "manage_inventory": True,
                        "calculated_price": {
                            "calculated_amount": 34990000,
                            "original_amount": 35990000,
                            "currency_code": "vnd",
                        }
                    }
                ],
            },
            {
                "id": "prod_samsungs26u",
                "title": "Samsung Galaxy S26 Ultra",
                "handle": "samsung-galaxy-s26-ultra",
                "thumbnail": "https://example.com/s26u.jpg",
                "material": "Armor Aluminum",
                "metadata": {
                    "warranty_months": 24,
                    "chip": "Snapdragon 8 Gen 5",
                    "camera": "200MP Zoom 100x",
                    "battery": "pin khủng 5000mAh",
                    "charging": "sạc nhanh 65W",
                    "sold_count": 420,
                    "rating": 4.8,
                    "promo_hint": "Tặng kèm sạc không dây 25W",
                },
                "variants": [
                    {
                        "title": "512GB / Titanium Black",
                        "manage_inventory": True,
                        "calculated_price": {
                            "calculated_amount": 31990000,
                            "original_amount": 31990000,
                            "currency_code": "vnd",
                        }
                    }
                ],
            }
        ]

    async def list_products(self, query=None, limit=50):
        if not query:
            return self.products[:limit]
        
        query_lower = query.lower()
        results = []
        for p in self.products:
            if (
                query_lower in p["title"].lower() 
                or query_lower in p["handle"].lower()
                or query_lower in (p["metadata"].get("chip") or "").lower()
            ):
                results.append(p)
        return results

    async def find_customer_order(self, order_code, customer_access_token):
        if customer_access_token != "prod-token":
            return None
        return {
            "id": order_code,
            "display_id": 1001,
            "fulfillment_status": "shipped",
            "payment_status": "captured",
            "status": "pending",
            "total": 34990000,
            "currency_code": "vnd",
            "created_at": "2026-06-13T10:00:00.000Z",
        }

    async def list_customer_orders(self, customer_access_token, limit=10):
        if customer_access_token != "prod-token":
            return []
        return [
            {
                "id": "ord_1001",
                "display_id": 1001,
                "fulfillment_status": "shipped",
                "payment_status": "captured",
                "status": "pending",
                "total": 34990000,
                "currency_code": "vnd",
            }
        ]


async def simulate_multi_turn(service: IntentService, turns: list[dict], token: str | None = None):
    """
    Hỗ trợ mô phỏng cuộc hội thoại đa lượt và lưu giữ context sessionAttributes qua các turn.
    """
    session_attributes = {}
    responses = []

    for turn in turns:
        intent = turn.get("intent", "FallbackIntent")
        slots = turn.get("slots", {})
        text = turn.get("text", "")
        
        # Merge slots vào sessionAttributes của lượt trước để mô phỏng Lex
        request_slots = {
            name: {"value": {"interpretedValue": val}}
            for name, val in slots.items()
        }
        
        event = LexV2Request(
            inputTranscript=text,
            sessionState={
                "intent": {
                    "name": intent,
                    "slots": request_slots
                },
                "sessionAttributes": session_attributes.copy()
            }
        )
        
        # Gọi service xử lý
        response = await service.handle(event, authorization_header=token)
        
        # Lưu lại session attributes cho turn tiếp theo
        session_attributes = response.sessionState.sessionAttributes.copy()
        responses.append(response)

    return responses


@pytest.mark.asyncio
async def test_scenario_product_research_and_compare():
    """
    KỊCH BẢN 1: Nghiên cứu sản phẩm và so sánh (Contextual Flow)
    """
    service = IntentService(ProductionFakeMedusaClient())
    
    turns = [
        # 1. Hỏi giá một máy cụ thể
        {
            "intent": "ProductPriceIntent",
            "slots": {"product_name": "iPhone 17 Pro Max"},
            "text": "iPhone 17 Pro Max giá bao nhiêu thế"
        },
        # 2. Hỏi tiếp về tồn kho (Dùng context sản phẩm cũ)
        {
            "intent": "InventoryIntent",
            "slots": {},
            "text": "bản này còn hàng không shop"
        },
        # 3. Hỏi tiếp về bảo hành (Dùng context sản phẩm cũ)
        {
            "intent": "WarrantyPolicyIntent",
            "slots": {},
            "text": "được bảo hành mấy tháng vậy"
        },
        # 4. So sánh với máy khác (Lấy máy cũ làm product_a, máy mới làm product_b)
        {
            "intent": "ProductCompareIntent",
            "slots": {"product_b": "Samsung Galaxy S26 Ultra"},
            "text": "so với Samsung Galaxy S26 Ultra thì sao"
        }
    ]
    
    responses = await simulate_multi_turn(service, turns)
    
    # Check Turn 1: Báo giá đúng iPhone 17 Pro Max
    msg1 = responses[0].fulfillment_response.messages[0].text.text[0]
    assert "iPhone 17 Pro Max" in msg1
    assert "34.990.000 VNĐ" in msg1
    assert responses[0].session_info.parameters["current_product_name"] == "iPhone 17 Pro Max"

    # Check Turn 2: Kiểm tra tồn kho iPhone 17 Pro Max kế thừa từ context
    msg2 = responses[1].fulfillment_response.messages[0].text.text[0]
    assert "iPhone 17 Pro Max" in msg2
    assert "có hàng" in msg2
    assert responses[1].session_info.parameters["inventory_status"] == "in_stock"

    # Check Turn 3: Kiểm tra chính sách bảo hành kế thừa từ context
    msg3 = responses[2].fulfillment_response.messages[0].text.text[0]
    assert "iPhone 17 Pro Max" in msg3
    assert "bảo hành 12 tháng" in msg3

    # Check Turn 4: So sánh iPhone 17 Pro Max và Samsung Galaxy S26 Ultra
    msg4 = responses[3].fulfillment_response.messages[0].text.text[0]
    assert "So sánh" in msg4
    assert "iPhone 17 Pro Max" in msg4
    assert "Samsung Galaxy S26 Ultra" in msg4
    assert responses[3].session_info.parameters["product_a_name"] == "iPhone 17 Pro Max"
    assert responses[3].session_info.parameters["product_b_name"] == "Samsung Galaxy S26 Ultra"


@pytest.mark.asyncio
async def test_scenario_order_lifecycle():
    """
    KỊCH BẢN 2: Tra cứu đơn hàng (Đăng nhập, xem trạng thái, xem chi tiết, và yêu cầu hỗ trợ)
    """
    service = IntentService(ProductionFakeMedusaClient())
    
    # Turn 1: Hỏi đơn hàng không đăng nhập
    turns_no_auth = [
        {
            "intent": "OrderStatusIntent",
            "slots": {},
            "text": "tôi có đơn hàng nào không"
        }
    ]
    res_no_auth = await simulate_multi_turn(service, turns_no_auth, token=None)
    msg_no_auth = res_no_auth[0].fulfillment_response.messages[0].text.text[0]
    assert "đăng nhập" in msg_no_auth
    assert res_no_auth[0].session_info.parameters["search_status"] == "authentication_required"

    # Turn 2: Đăng nhập thành công và tra cứu
    turns_auth = [
        # 1. Hỏi đơn hàng khi đã có Token
        {
            "intent": "OrderStatusIntent",
            "slots": {},
            "text": "tôi có đơn hàng nào không"
        },
        # 2. Xem chi tiết đơn hàng (Sử dụng ID đơn hàng vừa lấy được từ context)
        {
            "intent": "OrderDetailIntent",
            "slots": {},
            "text": "cho mình xem chi tiết đơn hàng này"
        },
        # 3. Yêu cầu hủy đơn hàng (aftercare handoff)
        {
            "intent": "OrderCancelIntent",
            "slots": {},
            "text": "mình muốn huỷ đơn"
        }
    ]
    
    responses = await simulate_multi_turn(service, turns_auth, token="prod-token")
    
    # Check Turn 2.1: Hiển thị đơn hàng ORD-1001 đang giao
    msg_list = responses[0].fulfillment_response.messages[0].text.text[0]
    assert "ORD-1001" in msg_list
    assert "đang được giao" in msg_list
    
    # Check Turn 2.2: Xem chi tiết đơn hàng ORD-1001 (context current_order_code được kế thừa)
    msg_detail = responses[1].fulfillment_response.messages[0].text.text[0]
    assert "Thông tin ORD-1001" in msg_detail
    assert "34.990.000 VNĐ" in msg_detail
    
    # Check Turn 2.3: Chuyển nhân viên hủy đơn (sau bán hàng)
    msg_cancel = responses[2].fulfillment_response.messages[0].text.text[0]
    assert "chuyển nhân viên" in msg_cancel
    assert "huỷ đơn" in msg_cancel
    assert responses[2].session_info.parameters["handover_requested"] is True


@pytest.mark.asyncio
async def test_scenario_promotion_and_shopping():
    """
    KỊCH BẢN 3: Khuyến mãi & Luồng giỏ hàng (Promotion and Shopping Flow)
    """
    service = IntentService(ProductionFakeMedusaClient())
    
    turns = [
        # 1. Hỏi khuyến mãi chung
        {
            "intent": "PromotionIntent",
            "slots": {},
            "text": "shop có chương trình khuyến mãi gì mới không ạ"
        },
        # 2. Hỏi cụ thể một mã giảm giá
        {
            "intent": "PromotionIntent",
            "slots": {"promo_code": "ANDROID15"},
            "text": "mã ANDROID15 dùng thế nào thế"
        },
        # 3. Thêm sản phẩm vào giỏ hàng
        {
            "intent": "CartAddItemIntent",
            "slots": {"product_name": "Samsung Galaxy S26 Ultra"},
            "text": "thêm Samsung Galaxy S26 Ultra vào giỏ hàng giúp mình"
        },
        # 4. Yêu cầu thanh toán
        {
            "intent": "CheckoutStartIntent",
            "slots": {},
            "text": "mình muốn thanh toán luôn"
        }
    ]
    
    responses = await simulate_multi_turn(service, turns)
    
    # Check Turn 1: Hiển thị các mã có sẵn
    msg1 = responses[0].fulfillment_response.messages[0].text.text[0]
    assert "WELCOME10" in msg1
    assert "FREESHIP" in msg1
    assert responses[0].session_info.parameters["search_status"] == "promotion_codes_available"
    
    # Check Turn 2: Thông tin mã ANDROID15
    msg2 = responses[1].fulfillment_response.messages[0].text.text[0]
    assert "ANDROID15" in msg2
    assert responses[1].session_info.parameters["promotion_code"] == "ANDROID15"
    assert responses[1].session_info.parameters["promotion_status"] == "available"
    
    # Check Turn 3: Hướng dẫn giỏ hàng
    msg3 = responses[2].fulfillment_response.messages[0].text.text[0]
    assert "Samsung Galaxy S26 Ultra" in msg3
    assert "thêm vào giỏ" in msg3
    assert responses[2].session_info.parameters["search_status"] == "cart_checkout_guidance"
    
    # Check Turn 4: Hướng dẫn thanh toán
    msg4 = responses[3].fulfillment_response.messages[0].text.text[0]
    assert "thanh toán" in msg4
    assert "checkout" in msg4.lower() or "giỏ" in msg4


@pytest.mark.asyncio
async def test_scenario_delivery_and_store_info():
    """
    KỊCH BẢN 4: Chính sách giao hàng & Thông tin shop (Delivery and Store Info)
    """
    service = IntentService(ProductionFakeMedusaClient())
    
    turns = [
        # 1. Hỏi về phí ship và thời gian giao hàng
        {
            "intent": "ShippingPolicyIntent",
            "slots": {},
            "text": "shop giao hàng mất bao lâu thế, phí ship thế nào"
        },
        # 2. Hỏi thông tin cửa hàng
        {
            "intent": "StoreInfoIntent",
            "slots": {},
            "text": "cửa hàng mình ở đâu vậy shop"
        }
    ]
    
    responses = await simulate_multi_turn(service, turns)
    
    # Check Turn 1: Trả về chính sách vận chuyển demo
    msg1 = responses[0].fulfillment_response.messages[0].text.text[0]
    assert "Giao hàng tiêu chuẩn" in msg1
    assert "50.000 VNĐ" in msg1
    assert responses[0].session_info.parameters["search_status"] == "shipping_policy"
    
    # Check Turn 2: Trả về thông tin cửa hàng và website
    msg2 = responses[1].fulfillment_response.messages[0].text.text[0]
    assert "Thông tin cửa hàng" in msg2
    assert responses[1].session_info.parameters["search_status"] == "store_info"


@pytest.mark.asyncio
async def test_scenario_smalltalk_and_fallback():
    """
    KỊCH BẢN 5: Smalltalk & Fallback ngoại phạm vi (Smalltalk and Fallback Flow)
    """
    service = IntentService(ProductionFakeMedusaClient())
    
    turns = [
        # 1. Chào hỏi shop
        {
            "intent": "GreetingIntent",
            "slots": {},
            "text": "xin chào shop nhé"
        },
        # 2. Khen ngợi bot (compliment)
        {
            "intent": "FallbackIntent",
            "slots": {},
            "text": "bạn giỏi và dễ thương quá"
        },
        # 3. Hỏi câu hỏi không liên quan đến điện thoại (off-topic fallback)
        {
            "intent": "FallbackIntent",
            "slots": {},
            "text": "nấu phở bò ăn ngon cần nguyên liệu gì thế"
        }
    ]
    
    responses = await simulate_multi_turn(service, turns)
    
    # Check Turn 1: Chào hỏi thành công
    msg1 = responses[0].fulfillment_response.messages[0].text.text[0]
    assert "chào" in msg1.lower() or "hi" in msg1.lower() or "medusan" in msg1.lower()
    
    # Check Turn 2: Nhận diện compliment thành công
    msg2 = responses[1].fulfillment_response.messages[0].text.text[0]
    assert "Cảm ơn" in msg2
    assert responses[1].session_info.parameters["search_status"] == "smalltalk_compliment"
    assert responses[1].session_info.parameters["resolved_intent"] == "smalltalk_compliment"
    
    # Check Turn 3: Rơi vào fallback do off-topic
    msg3 = responses[2].fulfillment_response.messages[0].text.text[0]
    assert "chưa hiểu" in msg3
    assert responses[2].session_info.parameters["search_status"] == "fallback"


@pytest.mark.asyncio
async def test_scenario_specs_and_advice():
    """
    KỊCH BẢN 6: Hỏi thông số cấu hình điện thoại cụ thể (Specs and advice Flow)
    """
    service = IntentService(ProductionFakeMedusaClient())
    
    turns = [
        # 1. Hỏi thông số cấu hình iPhone 17 Pro Max
        {
            "intent": "ProductSpecIntent",
            "slots": {"product_name": "iPhone 17 Pro Max"},
            "text": "iPhone 17 Pro Max cấu hình thế nào vậy shop"
        },
        # 2. Hỏi tiếp về pin (kế thừa context sản phẩm cũ)
        {
            "intent": "ProductBatteryIntent",
            "slots": {},
            "text": "pin dùng được lâu không bạn"
        },
        # 3. Hỏi tiếp về camera (kế thừa context sản phẩm cũ)
        {
            "intent": "ProductCameraIntent",
            "slots": {},
            "text": "camera chụp hình đẹp không"
        },
        # 4. Hỏi tiếp về khả năng chơi game (kế thừa context sản phẩm cũ)
        {
            "intent": "ProductGamingIntent",
            "slots": {},
            "text": "máy này chơi game tốt không"
        }
    ]
    
    responses = await simulate_multi_turn(service, turns)
    
    # Cả 4 turn đều kế thừa đúng sản phẩm và trả dữ liệu kỹ thuật theo intent.
    for turn_res in responses:
        msg = turn_res.fulfillment_response.messages[0].text.text[0]
        assert "iPhone 17 Pro Max" in msg
        assert turn_res.session_info.parameters["current_product_name"] == "iPhone 17 Pro Max"

    assert "Apple A19 Pro" in responses[0].fulfillment_response.messages[0].text.text[0]
    assert "4500mAh" in responses[1].fulfillment_response.messages[0].text.text[0]
    assert "48MP main camera" in responses[2].fulfillment_response.messages[0].text.text[0]
    assert "Apple A19 Pro" in responses[3].fulfillment_response.messages[0].text.text[0]
        
    assert responses[0].session_info.parameters["search_status"] == "product_spec"
    assert responses[1].session_info.parameters["search_status"] == "product_battery"
    assert responses[2].session_info.parameters["search_status"] == "product_camera"
    assert responses[3].session_info.parameters["search_status"] == "product_gaming"
