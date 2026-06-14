import pytest

from app.services.intent_nlu import (
    classify_intent,
    expand_product_abbreviations,
    infer_intent_from_text,
    normalize_resolved_intent,
)


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("xin chào shop", "greeting"),
        ("Ok cậu", "smalltalk_affirmation"),
        ("bạn đjp zai quá", "smalltalk_compliment"),
        ("Bạn đẹp giai quá", "smalltalk_compliment"),
        ("không cần đâu", "smalltalk_negation"),
        ("ip15 bn", "product_price"),
        ("iPhone 15 giá bao nhiêu", "product_price"),
        ("ss s26 còn hàng ko", "inventory"),
        ("shop có mã giảm giá không", "bonus"),
        ("phí ship bao nhiêu", "shipping_policy"),
        ("bảo hành bao lâu", "warranty_policy"),
        ("tôi có đặt đơn nào k", "order_list"),
        ("ORD-1001 đang ở đâu", "order_tracking"),
        ("so sánh iPhone 14 và iPhone 15", "product_compare"),
        ("top sản phẩm bán chạy", "best_sellers"),
        ("sản phẩm rẻ nhất", "top_cheap"),
        ("top giá cao nhất", "top_expensive"),
        ("tư vấn điện thoại chụp ảnh đẹp", "product_recommendation"),
        ("kiểm tra lại đơn này", "order_tracking"),
        ("kiếm iphone 16 pro max", "product_search"),
        ("có samsung dòng s không", "product_search"),
        ("tìm điện thoại dưới 15 triệu", "product_search"),
        ("cho xem máy oppo mới nhất", "product_search"),
        ("báo giá giúp mình", "product_price"),
        ("nói chuyện với người thật", "human_handover"),
        ("/h", "human_handover"),
    ],
)
def test_infer_intent_matrix(text, intent):
    assert infer_intent_from_text(text) == intent


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "🤔🤔🤔",
        "asdf qwer zxcv",
        "16",
        "Messi với Ronaldo ai đẹp trai hơn",
        "F8 học lập trình để đi làm",
    ],
)
def test_infer_intent_returns_none_for_ambiguous_or_off_topic_text(text):
    assert infer_intent_from_text(text) is None


def test_multi_intent_uses_priority_order():
    match = classify_intent("so sánh iPhone 14 và iPhone 15 giá bao nhiêu")

    assert match is not None
    assert match.intent == "product_compare"
    assert match.confidence == 1.0


@pytest.mark.parametrize(
    ("text", "expanded"),
    [
        ("ip15", "iPhone 15"),
        ("ip 14 pro max", "iPhone 14 Pro Max"),
        ("ss s26", "Samsung Galaxy S26"),
    ],
)
def test_expand_product_abbreviations(text, expanded):
    assert expand_product_abbreviations(text) == expanded


@pytest.mark.parametrize(
    ("lex_intent", "resolved"),
    [
        ("ProductPriceIntent", "product_price"),
        ("ShippingPolicyIntent", "shipping_policy"),
        ("ProductRecommendationIntent", "product_recommendation"),
        ("HumanHandoffIntent", "human_handover"),
        ("FallbackIntent", "fallback"),
    ],
)
def test_normalize_resolved_intent_supports_lex_names(lex_intent, resolved):
    assert normalize_resolved_intent(lex_intent) == resolved


def test_intent_failsafe_fixes():
    # 1. Comparison false positives
    assert infer_intent_from_text("Điện thoại mua ở shop được bảo hành chính hãng bao lâu và lỗi 1 đổi 1 trong mấy ngày?") == "warranty_policy"
    assert infer_intent_from_text("Mua iPhone 16 có được tặng kèm củ sạc hay ốp lưng không ạ?") == "bonus"
    
    # 2. Payment methods mapping (MoMo/VNPAY)
    assert infer_intent_from_text("Cửa hàng mình có chấp nhận thanh toán qua ví MoMo hay VNPAY không?") == "payment_method"
    
    # 3. Proper comparison classification
    assert infer_intent_from_text("So sánh iPhone 16 và Samsung Galaxy S26 Plus") == "product_compare"
    assert infer_intent_from_text("Nên chọn mua Xiaomi 15 Ultra hay OnePlus 13 vậy shop?") == "product_compare"

