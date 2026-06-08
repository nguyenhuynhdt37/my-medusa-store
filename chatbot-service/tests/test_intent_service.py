import pytest

from app.schemas.lexv2 import LexV2Request
from app.services.intent_service import IntentService


class FakeMedusaClient:
    async def list_products(self, query=None, limit=50):
        if query and "vintage shorts" in query.lower():
            return [
                {
                    "title": "Vintage Shorts",
                    "handle": "vintage-shorts",
                    "variants": [
                        {
                            "calculated_price": {
                                "calculated_amount": 250000,
                                "currency_code": "vnd",
                            }
                        }
                    ],
                }
            ]
        if query and "hoodie" in query.lower():
            return [
                {
                    "title": "Oversized Hoodie",
                    "handle": "oversized-hoodie",
                    "variants": [
                        {
                            "calculated_price": {
                                "calculated_amount": 299000,
                                "currency_code": "vnd",
                            }
                        }
                    ],
                }
            ]
        return [
            {
                "title": "Oversized Hoodie",
                "handle": "oversized-hoodie",
                "metadata": {
                    "warranty_months": 12,
                    "chip": "A18",
                    "camera": "48MP main camera",
                    "battery": "pin tốt",
                    "sold_count": 188,
                    "rating": 4.8,
                },
                "variants": [
                    {
                        "title": "M / Black",
                        "manage_inventory": True,
                        "calculated_price": {
                            "calculated_amount": 299000,
                            "currency_code": "vnd",
                        }
                    }
                ],
            },
            {
                "title": "Premium Jacket",
                "handle": "premium-jacket",
                "metadata": {
                    "warranty_months": 12,
                    "chip": "Snapdragon 8 Elite",
                    "camera": "Ultra zoom camera",
                    "charging": "fast charging",
                    "sold_count": 95,
                    "rating": 4.7,
                },
                "variants": [
                    {
                        "title": "L / Blue",
                        "manage_inventory": True,
                        "calculated_price": {
                            "calculated_amount": 999000,
                            "currency_code": "vnd",
                        }
                    }
                ],
            }
        ]

    async def find_order(self, order_code):
        return await self.find_customer_order(order_code, customer_access_token="test-token")

    async def find_customer_order(self, order_code, customer_access_token):
        return {
            "display_id": 1001,
            "fulfillment_status": "shipped",
            "payment_status": "captured",
            "status": "pending",
            "total": 599000,
            "currency_code": "vnd",
            "created_at": "2026-05-31T10:00:00.000Z",
        }

    async def list_customer_orders(self, customer_access_token, limit=10):
        return [
            {
                "display_id": 1001,
                "fulfillment_status": "shipped",
                "payment_status": "captured",
                "status": "pending",
                "total": 599000,
                "currency_code": "vnd",
            }
        ]


class FakeGeminiClient:
    def is_enabled(self):
        return True

    async def rewrite_customer_reply(self, **kwargs):
        return f"Gemini: {kwargs['draft_reply']}"


def make_request(intent: str, parameters: dict, text: str | None = None):
    return LexV2Request(
        inputTranscript=text,
        sessionState={
            "intent": {
                "name": intent,
                "slots": {
                    name: {"value": {"interpretedValue": val}}
                    for name, val in parameters.items()
                }
            },
            "sessionAttributes": parameters.copy()
        }
    )


@pytest.mark.asyncio
async def test_product_price_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("ProductPrice", {"product": "áo hoodie"}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Oversized Hoodie" in message
    assert "299.000 VNĐ" in message
    assert response.session_info.parameters["current_product_name"] == "Oversized Hoodie"
    assert response.session_info.parameters["search_status"] == "success"


@pytest.mark.asyncio
async def test_product_price_followup_uses_current_product_context():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request(
            "ProductPrice",
            {"current_product_name": "Oversized Hoodie"},
            text="giá bao nhiêu",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Oversized Hoodie" in message
    assert "299.000 VNĐ" in message


@pytest.mark.asyncio
async def test_product_price_extracts_product_from_text_when_parameter_missing():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("ProductPrice", {}, text="Giá Vintage Shorts bao nhiêu"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Vintage Shorts" in message
    assert response.session_info.parameters["current_product_price"] == "250.000 VNĐ"


@pytest.mark.asyncio
async def test_order_tracking_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request("OrderTracking", {"order_id": "ORD-1001"}),
        authorization_header="Bearer test-token",
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "ORD-1001" in message
    assert "đang được giao" in message


@pytest.mark.asyncio
async def test_order_tracking_requires_login():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("OrderTracking", {"order_id": "ORD-1001"}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "cần đăng nhập" in message


@pytest.mark.asyncio
async def test_order_status_intent_maps_to_order_tracking():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request("OrderStatusIntent", {"order_id": "ORD-1001"}),
        authorization_header="Bearer test-token",
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "ORD-1001" in message
    assert response.session_info.parameters["search_status"] == "success"


@pytest.mark.asyncio
async def test_order_status_misclassification_without_order_text_falls_back():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("OrderStatusIntent", {}, text="asdf qwer zxcv không hiểu gì"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Mình chưa hiểu yêu cầu" in message


@pytest.mark.asyncio
async def test_product_search_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("ProductSearch", {}, text="Tìm hoodie"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Sản phẩm phù hợp" in message
    assert response.session_info.parameters["result_count"] == 1


@pytest.mark.asyncio
async def test_product_recommendation_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("ProductRecommendation", {"style": "streetwear"}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Gợi ý sản phẩm" in message
    assert response.session_info.parameters["search_status"] == "recommendation_success"


@pytest.mark.asyncio
async def test_recommendation_text_overrides_product_search_intent():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("ProductSearch", {}, text="Gợi ý áo mặc mùa đông"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Gợi ý sản phẩm" in message
    assert response.session_info.parameters["search_status"] == "recommendation_success"


@pytest.mark.asyncio
async def test_bonus_without_promotions_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("Bonus", {"product": "hoodie"}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "chưa thấy chương trình khuyến mãi" in message
    assert response.session_info.parameters["promotion_status"] == "none"


@pytest.mark.asyncio
async def test_promotion_code_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("PromotionIntent", {"promo_code": "FREESHIP"}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "FREESHIP" in message
    assert "120.000 VNĐ" in message
    assert response.session_info.parameters["search_status"] == "promotion_success"


@pytest.mark.asyncio
async def test_product_promotion_followup_uses_current_product_context():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request(
            "PromotionIntent",
            {"current_product_name": "Oversized Hoodie"},
            text="có giảm giá không",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "chưa thấy chương trình khuyến mãi" in message
    assert response.session_info.parameters["current_product_name"] == "Oversized Hoodie"


@pytest.mark.asyncio
async def test_generic_promotion_response_lists_available_codes():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("PromotionIntent", {}, text="shop có mã giảm giá không"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "WELCOME10" in message
    assert "FREESHIP" in message
    assert response.session_info.parameters["search_status"] == "promotion_codes_available"


@pytest.mark.asyncio
async def test_inventory_intent_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("InventoryIntent", {"product_name": "hoodie"}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Oversized Hoodie" in message
    assert "có hàng" in message
    assert response.session_info.parameters["inventory_status"] == "in_stock"


@pytest.mark.asyncio
async def test_inventory_followup_uses_current_product_context():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request(
            "InventoryIntent",
            {"current_product_name": "Oversized Hoodie"},
            text="còn hàng không",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Oversized Hoodie" in message
    assert "có hàng" in message


@pytest.mark.asyncio
async def test_warranty_followup_uses_current_product_context():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request(
            "WarrantyPolicyIntent",
            {"current_product_name": "Oversized Hoodie"},
            text="bảo hành bao lâu",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Oversized Hoodie" in message
    assert "12 tháng" in message


@pytest.mark.asyncio
async def test_product_compare_intent_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request(
            "ProductCompareIntent",
            {"product_a": "hoodie", "product_b": "premium jacket"},
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "So sánh nhanh" in message
    assert "Oversized Hoodie" in message
    assert "Premium Jacket" in message
    assert response.session_info.parameters["search_status"] == "compare_success"


@pytest.mark.asyncio
async def test_top_expensive_products_from_text():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("ProductPrice", {}, text="top 5 sản phẩm giá cao nhất"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Top sản phẩm giá cao nhất" in message
    assert "Premium Jacket" in message
    assert response.session_info.parameters["search_status"] == "top_expensive"


@pytest.mark.asyncio
async def test_best_seller_products_from_text():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("Default Negative Intent", {}, text="bán chạy nhất"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Sản phẩm bán chạy nhất" in message
    assert response.session_info.parameters["search_status"] == "best_sellers"


@pytest.mark.asyncio
async def test_promotion_text_overrides_fallback_intent():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("Default Negative Intent", {}, text="có chương trình gì mới không ạ"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "khuyến mãi" in message
    assert response.session_info.parameters["search_status"] == "promotion_codes_available"


@pytest.mark.asyncio
async def test_order_list_requires_login():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("Default Negative Intent", {}, text="tôi có đặt đơn nào k"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "cần đăng nhập" in message
    assert response.session_info.parameters["search_status"] == "authentication_required"


@pytest.mark.asyncio
async def test_order_list_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request("Default Negative Intent", {}, text="tôi có đặt đơn nào k"),
        authorization_header="Bearer test-token",
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "ORD-1001" in message
    assert response.session_info.parameters["order_count"] == 1


@pytest.mark.asyncio
async def test_order_detail_response_requires_authenticated_customer():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request("OrderDetail", {"order_id": "ORD-1001"}),
        authorization_header="Bearer test-token",
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Thông tin ORD-1001" in message
    assert "599.000 VNĐ" in message


@pytest.mark.asyncio
async def test_human_handover_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("HumanHandover", {}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "nhân viên hỗ trợ" in message
    assert response.session_info.parameters["handover_requested"] is True


@pytest.mark.asyncio
async def test_human_handover_text_overrides_recommendation_keywords():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("HumanHandoffIntent", {}, text="cho tôi gặp tư vấn viên"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "nhân viên hỗ trợ" in message
    assert response.session_info.parameters["search_status"] == "human_handover"


@pytest.mark.asyncio
async def test_shipping_policy_response_from_intent():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("ShippingPolicyIntent", {}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Giao hàng tiêu chuẩn" in message
    assert "FREESHIP" in message
    assert response.session_info.parameters["search_status"] == "shipping_policy"


@pytest.mark.asyncio
async def test_shipping_policy_text_overrides_price_keywords():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("Default Negative Intent", {}, text="phí ship bao nhiêu"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "120.000 VNĐ" in message
    assert response.session_info.parameters["search_status"] == "shipping_policy"


@pytest.mark.asyncio
async def test_warranty_policy_response():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("WarrantyPolicyIntent", {"product_name": "hoodie"}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "bảo hành 12 tháng" in message
    assert "đổi trả trong 7 ngày" in message
    assert response.session_info.parameters["search_status"] == "warranty_policy"


@pytest.mark.asyncio
async def test_gemini_rewrites_only_customer_text():
    service = IntentService(FakeMedusaClient(), gemini_client=FakeGeminiClient())
    response = await service.handle(make_request("ProductPrice", {"product": "áo hoodie"}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert message.startswith("Gemini:")
    assert response.session_info.parameters["current_product_name"] == "Oversized Hoodie"
    assert response.fulfillment_response.messages[1].payload["product"]["title"] == "Oversized Hoodie"
