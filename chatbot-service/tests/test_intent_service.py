import pytest

from app.schemas.lexv2 import LexV2Request
from app.services.intent_service import IntentService, extract_product_compare_names_from_text
from tests.test_extended_scenarios import ExtendedFakeMedusaClient


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


class FakeIntentResolvingGeminiClient(FakeGeminiClient):
    def __init__(self):
        self.resolve_called = False

    async def resolve_customer_intent(self, **kwargs):
        self.resolve_called = True
        return {"intent": "product_recommendation", "confidence": 0.83}


class FakeHumanResolvingGeminiClient(FakeGeminiClient):
    async def resolve_customer_intent(self, **kwargs):
        return {"intent": "human_handover", "confidence": 0.95}


class FakeRecommendationGeminiClient(FakeGeminiClient):
    def __init__(self):
        self.recommendation_called = False
        self.last_user_text = None
        self.last_products = None

    async def generate_product_recommendation(self, user_text, products):
        self.recommendation_called = True
        self.last_user_text = user_text
        self.last_products = products
        return {
            "recommended_product_ids": ["prod_1"],
            "recommendation_message": "Đây là gợi ý của Gemini dành cho mẹ của bạn."
        }



class PhoneCatalogFakeMedusaClient:
    def __init__(self):
        self.products = [
            self._product("iPhone 16", "iphone-16", 19990000),
            self._product("iPhone 17", "iphone-17", 22990000),
            self._product("iPhone 11", "iphone-11", 6990000),
            self._product("Samsung Galaxy S26 Ultra", "samsung-galaxy-s26-ultra", 32990000),
            self._product("Samsung Galaxy S26 Plus", "samsung-galaxy-s26-plus", 25990000),
        ]

    @staticmethod
    def _product(title, handle, amount):
        return {
            "title": title,
            "handle": handle,
            "variants": [
                {
                    "title": "Default",
                    "calculated_price": {
                        "calculated_amount": amount,
                        "original_amount": amount,
                        "currency_code": "vnd",
                    },
                }
            ],
        }

    async def list_products(self, query=None, limit=50):
        if not query:
            return self.products[:limit]

        query_lower = query.lower()
        if "iphone 16 pro max" in query_lower:
            return [self.products[0]]

        results = [
            product
            for product in self.products
            if query_lower in product["title"].lower() or query_lower in product["handle"].lower()
        ]
        return results[:limit]

    async def find_customer_order(self, order_code, customer_access_token):
        return None

    async def list_customer_orders(self, customer_access_token, limit=10):
        return []


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


def make_request_with_session(intent: str, parameters: dict, session: dict, text: str | None = None):
    merged = session.copy()
    merged.update(parameters)
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
            "sessionAttributes": merged,
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
async def test_product_context_is_not_reused_for_unrelated_product_intent():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request(
            "ProductPrice",
            {"current_product_name": "Oversized Hoodie"},
            text="hướng dẫn tôi sử dụng app",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Mình chưa hiểu rõ" in message
    assert "Oversized Hoodie" not in message
    assert response.session_info.parameters["search_status"] == "fallback"


@pytest.mark.asyncio
async def test_product_context_is_not_reused_for_bot_compliment():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(
        make_request(
            "ProductPrice",
            {"current_product_name": "Oversized Hoodie"},
            text="Bạn đẹp giai quá",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Cảm ơn" in message
    assert "Oversized Hoodie" not in message
    assert response.session_info.parameters["resolved_intent"] == "smalltalk_compliment"


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
    assert "đăng nhập" in message
    assert len(response.fulfillment_response.messages) == 1


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
async def test_product_price_response_uses_deterministic_business_data():
    gemini_client = FakeGeminiClient()
    service = IntentService(FakeMedusaClient(), gemini_client=gemini_client)
    response = await service.handle(make_request("ProductPrice", {"product": "áo hoodie"}))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert not message.startswith("Gemini:")
    assert response.session_info.parameters["current_product_name"] == "Oversized Hoodie"
    assert response.fulfillment_response.messages[1].payload["product"]["title"] == "Oversized Hoodie"


@pytest.mark.asyncio
async def test_specific_lex_intent_does_not_call_gemini_resolution():
    gemini_client = FakeIntentResolvingGeminiClient()
    service = IntentService(FakeMedusaClient(), gemini_client=gemini_client)

    response = await service.handle(
        make_request("ShippingPolicyIntent", {}, text="phí ship bao nhiêu")
    )

    assert gemini_client.resolve_called is False
    assert response.session_info.parameters["resolved_intent"] == "shipping_policy"
    assert response.session_info.parameters["resolution_source"] == "lex"


@pytest.mark.asyncio
async def test_fallback_lex_intent_does_not_use_gemini_nlu_fallback():
    gemini_client = FakeIntentResolvingGeminiClient()
    service = IntentService(FakeMedusaClient(), gemini_client=gemini_client)

    response = await service.handle(
        make_request("FallbackIntent", {}, text="máy nào hợp mua cho mẹ")
    )

    assert gemini_client.resolve_called is False
    assert response.session_info.parameters["resolved_intent"] == "fallback"
    assert response.session_info.parameters["resolution_source"] == "local_nlu"


@pytest.mark.asyncio
async def test_product_recommendation_with_gemini():
    class CustomFakeMedusaClient:
        async def list_products(self, query=None, limit=150):
            return [
                {
                    "id": "prod_1",
                    "title": "iPhone 15 Pro",
                    "handle": "iphone-15-pro",
                    "metadata": {
                        "chip": "A17 Pro",
                    },
                    "variants": [
                        {
                            "title": "Default",
                            "calculated_price": {
                                "calculated_amount": 25000000,
                                "currency_code": "vnd",
                            }
                        }
                    ]
                },
                {
                    "id": "prod_2",
                    "title": "Samsung S24",
                    "handle": "samsung-s24",
                    "metadata": {
                        "chip": "Exynos 2400",
                    },
                    "variants": [
                        {
                            "title": "Default",
                            "calculated_price": {
                                "calculated_amount": 20000000,
                                "currency_code": "vnd",
                            }
                        }
                    ]
                }
            ]

    gemini_client = FakeRecommendationGeminiClient()
    service = IntentService(CustomFakeMedusaClient(), gemini_client=gemini_client)

    response = await service.handle(
        make_request("ProductRecommendation", {}, text="máy nào quay phim đẹp")
    )

    assert gemini_client.recommendation_called is True
    assert gemini_client.last_user_text == "máy nào quay phim đẹp"
    assert len(gemini_client.last_products) == 2
    
    # Asserting that the recommended product was returned and the message was used
    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Đây là gợi ý của Gemini dành cho mẹ của bạn." in message
    assert "iPhone 15 Pro" in message
    assert response.session_info.parameters["search_status"] == "recommendation_success"



@pytest.mark.asyncio
async def test_off_topic_text_does_not_follow_misclassified_recommendation_intent():
    service = IntentService(FakeMedusaClient(), gemini_client=FakeIntentResolvingGeminiClient())
    response = await service.handle(
        make_request(
            "ProductRecommendationIntent",
            {},
            text="Messi với ronaldo thì ai đẹp trai hơn",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "sản phẩm" in message
    assert response.session_info.parameters["search_status"] in {"gemini_clarify", "fallback_handover", "fallback"}
    assert response.session_info.parameters["resolved_intent"] == "fallback"


@pytest.mark.asyncio
async def test_bot_compliment_is_smalltalk_not_handover():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("FallbackIntent", {}, text="bạn đjp zai quá"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Cảm ơn" in message
    assert response.session_info.parameters["search_status"] == "smalltalk_compliment"
    assert response.session_info.parameters["resolved_intent"] == "smalltalk_compliment"


@pytest.mark.asyncio
async def test_lex_handover_intent_is_ignored_without_explicit_handoff_text():
    service = IntentService(FakeMedusaClient())
    response = await service.handle(make_request("HumanHandoverIntent", {}, text="asdf qwer zxcv"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Mình chưa hiểu rõ" in message
    assert response.session_info.parameters["resolved_intent"] == "fallback"
    assert response.session_info.parameters["search_status"] == "fallback"
    assert response.session_info.parameters.get("handover_requested") is None


@pytest.mark.asyncio
async def test_gemini_handover_resolution_is_ignored_without_explicit_handoff_text():
    service = IntentService(FakeMedusaClient(), gemini_client=FakeHumanResolvingGeminiClient())
    response = await service.handle(make_request("FallbackIntent", {}, text="asdf qwer zxcv"))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "sản phẩm" in message
    assert response.session_info.parameters["resolved_intent"] == "fallback"
    assert response.session_info.parameters.get("handover_requested") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "resolved_intent", "search_status"),
    [
        ("mua iphone 15 trả góp 12 tháng", "installment", "payment_installment_policy"),
        ("shop có nhận momo không", "payment_method", "payment_installment_policy"),
        ("cho tôi xem giỏ hàng", "cart_view", "cart_checkout_guidance"),
        ("tôi muốn hủy đơn 12345", "order_cancel", "aftercare_handoff"),
        ("bao giờ tôi được hoàn tiền", "refund_status", "aftercare_handoff"),
        ("địa chỉ cửa hàng ở đâu", "store_info", "store_info"),
    ],
)
async def test_fallback_uses_new_lex_intent_classifier(text, resolved_intent, search_status):
    service = IntentService(FakeMedusaClient())

    response = await service.handle(make_request("FallbackIntent", {}, text=text))

    assert response.session_info.parameters["resolved_intent"] == resolved_intent
    assert response.session_info.parameters["search_status"] == search_status


@pytest.mark.asyncio
async def test_specific_shipping_tracking_intent_is_not_overridden_by_legacy_classifier():
    service = IntentService(FakeMedusaClient())

    response = await service.handle(
        make_request("ShippingTrackingIntent", {"order_id": "ORD-1001"}, text="đơn đang giao tới đâu"),
        authorization_header="Bearer test-token",
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "ORD-1001" in message
    assert response.session_info.parameters["resolved_intent"] == "shipping_tracking"
    assert response.session_info.parameters["resolution_source"] == "lex"


@pytest.mark.asyncio
async def test_specific_payment_intent_is_authoritative():
    service = IntentService(FakeMedusaClient())

    response = await service.handle(
        make_request("PaymentMethodIntent", {}, text="thanh toán khi nhận hàng được không")
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "COD" in message
    assert response.session_info.parameters["resolved_intent"] == "payment_method"
    assert response.session_info.parameters["resolution_source"] == "lex"


@pytest.mark.asyncio
async def test_exact_model_with_missing_qualifier_does_not_fallback_to_base_model():
    service = IntentService(PhoneCatalogFakeMedusaClient())
    response = await service.handle(
        make_request("ProductSearchIntent", {}, text="kiếm iphone 16 pro max")
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "iPhone 16" not in message
    assert "chưa tìm thấy" in message
    assert response.session_info.parameters["search_status"] == "product_not_found"


@pytest.mark.asyncio
async def test_budget_phone_search_lists_products_under_budget():
    service = IntentService(PhoneCatalogFakeMedusaClient())
    response = await service.handle(
        make_request("ProductSearchIntent", {}, text="tìm điện thoại dưới 15 triệu")
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "iPhone 11" in message
    assert "6.990.000 VNĐ" in message
    assert "iPhone 16" not in message
    assert response.session_info.parameters["search_status"] == "success"


@pytest.mark.asyncio
async def test_unknown_brand_search_does_not_return_unrelated_recommendations():
    service = IntentService(PhoneCatalogFakeMedusaClient())
    response = await service.handle(
        make_request("ProductSearchIntent", {}, text="cho xem máy oppo mới nhất")
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "iPhone" not in message
    assert "Samsung" not in message
    assert "chưa tìm thấy" in message
    assert response.session_info.parameters["search_status"] == "product_not_found"


@pytest.mark.asyncio
async def test_bare_two_digit_text_is_not_treated_as_order_lookup():
    service = IntentService(PhoneCatalogFakeMedusaClient())
    response = await service.handle(
        make_request("OrderStatusIntent", {"order_id": "16"}, text="16")
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "cần đăng nhập" not in message
    assert response.session_info.parameters["search_status"] in {"missing_order_code", "fallback"}


@pytest.mark.asyncio
async def test_generic_price_after_multi_product_search_does_not_reuse_stale_product():
    service = IntentService(PhoneCatalogFakeMedusaClient())

    first = await service.handle(
        make_request("ProductSearchIntent", {}, text="có samsung dòng s không")
    )
    session = first.sessionState.sessionAttributes.copy()
    assert "Samsung Galaxy S26 Ultra" in first.fulfillment_response.messages[0].text.text[0]
    assert not session.get("current_product_name")

    second = await service.handle(
        make_request_with_session("ProductPriceIntent", {}, session, text="báo giá giúp mình")
    )

    message = second.fulfillment_response.messages[0].text.text[0]
    assert "Samsung Galaxy S26 Ultra" not in message
    assert "iPhone" not in message
    assert second.session_info.parameters["search_status"] in {"product_not_found", "fallback"}


@pytest.mark.asyncio
async def test_product_context_expires_after_two_unrelated_turns():
    service = IntentService(PhoneCatalogFakeMedusaClient())

    first = await service.handle(
        make_request("ProductPriceIntent", {"product_name": "iPhone 16"}, text="iPhone 16 giá bao nhiêu")
    )
    session = first.sessionState.sessionAttributes.copy()
    assert session["current_product_name"] == "iPhone 16"
    assert session["product_context_turns_remaining"] == 2

    second = await service.handle(
        make_request_with_session("FallbackIntent", {}, session, text="ok")
    )
    session = second.sessionState.sessionAttributes.copy()
    assert session["current_product_name"] == "iPhone 16"
    assert session["product_context_turns_remaining"] == 1

    third = await service.handle(
        make_request_with_session("FallbackIntent", {}, session, text="vâng")
    )
    session = third.sessionState.sessionAttributes.copy()
    assert session.get("current_product_name") is None
    assert session.get("history_products") is None

    fourth = await service.handle(
        make_request_with_session("ProductPriceIntent", {}, session, text="giá bao nhiêu")
    )
    message = fourth.fulfillment_response.messages[0].text.text[0]
    assert "iPhone 16" not in message
    assert fourth.session_info.parameters["search_status"] in {"product_not_found", "fallback"}


@pytest.mark.asyncio
async def test_order_context_expires_after_two_unrelated_turns():
    service = IntentService(FakeMedusaClient())

    first = await service.handle(
        make_request("OrderTracking", {"order_id": "ORD-1001"}, text="kiểm tra đơn ORD-1001"),
        authorization_header="Bearer test-token",
    )
    session = first.sessionState.sessionAttributes.copy()
    assert session["current_order_code"] == "ORD-1001"
    assert session["order_context_turns_remaining"] == 2

    second = await service.handle(
        make_request_with_session("FallbackIntent", {}, session, text="ok")
    )
    session = second.sessionState.sessionAttributes.copy()
    assert session["current_order_code"] == "ORD-1001"
    assert session["order_context_turns_remaining"] == 1

    third = await service.handle(
        make_request_with_session("FallbackIntent", {}, session, text="vâng")
    )
    session = third.sessionState.sessionAttributes.copy()
    assert session.get("current_order_code") is None

    fourth = await service.handle(
        make_request_with_session("OrderStatusIntent", {}, session, text="đơn này đang ở đâu"),
        authorization_header="Bearer test-token",
    )
    message = fourth.fulfillment_response.messages[0].text.text[0]
    assert "ORD-1001" not in message
    assert fourth.session_info.parameters["search_status"] == "missing_order_code"


@pytest.mark.asyncio
async def test_recommendation_respects_explicit_budget_range():
    service = IntentService(PhoneCatalogFakeMedusaClient())
    response = await service.handle(
        make_request(
            "ProductRecommendationIntent",
            {},
            text="Shop tư vấn cho mình máy nào tầm 15 đến 20 triệu chơi game mượt và màn hình đẹp với.",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "iPhone 16" in message
    assert "iPhone 11" not in message
    assert "iPhone 17" not in message


@pytest.mark.asyncio
async def test_generic_promotion_does_not_reuse_previous_product_context():
    service = IntentService(PhoneCatalogFakeMedusaClient())
    response = await service.handle(
        make_request_with_session(
            "PromotionIntent",
            {},
            {"current_product_name": "OPPO Find X8 Pro", "product_context_turns_remaining": 2},
            text="Hôm nay shop có mã giảm giá hay chương trình khuyến mãi gì cho khách mới không?",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "WELCOME10" in message
    assert "OPPO Find X8 Pro" not in message


@pytest.mark.asyncio
async def test_installment_policy_does_not_treat_whole_sentence_as_product():
    service = IntentService(PhoneCatalogFakeMedusaClient())
    response = await service.handle(
        make_request(
            "InstallmentIntent",
            {"product_name": "Mình muốn mua trả góp qua thẻ tín dụng thì lãi suất và cần trả trước"},
            text="Mình muốn mua trả góp qua thẻ tín dụng thì lãi suất thế nào và cần trả trước bao nhiêu?",
        )
    )

    message = response.fulfillment_response.messages[0].text.text[0]
    assert "với Mình muốn" not in message
    assert "Shop hỗ trợ các phương thức thanh toán:" in message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intent", "text", "expected"),
    [
        ("ProductSpecIntent", "iPhone 17 có hỗ trợ esim không và dùng chip gì thế?", "Apple A19 Pro"),
        ("ProductCameraIntent", "camera Samsung Galaxy S26 Ultra có đẹp không?", "200MP Zoom 100x"),
        ("ProductBatteryIntent", "pin Samsung Galaxy S26 Ultra dùng được bao lâu?", "5000mAh"),
    ],
)
async def test_product_advice_returns_technical_data_instead_of_price_table(intent, text, expected):
    service = IntentService(ExtendedFakeMedusaClient())
    response = await service.handle(make_request(intent, {}, text=text))

    message = response.fulfillment_response.messages[0].text.text[0]
    assert expected in message
    assert "Bảng giá" not in message


def test_extracts_products_from_long_comparison_sentence():
    left, right = extract_product_compare_names_from_text(
        "So sánh giúp mình cấu hình giữa iPhone 16 và Samsung Galaxy S26 Plus cái nào tốt hơn?"
    )

    assert left == "iPhone 16"
    assert right == "Samsung Galaxy S26 Plus"


@pytest.mark.asyncio
async def test_order_detail_extraction_and_lookup():
    service = IntentService(FakeMedusaClient())
    
    # 1. Test "chi tiết ord-1001" extracts "ORD-1001" and successfully loads order details
    response = await service.handle(
        make_request("FallbackIntent", {}, text="chi tiết ord-1001"),
        authorization_header="Bearer test-token",
    )
    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Thông tin ORD-1001:" in message
    assert "599.000" in message
    assert response.session_info.parameters["current_order_code"] == "ORD-1001"

    # 2. Test "chi tiết đơn hàng 1001" extracts "1001" and loads the order
    response2 = await service.handle(
        make_request("FallbackIntent", {}, text="chi tiết đơn hàng 1001"),
        authorization_header="Bearer test-token",
    )
    message2 = response2.fulfillment_response.messages[0].text.text[0]
    assert "Thông tin ORD-1001:" in message2
    assert response2.session_info.parameters["current_order_code"] == "ORD-1001"


@pytest.mark.asyncio
async def test_promo_code_direct_routing():
    service = IntentService(PhoneCatalogFakeMedusaClient())
    
    # Test "WELCOME10" is routed directly to bonus/promotions and displays welcome discount details
    response = await service.handle(
        make_request("FallbackIntent", {}, text="WELCOME10")
    )
    message = response.fulfillment_response.messages[0].text.text[0]
    assert "WELCOME10" in message
    assert "giảm 10%" in message
    assert response.session_info.parameters["resolved_intent"] == "bonus"
    
    # Test "mã giảm giá WELCOME10"
    response2 = await service.handle(
        make_request("FallbackIntent", {}, text="mã giảm giá WELCOME10")
    )
    message2 = response2.fulfillment_response.messages[0].text.text[0]
    assert "WELCOME10" in message2
    assert "giảm 10%" in message2


@pytest.mark.asyncio
async def test_failsafe_fixes_in_intent_service():
    from app.services.intent_service import is_plausible_product_name
    
    # 1. Test is_plausible_product_name
    assert is_plausible_product_name("ip16") is True
    assert is_plausible_product_name("iphone 16") is True
    assert is_plausible_product_name("0") is False
    assert is_plausible_product_name("0%") is False
    assert is_plausible_product_name("16") is False
    assert is_plausible_product_name("va") is False
    assert is_plausible_product_name(None) is False

    service = IntentService(PhoneCatalogFakeMedusaClient())

    # 2. Test brand fallback in product_price when product is not in catalog (e.g. iPhone 15 Pro Max)
    response = await service.handle(
        make_request("ProductPrice", {"product": "iPhone 15 Pro Max"}, text="iPhone 15 Pro Max giá bao nhiêu")
    )
    message = response.fulfillment_response.messages[0].text.text[0]
    assert "Sản phẩm phù hợp" in message
    assert "iPhone 16" in message
    assert "iPhone 17" in message
    assert "iPhone 11" in message
    assert response.session_info.parameters["search_status"] == "product_list_fallback"

    # 3. Test brand fallback in inventory_status
    response_inv = await service.handle(
        make_request("ProductAvailability", {"product": "iPhone 15 Pro Max"}, text="iPhone 15 Pro Max còn hàng không")
    )
    message_inv = response_inv.fulfillment_response.messages[0].text.text[0]
    assert "Sản phẩm phù hợp" in message_inv
    assert "iPhone 16" in message_inv
    assert "iPhone 17" in message_inv
    assert response_inv.session_info.parameters["search_status"] == "product_list_fallback"

    # 4. Test flexible comparison parsing with catalog scanning fallback
    response_comp = await service.handle(
        make_request("ProductCompareIntent", {}, text="So sánh giúp mình cấu hình giữa iPhone 16 và Samsung Galaxy S26 Plus cái nào tốt hơn?")
    )
    message_comp = response_comp.fulfillment_response.messages[0].text.text[0]
    assert "So sánh nhanh" in message_comp
    assert "iPhone 16" in message_comp
    assert "Samsung Galaxy S26 Plus" in message_comp

