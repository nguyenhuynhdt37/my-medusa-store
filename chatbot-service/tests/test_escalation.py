import pytest

from app.services.escalation import is_explicit_handoff_request, should_escalate_to_admin


def build_10000_handoff_regression_cases():
    explicit_templates = [
        "cho tôi gặp nhân viên {n}",
        "gặp người thật giúp mình {n}",
        "nói chuyện với nhân viên ca {n}",
        "chuyển cho sale đơn {n}",
        "tư vấn viên đâu vậy {n}",
        "hỗ trợ trực tiếp giúp tôi {n}",
        "gặp admin xử lý {n}",
        "nhân viên đâu hỗ trợ {n}",
        "cho gặp người phụ trách {n}",
        "/h gặp nhân viên ca {n}",
    ]
    non_handoff_templates = [
        "bạn đjp zai quá {n}",
        "bot dễ thương ghê {n}",
        "medusan giỏi quá {n}",
        "Messi với Ronaldo ai đẹp trai hơn {n}",
        "hôm nay trời đẹp quá {n}",
        "asdf qwer zxcv {n}",
        "F8 học lập trình để đi làm {n}",
        "kể chuyện vui đi {n}",
        "ai là ca sĩ nổi tiếng {n}",
        "tôi đang buồn ngủ {n}",
        "ok {n}",
        "không cần {n}",
        "cảm ơn shop {n}",
        "bạn tên gì {n}",
        "đẹp trai không {n}",
    ]
    business_templates = [
        ("tôi muốn khiếu nại đơn {n}", "complaint"),
        ("shop hoàn tiền giúp tôi đơn {n}", "refund_request"),
        ("đơn hàng giao thiếu sản phẩm {n}", "abnormal_order"),
        ("thanh toán thất bại mà bị trừ tiền {n}", "payment_failed"),
        ("tôi muốn trả hàng mã {n}", "return_request"),
    ]
    product_templates = [
        "iPhone {n} giá bao nhiêu",
        "có sản phẩm nào dưới {n} triệu không",
        "phí ship đơn {n} bao nhiêu",
        "shop có mã giảm giá {n} không",
        "đơn hàng ORD-{n:04d} đang ở đâu",
        "Samsung S{n} còn hàng không",
        "bảo hành máy này bao lâu {n}",
        "so sánh iPhone 14 và iPhone 15 bản {n}",
        "tư vấn điện thoại chụp ảnh đẹp tầm {n} triệu",
        "top sản phẩm bán chạy {n}",
    ]

    cases = []
    for index in range(2000):
        template = explicit_templates[index % len(explicit_templates)]
        cases.append((f"explicit-{index}", template.format(n=index), "HumanHandoverIntent", 0.99, True, "human_handoff"))

    for index in range(3000):
        template = non_handoff_templates[index % len(non_handoff_templates)]
        cases.append((f"misclassified-nonhandoff-{index}", template.format(n=index), "HumanHandoverIntent", 0.95, False, None))

    for index in range(1500):
        template, reason = business_templates[index % len(business_templates)]
        cases.append((f"business-{index}", template.format(n=index), "fallback", 0.5, True, reason))

    for index in range(2000):
        template = product_templates[index % len(product_templates)]
        cases.append((f"low-confidence-product-{index}", template.format(n=index), "product_search", 0.2, False, "low_confidence"))

    for index in range(1500):
        template = non_handoff_templates[(index + 3) % len(non_handoff_templates)]
        cases.append((f"fallback-{index}", template.format(n=index + 100000), "fallback", 0.2, False, "fallback_prompt"))

    assert len(cases) == 10000
    assert len({message for _, message, *_ in cases}) == 10000
    return cases


@pytest.mark.parametrize(
    "message",
    [
        "/h",
        "cho tôi gặp nhân viên",
        "gặp người thật giúp mình",
        "nói chuyện với nhân viên",
        "nói chuyện với người thật",
        "chuyển cho sale đi",
        "tư vấn viên đâu",
    ],
)
def test_explicit_handoff_requests_are_detected(message):
    assert is_explicit_handoff_request(message) is True
    result = should_escalate_to_admin(message=message, intent="HumanHandoverIntent", confidence=0.99)
    assert result.escalate is True
    assert result.reason == "human_handoff"


@pytest.mark.parametrize(
    "message",
    [
        "bạn đjp zai quá",
        "bot dễ thương ghê",
        "Messi với Ronaldo ai đẹp trai hơn",
        "hôm nay trời đẹp quá",
        "asdf qwer zxcv",
    ],
)
def test_non_handoff_messages_do_not_escalate_even_if_intent_is_misclassified(message):
    assert is_explicit_handoff_request(message) is False
    result = should_escalate_to_admin(message=message, intent="HumanHandoverIntent", confidence=0.95)
    assert result.escalate is False


def test_fallback_and_low_confidence_prompt_without_escalation():
    fallback = should_escalate_to_admin(message="asdf qwer", intent="fallback", confidence=0.2)
    low_confidence = should_escalate_to_admin(message="có sản phẩm nào không", intent="product_search", confidence=0.2)

    assert fallback.escalate is False
    assert fallback.reason == "fallback_prompt"
    assert low_confidence.escalate is False
    assert low_confidence.reason == "low_confidence"


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("tôi muốn khiếu nại", "complaint"),
        ("shop hoàn tiền giúp tôi", "refund_request"),
        ("đơn hàng giao thiếu", "abnormal_order"),
        ("thanh toán thất bại mà bị trừ tiền", "payment_failed"),
    ],
)
def test_business_escalation_keywords_still_escalate(message, reason):
    result = should_escalate_to_admin(message=message, intent="fallback", confidence=0.5)

    assert result.escalate is True
    assert result.reason == reason


@pytest.mark.parametrize(
    ("case_id", "message", "intent", "confidence", "expected_escalate", "expected_reason"),
    build_10000_handoff_regression_cases(),
    ids=[case[0] for case in build_10000_handoff_regression_cases()],
)
def test_10000_handoff_regression_cases(case_id, message, intent, confidence, expected_escalate, expected_reason):
    result = should_escalate_to_admin(message=message, intent=intent, confidence=confidence)

    assert result.escalate is expected_escalate, case_id
    if expected_reason:
        assert result.reason == expected_reason, case_id
