from app.services.moderation import moderate_customer_message


def test_moderation_blocks_vietnamese_abusive_language():
    result = moderate_customer_message("địt mẹ")

    assert result.blocked is True
    assert result.reason == "abusive_language"


def test_moderation_allows_normal_product_question():
    result = moderate_customer_message("iPhone 17 Pro Max giá bao nhiêu?")

    assert result.blocked is False
