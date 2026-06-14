import itertools

import pytest

from app.schemas.lexv2 import LexV2Request
from app.services.intent_service import IntentService
from tests.test_extended_scenarios import ExtendedFakeMedusaClient


PRODUCTS = ["iPhone 16", "Samsung Galaxy S26 Ultra"]
PRODUCT_FOLLOWUPS = [
    ("ProductAvailabilityIntent", "máy này còn hàng không"),
    ("WarrantyPolicyIntent", "máy này bảo hành bao lâu"),
    ("ProductCameraIntent", "camera máy này thế nào"),
    ("ProductBatteryIntent", "pin máy này dùng lâu không"),
    ("ProductGamingIntent", "máy này chơi game ổn không"),
    ("ProductSpecIntent", "cấu hình máy này thế nào"),
    ("PromotionIntent", "máy này có ưu đãi không"),
    ("InstallmentIntent", "máy này trả góp được không"),
    ("CartAddItemIntent", "thêm máy này vào giỏ"),
    ("CheckoutStartIntent", "mua máy này ngay"),
]
PRODUCT_TOPIC_SWITCHES = [
    ("StoreInfoIntent", "shop mở cửa lúc mấy giờ"),
    ("GreetingIntent", "xin chào shop"),
    ("FallbackIntent", "kể cho tôi chuyện cổ tích"),
    ("HumanHandoffIntent", "cho tôi gặp nhân viên"),
    ("OrderHistoryIntent", "xem lịch sử đơn hàng"),
    ("OrderStatusIntent", "đơn của tôi đang ở đâu"),
    ("OrderDetailIntent", "xem chi tiết đơn hàng"),
    ("OrderCancelIntent", "tôi muốn hủy đơn"),
    ("OrderModifyIntent", "tôi muốn sửa đơn"),
    ("RefundStatusIntent", "bao giờ tôi được hoàn tiền"),
]
PRODUCT_AMBIGUOUS_FOLLOWUPS = [
    ("ProductPriceIntent", "giá bao nhiêu"),
    ("ProductAvailabilityIntent", "còn hàng không"),
    ("WarrantyPolicyIntent", "bảo hành bao lâu"),
    ("ProductCameraIntent", "camera thế nào"),
    ("ProductBatteryIntent", "pin có tốt không"),
]

ORDER_FOLLOWUPS = [
    ("OrderDetailIntent", "xem chi tiết đơn này"),
    ("OrderStatusIntent", "đơn này đang ở đâu"),
    ("ShippingTrackingIntent", "đơn này giao tới đâu"),
    ("OrderCancelIntent", "hủy đơn này giúp tôi"),
    ("OrderModifyIntent", "sửa địa chỉ đơn này"),
    ("RefundStatusIntent", "đơn này hoàn tiền chưa"),
    ("ComplaintIntent", "tôi muốn khiếu nại đơn này"),
    ("OrderDetailIntent", "đơn này tổng tiền bao nhiêu"),
    ("OrderStatusIntent", "kiểm tra lại đơn này"),
    ("ShippingTrackingIntent", "shipper của đơn này tới chưa"),
]
ORDER_TOPIC_SWITCHES = [
    ("ProductPriceIntent", "iPhone 16 giá bao nhiêu", {"product_name": "iPhone 16"}),
    ("ProductSearchIntent", "tìm Samsung Galaxy S26 Ultra", {"product_name": "Samsung Galaxy S26 Ultra"}),
    ("ProductRecommendationIntent", "tư vấn điện thoại chụp ảnh", {}),
    ("StoreInfoIntent", "shop mở cửa lúc mấy giờ", {}),
    ("GreetingIntent", "xin chào shop", {}),
    ("FallbackIntent", "kể cho tôi chuyện cổ tích", {}),
    ("ShippingPolicyIntent", "phí ship bao nhiêu", {}),
    ("PaymentMethodIntent", "shop có nhận momo không", {}),
    ("CartViewIntent", "xem giỏ hàng", {}),
    ("WarrantyPolicyIntent", "chính sách bảo hành thế nào", {}),
]
ORDER_AMBIGUOUS_FOLLOWUPS = [
    ("OrderDetailIntent", "xem chi tiết đơn này"),
    ("OrderStatusIntent", "đơn này đang ở đâu"),
    ("ShippingTrackingIntent", "đơn này giao tới đâu"),
    ("OrderCancelIntent", "hủy đơn này"),
    ("OrderModifyIntent", "sửa đơn này"),
    ("RefundStatusIntent", "hoàn tiền đơn này"),
    ("ComplaintIntent", "khiếu nại đơn này"),
    ("OrderDetailIntent", "đơn này bao nhiêu tiền"),
    ("OrderStatusIntent", "kiểm tra đơn này"),
    ("ShippingTrackingIntent", "shipper tới chưa"),
]


async def send_turn(service, attributes, intent, text, slots=None, token=None):
    request = LexV2Request(
        inputTranscript=text,
        sessionState={
            "intent": {
                "name": intent,
                "slots": {
                    name: {"value": {"interpretedValue": value}}
                    for name, value in (slots or {}).items()
                },
            },
            "sessionAttributes": attributes.copy(),
        },
    )
    response = await service.handle(request, authorization_header=token)
    return response, response.sessionState.sessionAttributes.copy()


PRODUCT_CASES = list(
    itertools.product(
        PRODUCTS,
        PRODUCT_FOLLOWUPS,
        PRODUCT_TOPIC_SWITCHES,
        PRODUCT_AMBIGUOUS_FOLLOWUPS,
    )
)
ORDER_CASES = list(
    itertools.product(
        ORDER_FOLLOWUPS,
        ORDER_TOPIC_SWITCHES,
        ORDER_AMBIGUOUS_FOLLOWUPS,
    )
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("product", "followup", "topic_switch", "ambiguous"), PRODUCT_CASES)
async def test_product_context_matrix(product, followup, topic_switch, ambiguous):
    service = IntentService(ExtendedFakeMedusaClient())
    attributes = {}

    initial_response, attributes = await send_turn(
        service,
        attributes,
        "ProductPriceIntent",
        f"{product} giá bao nhiêu",
        {"product_name": product},
    )
    assert attributes.get("current_product_name") == product
    assert attributes.get("resolved_intent") == "product_price"
    assert attributes.get("search_status") == "success"
    assert product in initial_response.messages[0].content

    related_response, attributes = await send_turn(service, attributes, *followup)

    assert attributes.get("current_product_name") == product
    assert product in related_response.messages[0].content

    _, attributes = await send_turn(service, attributes, *topic_switch)
    assert attributes.get("current_product_name") is None

    _, attributes = await send_turn(service, attributes, *ambiguous)
    assert attributes.get("current_product_name") != product
    assert attributes.get("current_product_id") not in {"prod_iphone16", "prod_samsungs26u"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("followup", "topic_switch", "ambiguous"), ORDER_CASES)
async def test_order_context_matrix(followup, topic_switch, ambiguous):
    service = IntentService(ExtendedFakeMedusaClient())
    attributes = {}

    initial_response, attributes = await send_turn(
        service,
        attributes,
        "OrderHistoryIntent",
        "xem lịch sử đơn hàng",
        token="extended-token",
    )
    assert attributes.get("current_order_code") == "ORD-1001"
    assert attributes.get("resolved_intent") in {"order_history", "order_list"}
    assert attributes.get("search_status") == "success"
    assert "ORD-1001" in initial_response.messages[0].content

    related_response, attributes = await send_turn(
        service,
        attributes,
        *followup,
        token="extended-token",
    )

    assert attributes.get("current_order_code") == "ORD-1001"
    assert (
        "ORD-1001" in related_response.messages[0].content
        or attributes.get("search_status") == "aftercare_handoff"
    )

    _, attributes = await send_turn(
        service,
        attributes,
        topic_switch[0],
        topic_switch[1],
        topic_switch[2],
        token="extended-token",
    )
    assert attributes.get("current_order_code") is None

    final_response, attributes = await send_turn(
        service,
        attributes,
        *ambiguous,
        token="extended-token",
    )
    if ambiguous[1] == "shipper tới chưa":
        assert attributes.get("current_order_code") == "ORD-1001"
        assert "ORD-1001" in final_response.messages[0].content
    else:
        assert attributes.get("current_order_code") != "ORD-1001"
        assert "ORD-1001" not in final_response.messages[0].content
