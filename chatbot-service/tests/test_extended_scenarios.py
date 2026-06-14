import pytest
from app.schemas.lexv2 import LexV2Request
from app.services.intent_service import IntentService


class ExtendedFakeMedusaClient:
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
            },
            {
                "id": "prod_iphone16",
                "title": "iPhone 16",
                "handle": "iphone-16",
                "thumbnail": "https://example.com/iphone16.jpg",
                "material": "Aluminum",
                "metadata": {
                    "warranty_months": 12,
                    "chip": "Apple A18",
                    "camera": "48MP Dual Camera",
                    "battery": "pin trung bình 3561mAh",
                    "charging": "sạc nhanh 25W",
                    "sold_count": 1500,
                    "rating": 4.6,
                    "promo_hint": "Giảm 500k khi mua kèm phụ kiện",
                },
                "variants": [
                    {
                        "title": "128GB / Black",
                        "manage_inventory": True,
                        "calculated_price": {
                            "calculated_amount": 21990000,
                            "original_amount": 22990000,
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
        if customer_access_token != "extended-token":
            return None
        
        # Hỗ trợ tìm kiếm theo cả ORD-1001, ord1001, 1001
        clean_code = str(order_code).lower().replace("ord-", "").replace("ord", "").strip()
        if clean_code in ("1001", "ord_1001"):
            return {
                "id": "ord_1001",
                "display_id": 1001,
                "fulfillment_status": "shipped",
                "payment_status": "captured",
                "status": "pending",
                "total": 34990000,
                "currency_code": "vnd",
                "created_at": "2026-06-13T10:00:00.000Z",
            }
        elif clean_code in ("1002", "ord_1002"):
            return {
                "id": "ord_1002",
                "display_id": 1002,
                "fulfillment_status": "fulfilled",
                "payment_status": "refunded",
                "status": "completed",
                "total": 21990000,
                "currency_code": "vnd",
                "created_at": "2026-06-10T08:00:00.000Z",
            }
        return None

    async def list_customer_orders(self, customer_access_token, limit=10):
        if customer_access_token != "extended-token":
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
            },
            {
                "id": "ord_1002",
                "display_id": 1002,
                "fulfillment_status": "fulfilled",
                "payment_status": "refunded",
                "status": "completed",
                "total": 21990000,
                "currency_code": "vnd",
            }
        ]


async def simulate_multi_turn_extended(service: IntentService, turns: list[dict], token: str | None = None):
    session_attributes = {}
    responses = []

    for turn in turns:
        intent = turn.get("intent", "FallbackIntent")
        slots = turn.get("slots", {})
        text = turn.get("text", "")
        
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
        
        response = await service.handle(event, authorization_header=token)
        session_attributes = response.sessionState.sessionAttributes.copy()
        responses.append(response)

    return responses


@pytest.mark.asyncio
async def test_abbreviations_and_specs():
    """
    TEST SET 1: Viết tắt sản phẩm và tra cứu cấu hình chi tiết (ip17pm, s26u, ip16)
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    # Kịch bản 1: Viết tắt ip17pm
    turns_ip = [
        {
            "intent": "ProductPriceIntent",
            "slots": {"product_name": "ip17pm"},
            "text": "ip17pm bao nhiêu tiền"
        },
        {
            "intent": "ProductSpecIntent",
            "slots": {},
            "text": "cấu hình em nó thế nào shop"
        }
    ]
    res_ip = await simulate_multi_turn_extended(service, turns_ip)
    assert "iPhone 17 Pro Max" in res_ip[0].fulfillment_response.messages[0].text.text[0]
    assert "34.990.000 VNĐ" in res_ip[0].fulfillment_response.messages[0].text.text[0]
    assert "iPhone 17 Pro Max" in res_ip[1].fulfillment_response.messages[0].text.text[0]
    assert "Apple A19 Pro" in res_ip[1].fulfillment_response.messages[0].text.text[0]

    # Kịch bản 2: Viết tắt s26u
    turns_s26 = [
        {
            "intent": "ProductPriceIntent",
            "slots": {"product_name": "s26u"},
            "text": "giá con s26u"
        },
        {
            "intent": "ProductCameraIntent",
            "slots": {},
            "text": "camera chụp hình ổn không bạn"
        }
    ]
    res_s26 = await simulate_multi_turn_extended(service, turns_s26)
    assert "Samsung Galaxy S26 Ultra" in res_s26[0].fulfillment_response.messages[0].text.text[0]
    assert "31.990.000 VNĐ" in res_s26[0].fulfillment_response.messages[0].text.text[0]
    assert "Samsung Galaxy S26 Ultra" in res_s26[1].fulfillment_response.messages[0].text.text[0]
    assert "200MP Zoom 100x" in res_s26[1].fulfillment_response.messages[0].text.text[0]


@pytest.mark.asyncio
async def test_cart_operations():
    """
    TEST SET 2: Các thao tác giỏ hàng (thêm, cập nhật, xem giỏ, thanh toán)
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    turns = [
        # Thêm sản phẩm vào giỏ hàng
        {
            "intent": "CartAddItemIntent",
            "slots": {"product_name": "iPhone 16"},
            "text": "bỏ iPhone 16 vào giỏ hàng giùm"
        },
        # Xem giỏ hàng
        {
            "intent": "CartViewIntent",
            "slots": {},
            "text": "giỏ hàng mình có gì rồi"
        },
        # Cập nhật số lượng
        {
            "intent": "CartUpdateIntent",
            "slots": {},
            "text": "xóa bớt sản phẩm khỏi giỏ hàng đi"
        },
        # Tiến hành thanh toán
        {
            "intent": "CheckoutStartIntent",
            "slots": {},
            "text": "mình muốn thanh toán"
        }
    ]
    
    res = await simulate_multi_turn_extended(service, turns)
    assert "iPhone 16" in res[0].fulfillment_response.messages[0].text.text[0]
    assert "thêm vào giỏ" in res[0].fulfillment_response.messages[0].text.text[0]
    assert "giỏ hàng" in res[1].fulfillment_response.messages[0].text.text[0]
    assert "cập nhật" in res[2].fulfillment_response.messages[0].text.text[0] or "giỏ hàng" in res[2].fulfillment_response.messages[0].text.text[0]
    assert "thanh toán" in res[3].fulfillment_response.messages[0].text.text[0]


@pytest.mark.asyncio
async def test_payment_and_installment():
    """
    TEST SET 3: Phương thức thanh toán & Trả góp
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    # 1. Hỏi các phương thức thanh toán
    turns_payment = [
        {
            "intent": "PaymentMethodIntent",
            "slots": {},
            "text": "shop nhận thanh toán qua những cổng nào"
        }
    ]
    res_pay = await simulate_multi_turn_extended(service, turns_payment)
    msg_pay = res_pay[0].fulfillment_response.messages[0].text.text[0].lower()
    assert "chuyển khoản" in msg_pay or "momo" in msg_pay or "cod" in msg_pay

    # 2. Hỏi chính sách trả góp
    turns_installment = [
        {
            "intent": "InstallmentIntent",
            "slots": {},
            "text": "mua điện thoại bên mình có được trả góp 0% không"
        }
    ]
    res_inst = await simulate_multi_turn_extended(service, turns_installment)
    msg_inst = res_inst[0].fulfillment_response.messages[0].text.text[0].lower()
    assert "trả góp" in msg_inst
    assert "0%" in msg_inst or "thẻ tín dụng" in msg_inst


@pytest.mark.asyncio
async def test_shipping_and_warranty():
    """
    TEST SET 4: Chính sách vận chuyển, bảo hành & Đổi trả lỗi
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    turns = [
        # Hỏi bảo hành
        {
            "intent": "WarrantyPolicyIntent",
            "slots": {},
            "text": "chế độ bảo hành máy lỗi thế nào"
        },
        # Yêu cầu bảo hành (Warranty claim)
        {
            "intent": "WarrantyClaimIntent",
            "slots": {},
            "text": "máy mình tự dưng sập nguồn cần gửi bảo hành"
        },
        # Hỏi chính sách vận chuyển/ship hàng
        {
            "intent": "ShippingPolicyIntent",
            "slots": {},
            "text": "phí giao hàng nội thành bao nhiêu shop"
        }
    ]
    
    res = await simulate_multi_turn_extended(service, turns)
    assert "bảo hành" in res[0].fulfillment_response.messages[0].text.text[0].lower()
    assert "bảo hành" in res[1].fulfillment_response.messages[0].text.text[0].lower()
    assert "ship" in res[2].fulfillment_response.messages[0].text.text[0].lower() or "giao hàng" in res[2].fulfillment_response.messages[0].text.text[0].lower()


@pytest.mark.asyncio
async def test_order_actions_and_refunds():
    """
    TEST SET 5: Xem đơn hàng, tra cứu chi tiết, thay đổi thông tin nhận, hủy đơn & hoàn tiền
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    turns = [
        # 1. Liệt kê đơn hàng
        {
            "intent": "OrderListIntent",
            "slots": {},
            "text": "cho xem lịch sử mua hàng của tôi"
        },
        # 2. Xem chi tiết ORD-1002 (đơn đã hoàn tiền)
        {
            "intent": "OrderDetailIntent",
            "slots": {"order_code": "ORD-1002"},
            "text": "chi tiết đơn ORD-1002"
        },
        # 3. Hỏi về tình trạng hoàn tiền
        {
            "intent": "RefundStatusIntent",
            "slots": {},
            "text": "bao lâu thì nhận được tiền hoàn vậy"
        },
        # 4. Sửa thông tin địa chỉ đơn hàng (Order Modify)
        {
            "intent": "OrderModifyIntent",
            "slots": {},
            "text": "mình muốn đổi địa chỉ giao hàng của đơn ORD-1001"
        }
    ]
    
    res = await simulate_multi_turn_extended(service, turns, token="extended-token")
    
    # Liệt kê
    assert "ORD-1001" in res[0].fulfillment_response.messages[0].text.text[0]
    assert "ORD-1002" in res[0].fulfillment_response.messages[0].text.text[0]
    
    # Chi tiết
    assert "ORD-1002" in res[1].fulfillment_response.messages[0].text.text[0]
    assert "refunded" in res[1].fulfillment_response.messages[0].text.text[0].lower() or "hoàn tiền" in res[1].fulfillment_response.messages[0].text.text[0].lower() or "21.990.000" in res[1].fulfillment_response.messages[0].text.text[0]
    
    # Hoàn tiền
    assert "hoàn tiền" in res[2].fulfillment_response.messages[0].text.text[0].lower()
    
    # Sửa đổi đơn
    assert "địa chỉ" in res[3].fulfillment_response.messages[0].text.text[0] or "chuyển nhân viên" in res[3].fulfillment_response.messages[0].text.text[0]


@pytest.mark.asyncio
async def test_smalltalk_negations_and_offtopic():
    """
    TEST SET 6: Smalltalk, Negation, và Fallback
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    # Kịch bản 1: Khen ngợi -> Chào -> Câu hỏi lạc đề
    turns1 = [
        {
            "intent": "GreetingIntent",
            "slots": {},
            "text": "alo shop ơi"
        },
        {
            "intent": "FallbackIntent",
            "slots": {},
            "text": "bot trả lời thông minh quá đi"
        },
        {
            "intent": "FallbackIntent",
            "slots": {},
            "text": "nấu lẩu thái hải sản cần mua rau gì ngon"
        }
    ]
    res1 = await simulate_multi_turn_extended(service, turns1)
    assert "chào" in res1[0].fulfillment_response.messages[0].text.text[0].lower() or "hi" in res1[0].fulfillment_response.messages[0].text.text[0].lower() or "giúp" in res1[0].fulfillment_response.messages[0].text.text[0].lower()
    assert "cảm ơn" in res1[1].fulfillment_response.messages[0].text.text[0].lower() or "dễ thương" in res1[1].fulfillment_response.messages[0].text.text[0].lower()
    assert "chưa hiểu" in res1[2].fulfillment_response.messages[0].text.text[0].lower() or "sản phẩm" in res1[2].fulfillment_response.messages[0].text.text[0].lower()

    # Kịch bản 2: Negation
    turns2 = [
        {
            "intent": "FallbackIntent",
            "slots": {},
            "text": "không cần đâu shop ơi"
        }
    ]
    res2 = await simulate_multi_turn_extended(service, turns2)
    assert "cần" in res2[0].fulfillment_response.messages[0].text.text[0].lower() or "giúp" in res2[0].fulfillment_response.messages[0].text.text[0].lower()


@pytest.mark.asyncio
async def test_explicit_human_handoff():
    """
    TEST SET 7: Yêu cầu gặp nhân viên hỗ trợ (Human Handover)
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    turns = [
        {
            "intent": "HumanHandoverIntent",
            "slots": {},
            "text": "cho mình nói chuyện trực tiếp với nhân viên đi"
        }
    ]
    res = await simulate_multi_turn_extended(service, turns)
    msg = res[0].fulfillment_response.messages[0].text.text[0].lower()
    assert "chuyển" in msg and "nhân viên" in msg
    assert res[0].session_info.parameters.get("handover_requested") is True


@pytest.mark.asyncio
async def test_comparison_and_recommendation():
    """
    TEST SET 8: So sánh sản phẩm & Tư vấn gợi ý (Product Compare, Product Recommendation)
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    # 1. So sánh hai sản phẩm trực tiếp từ câu hỏi
    turns_compare = [
        {
            "intent": "ProductCompareIntent",
            "slots": {"product_a": "iPhone 17 Pro Max", "product_b": "Samsung Galaxy S26 Ultra"},
            "text": "so sánh iPhone 17 Pro Max và Samsung Galaxy S26 Ultra"
        }
    ]
    res_comp = await simulate_multi_turn_extended(service, turns_compare)
    msg_comp = res_comp[0].fulfillment_response.messages[0].text.text[0]
    assert "So sánh" in msg_comp
    assert "iPhone 17 Pro Max" in msg_comp
    assert "Samsung Galaxy S26 Ultra" in msg_comp

    # 2. Yêu cầu tư vấn giới thiệu sản phẩm
    turns_recommend = [
        {
            "intent": "ProductRecommendationIntent",
            "slots": {},
            "text": "tư vấn cho mình chiếc điện thoại nào pin trâu chơi game mượt với"
        }
    ]
    res_rec = await simulate_multi_turn_extended(service, turns_recommend)
    msg_rec = res_rec[0].fulfillment_response.messages[0].text.text[0]
    assert "gợi ý" in msg_rec.lower() or "tư vấn" in msg_rec.lower() or "sản phẩm" in msg_rec.lower()


@pytest.mark.asyncio
async def test_installment_and_payment_details():
    """
    TEST SET 9: Trả góp qua ngân hàng, kỳ hạn thẻ tín dụng và thủ tục trả góp
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    turns = [
        # 1. Hỏi về trả góp thẻ tín dụng Sacombank
        {
            "intent": "InstallmentIntent",
            "slots": {},
            "text": "mình muốn trả góp qua thẻ tín dụng Sacombank có được không"
        },
        # 2. Hỏi thủ tục có cần CMND không
        {
            "intent": "InstallmentIntent",
            "slots": {},
            "text": "thủ tục có cần cmnd hay hộ khẩu gì không shop"
        }
    ]
    
    responses = await simulate_multi_turn_extended(service, turns)
    
    # Check turn 1
    msg1 = responses[0].fulfillment_response.messages[0].text.text[0].lower()
    assert "trả góp" in msg1 or "thẻ tín dụng" in msg1
    assert responses[0].session_info.parameters["search_status"] == "payment_installment_policy"

    # Check turn 2
    msg2 = responses[1].fulfillment_response.messages[0].text.text[0].lower()
    assert "trả góp" in msg2 or "nhân viên" in msg2


@pytest.mark.asyncio
async def test_order_modify_delivery_delay():
    """
    TEST SET 10: Sửa thông tin giao hàng khi đi công tác & Khiếu nại giao hàng trễ (Handoff)
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    turns = [
        # 1. Khách đi công tác muốn đổi địa chỉ giao hàng của ORD-1001
        {
            "intent": "OrderModifyIntent",
            "slots": {"order_code": "ORD-1001"},
            "text": "mình đi công tác đột xuất nên muốn đổi địa chỉ giao hàng đơn ORD-1001"
        },
        # 2. Khiếu nại đơn giao quá trễ
        {
            "intent": "ComplaintIntent",
            "slots": {},
            "text": "đơn này trễ 3 ngày rồi shop làm ăn chán quá, tôi không hài lòng chút nào"
        }
    ]
    
    responses = await simulate_multi_turn_extended(service, turns, token="extended-token")
    
    # Check turn 1: Phải đi vào luồng sửa đổi đơn hàng (sau bán hàng)
    msg1 = responses[0].fulfillment_response.messages[0].text.text[0].lower()
    assert "sửa thông tin" in msg1 or "nhân viên" in msg1
    assert responses[0].session_info.parameters["handover_requested"] is True
    assert responses[0].session_info.parameters["search_status"] == "aftercare_handoff"

    # Check turn 2: Nhận diện khiếu nại (complaint) và handoff chuyển nhân viên tiếp
    msg2 = responses[1].fulfillment_response.messages[0].text.text[0].lower()
    assert "khiếu nại" in msg2 or "nhân viên" in msg2
    assert responses[1].session_info.parameters["handover_requested"] is True


@pytest.mark.asyncio
async def test_multi_product_context_comparison():
    """
    TEST SET 11: So sánh sản phẩm đa lượt liên tiếp để kiểm tra kế thừa context
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    turns = [
        # 1. So sánh iPhone 16 và Samsung Galaxy S26 Ultra
        {
            "intent": "ProductCompareIntent",
            "slots": {"product_a": "iPhone 16", "product_b": "Samsung Galaxy S26 Ultra"},
            "text": "so sánh iPhone 16 và Samsung Galaxy S26 Ultra giúp mình"
        },
        # 2. So sánh tiếp: "Thế còn iPhone 17 Pro Max so với Samsung thì sao?"
        # Ở đây product_a mới là iPhone 17 Pro Max, còn product_b phải kế thừa Samsung Galaxy S26 Ultra từ lượt trước
        {
            "intent": "ProductCompareIntent",
            "slots": {"product_a": "iPhone 17 Pro Max"},
            "text": "Thế còn iPhone 17 Pro Max so với Samsung thì sao"
        }
    ]
    
    responses = await simulate_multi_turn_extended(service, turns)
    
    # Check turn 1
    msg1 = responses[0].fulfillment_response.messages[0].text.text[0]
    assert "So sánh" in msg1
    assert "iPhone 16" in msg1
    assert "Samsung Galaxy S26 Ultra" in msg1
    assert responses[0].session_info.parameters["product_a_name"] == "iPhone 16"
    assert responses[0].session_info.parameters["product_b_name"] == "Samsung Galaxy S26 Ultra"

    # Check turn 2: product_b_name phải là Samsung Galaxy S26 Ultra nhờ kế thừa ngữ cảnh
    msg2 = responses[1].fulfillment_response.messages[0].text.text[0]
    assert "So sánh" in msg2
    assert "iPhone 17 Pro Max" in msg2
    assert "Samsung Galaxy S26 Ultra" in msg2
    assert responses[1].session_info.parameters["product_a_name"] == "iPhone 17 Pro Max"
    assert responses[1].session_info.parameters["product_b_name"] == "Samsung Galaxy S26 Ultra"


@pytest.mark.asyncio
async def test_budget_search_and_availability():
    """
    TEST SET 12: Tìm kiếm sản phẩm theo ngân sách -> Hỏi xem còn hàng không (kế thừa tên sản phẩm vừa tìm được)
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    turns = [
        # 1. Tìm điện thoại tầm 25 triệu
        {
            "intent": "ProductSearchIntent",
            "slots": {},
            "text": "tìm điện thoại nào tầm 25 triệu đổ lại"
        },
        # 2. Hỏi xem còn hàng không (ở đây bot phải nhớ tên sản phẩm vừa tìm được là iPhone 16 từ kết quả tìm kiếm)
        {
            "intent": "InventoryIntent",
            "slots": {},
            "text": "bản này shop còn hàng không"
        }
    ]
    
    responses = await simulate_multi_turn_extended(service, turns)
    
    # Check turn 1: Giá iPhone 16 (21.99M) phù hợp ngân sách 25 triệu
    msg1 = responses[0].fulfillment_response.messages[0].text.text[0]
    assert "iPhone 16" in msg1
    assert "21.990.000 VNĐ" in msg1

    # Check turn 2: Kiểm tra tồn kho cho iPhone 16
    msg2 = responses[1].fulfillment_response.messages[0].text.text[0]
    assert "iPhone 16" in msg2
    assert "còn hàng" in msg2.lower() or "có hàng" in msg2.lower()
    assert responses[1].session_info.parameters["inventory_status"] == "in_stock"


@pytest.mark.asyncio
async def test_warranty_return_process():
    """
    TEST SET 13: Bảo hành và quy trình đổi trả hàng lỗi kỹ thuật
    """
    service = IntentService(ExtendedFakeMedusaClient())
    
    turns = [
        # 1. Hỏi chính sách bảo hành
        {
            "intent": "WarrantyPolicyIntent",
            "slots": {},
            "text": "cho mình hỏi chính sách bảo hành đổi trả bên mình như thế nào"
        },
        # 2. Đổi trả hàng lỗi kỹ thuật (màn hình bị sọc)
        {
            "intent": "ReturnRequestIntent",
            "slots": {},
            "text": "máy mình mới nhận hôm qua bị sọc màn hình muốn đổi máy mới thì làm sao"
        }
    ]
    
    responses = await simulate_multi_turn_extended(service, turns)
    
    # Check turn 1: Phải hiển thị chính sách bảo hành chung
    msg1 = responses[0].fulfillment_response.messages[0].text.text[0].lower()
    assert "bảo hành" in msg1 or "đổi trả" in msg1
    assert responses[0].session_info.parameters["search_status"] == "warranty_policy"

    # Check turn 2: Nhận diện yêu cầu đổi trả (return_request) và chuyển nhân viên hỗ trợ đổi trả
    msg2 = responses[1].fulfillment_response.messages[0].text.text[0].lower()
    assert "đổi trả" in msg2 or "nhân viên" in msg2
    assert responses[1].session_info.parameters["handover_requested"] is True
    assert responses[1].session_info.parameters["search_status"] == "aftercare_handoff"


@pytest.mark.asyncio
async def test_product_context_is_reused_only_for_related_followups():
    service = IntentService(ExtendedFakeMedusaClient())
    turns = [
        {
            "intent": "ProductPriceIntent",
            "slots": {"product_name": "iPhone 16"},
            "text": "iPhone 16 giá bao nhiêu",
        },
        {
            "intent": "ProductAvailabilityIntent",
            "slots": {},
            "text": "máy này còn hàng không",
        },
        {
            "intent": "StoreInfoIntent",
            "slots": {},
            "text": "shop mở cửa lúc mấy giờ",
        },
        {
            "intent": "ProductPriceIntent",
            "slots": {},
            "text": "giá bao nhiêu",
        },
    ]

    responses = await simulate_multi_turn_extended(service, turns)

    assert "iPhone 16" in responses[0].fulfillment_response.messages[0].text.text[0]
    assert "iPhone 16" in responses[1].fulfillment_response.messages[0].text.text[0]
    assert responses[1].session_info.parameters["current_product_name"] == "iPhone 16"

    assert responses[2].session_info.parameters.get("current_product_name") is None
    final_message = responses[3].fulfillment_response.messages[0].text.text[0]
    assert "chưa tìm thấy sản phẩm" in final_message.lower()
    assert "iPhone 16" not in final_message


@pytest.mark.asyncio
async def test_order_context_is_reused_then_cleared_after_topic_switch():
    service = IntentService(ExtendedFakeMedusaClient())
    turns = [
        {
            "intent": "OrderHistoryIntent",
            "slots": {},
            "text": "xem các đơn gần đây",
        },
        {
            "intent": "OrderDetailIntent",
            "slots": {},
            "text": "cho mình xem chi tiết đơn này",
        },
        {
            "intent": "ProductPriceIntent",
            "slots": {"product_name": "iPhone 16"},
            "text": "iPhone 16 giá bao nhiêu",
        },
        {
            "intent": "OrderDetailIntent",
            "slots": {},
            "text": "chi tiết đơn này",
        },
    ]

    responses = await simulate_multi_turn_extended(service, turns, token="extended-token")

    assert responses[0].session_info.parameters["current_order_code"] == "ORD-1001"
    assert "ORD-1001" in responses[1].fulfillment_response.messages[0].text.text[0]
    assert responses[2].session_info.parameters.get("current_order_code") is None

    final_message = responses[3].fulfillment_response.messages[0].text.text[0]
    assert "cung cấp mã đơn hàng" in final_message.lower()
    assert "ORD-1001" not in final_message


@pytest.mark.asyncio
async def test_product_pronoun_context_supports_installment_and_cart():
    service = IntentService(ExtendedFakeMedusaClient())
    turns = [
        {
            "intent": "ProductPriceIntent",
            "slots": {"product_name": "iPhone 16"},
            "text": "iPhone 16 giá bao nhiêu",
        },
        {
            "intent": "InstallmentIntent",
            "slots": {},
            "text": "máy này trả góp được không",
        },
        {
            "intent": "CartAddItemIntent",
            "slots": {},
            "text": "thêm máy này vào giỏ",
        },
    ]

    responses = await simulate_multi_turn_extended(service, turns)

    assert "iPhone 16" in responses[1].fulfillment_response.messages[0].text.text[0]
    assert "iPhone 16" in responses[2].fulfillment_response.messages[0].text.text[0]
    assert responses[2].session_info.parameters["current_product_name"] == "iPhone 16"


@pytest.mark.asyncio
async def test_deictic_order_reference_requires_context_after_topic_switch():
    service = IntentService(ExtendedFakeMedusaClient())
    turns = [
        {
            "intent": "OrderHistoryIntent",
            "slots": {},
            "text": "xem lịch sử đơn hàng",
        },
        {
            "intent": "ProductPriceIntent",
            "slots": {"product_name": "iPhone 16"},
            "text": "iPhone 16 giá bao nhiêu",
        },
        {
            "intent": "OrderStatusIntent",
            "slots": {},
            "text": "đơn này đang ở đâu",
        },
    ]

    responses = await simulate_multi_turn_extended(service, turns, token="extended-token")

    final_message = responses[2].fulfillment_response.messages[0].text.text[0]
    assert "cung cấp mã đơn hàng" in final_message.lower()
    assert responses[2].session_info.parameters.get("current_order_code") is None
