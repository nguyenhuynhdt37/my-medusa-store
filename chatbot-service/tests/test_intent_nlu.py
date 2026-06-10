import pytest

from app.services.intent_nlu import classify_intent, expand_product_abbreviations, infer_intent_from_text


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
        ("ip 14 pro max", "iPhone 14 pro max"),
        ("ss s26", "Samsung Galaxy s26"),
    ],
)
def test_expand_product_abbreviations(text, expanded):
    assert expand_product_abbreviations(text) == expanded
