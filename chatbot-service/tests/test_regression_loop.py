import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.clients.medusa_client import get_medusa_client
from app.clients.gemini_client import get_gemini_client
from tests.test_intent_service import FakeRecommendationGeminiClient, FakeIntentResolvingGeminiClient

# The 161 test cases from test_run_all_cases.py
TEST_CASES = [
    # ProductSearchIntent
    ("ProductSearchIntent", "kiếm iphone 16 pro max"),
    ("ProductSearchIntent", "có samsung dòng s không"),
    ("ProductSearchIntent", "tìm điện thoại dưới 15 triệu"),
    ("ProductSearchIntent", "cho xem máy oppo mới nhất"),
    ("ProductSearchIntent", "shop bán xiaomi nào ngon"),
    ("ProductSearchIntent", "còn điện thoại nào tầm 10 củ không"),

    # ProductPriceIntent
    ("ProductPriceIntent", "iphone 16 giá nhiêu"),
    ("ProductPriceIntent", "giá con samsung s25 ultra"),
    ("ProductPriceIntent", "bản 512gb của iphone 16 pro max bao nhiêu"),
    ("ProductPriceIntent", "máy này giá sao"),
    ("ProductPriceIntent", "báo giá giúp mình"),

    # ProductAvailabilityIntent
    ("ProductAvailabilityIntent", "còn hàng iphone 16 không"),
    ("ProductAvailabilityIntent", "còn màu đen không"),
    ("ProductAvailabilityIntent", "máy này hết hàng chưa"),
    ("ProductAvailabilityIntent", "còn bản 256gb không"),
    ("ProductAvailabilityIntent", "có sẵn tại shop không"),

    # ProductRecommendationIntent
    ("ProductRecommendationIntent", "tư vấn cho mình điện thoại chơi game"),
    ("ProductRecommendationIntent", "mua máy dưới 12 triệu nên chọn gì"),
    ("ProductRecommendationIntent", "cần điện thoại pin khỏe"),
    ("ProductRecommendationIntent", "gợi ý điện thoại chụp ảnh đẹp"),
    ("ProductRecommendationIntent", "sinh viên nên mua máy nào"),

    # ProductCompareIntent
    ("ProductCompareIntent", "iphone 16 với s25 cái nào ngon hơn"),
    ("ProductCompareIntent", "nên chọn xiaomi hay samsung"),
    ("ProductCompareIntent", "so sánh giúp mình 2 máy này"),
    ("ProductCompareIntent", "con nào đáng tiền hơn"),
    ("ProductCompareIntent", "khác nhau chỗ nào"),

    # ProductSpecIntent
    ("ProductSpecIntent", "cấu hình máy này thế nào"),
    ("ProductSpecIntent", "ram bao nhiêu vậy"),
    ("ProductSpecIntent", "dùng chip gì"),
    ("ProductSpecIntent", "màn hình bao nhiêu hz"),
    ("ProductSpecIntent", "có hỗ trợ esim không"),

    # ProductCameraIntent
    ("ProductCameraIntent", "camera có đẹp không"),
    ("ProductCameraIntent", "chụp đêm ổn chứ"),
    ("ProductCameraIntent", "quay video có rung không"),
    ("ProductCameraIntent", "máy nào selfie đẹp"),
    ("ProductCameraIntent", "chụp chân dung ngon không"),

    # ProductBatteryIntent
    ("ProductBatteryIntent", "pin dùng được mấy tiếng"),
    ("ProductBatteryIntent", "pin có trâu không"),
    ("ProductBatteryIntent", "sạc đầy mất bao lâu"),
    ("ProductBatteryIntent", "hỗ trợ sạc nhanh bao nhiêu w"),
    ("ProductBatteryIntent", "dùng cả ngày nổi không"),

    # ProductGamingIntent
    ("ProductGamingIntent", "chơi liên quân mượt không"),
    ("ProductGamingIntent", "chiến pubg max setting được không"),
    ("ProductGamingIntent", "máy nào gaming ngon"),
    ("ProductGamingIntent", "chơi genshin ổn không"),
    ("ProductGamingIntent", "có nóng máy không"),

    # PromotionIntent
    ("PromotionIntent", "đang có sale gì không"),
    ("PromotionIntent", "hôm nay có ưu đãi gì"),
    ("PromotionIntent", "áp được mã giảm giá không"),
    ("PromotionIntent", "có tặng quà kèm không"),
    ("PromotionIntent", "máy này có khuyến mãi không"),

    # InstallmentIntent
    ("InstallmentIntent", "trả góp được không"),
    ("InstallmentIntent", "góp 12 tháng được chứ"),
    ("InstallmentIntent", "cần trả trước bao nhiêu"),
    ("InstallmentIntent", "có 0 phần trăm không"),
    ("InstallmentIntent", "trả góp qua thẻ tín dụng nha"),

    # PaymentMethodIntent
    ("PaymentMethodIntent", "nhận chuyển khoản không"),
    ("PaymentMethodIntent", "có thanh toán momo không"),
    ("PaymentMethodIntent", "quẹt thẻ được không"),
    ("PaymentMethodIntent", "cod được chứ"),
    ("PaymentMethodIntent", "thanh toán bằng vnpay được không"),

    # CartAddItemIntent
    ("CartAddItemIntent", "thêm iphone 16 vào giỏ"),
    ("CartAddItemIntent", "mua luôn 2 cái"),
    ("CartAddItemIntent", "cho mình đặt 1 máy"),
    ("CartAddItemIntent", "bỏ sản phẩm này vào giỏ"),
    ("CartAddItemIntent", "lấy con này luôn"),

    # CartViewIntent
    ("CartViewIntent", "mở giỏ hàng"),
    ("CartViewIntent", "xem giỏ giúp mình"),
    ("CartViewIntent", "trong giỏ còn gì"),
    ("CartViewIntent", "tôi đang mua gì vậy"),
    ("CartViewIntent", "kiểm tra giỏ"),

    # CartUpdateIntent
    ("CartUpdateIntent", "tăng lên 2 sản phẩm"),
    ("CartUpdateIntent", "giảm còn 1 cái"),
    ("CartUpdateIntent", "bỏ sản phẩm này đi"),
    ("CartUpdateIntent", "xóa iphone khỏi giỏ"),
    ("CartUpdateIntent", "sửa giỏ hàng"),

    # CheckoutStartIntent
    ("CheckoutStartIntent", "thanh toán luôn"),
    ("CheckoutStartIntent", "đặt hàng ngay"),
    ("CheckoutStartIntent", "mua ngay đi"),
    ("CheckoutStartIntent", "chốt đơn"),
    ("CheckoutStartIntent", "tiến hành thanh toán"),

    # OrderStatusIntent
    ("OrderStatusIntent", "đơn của mình tới đâu rồi"),
    ("OrderStatusIntent", "hàng giao chưa"),
    ("OrderStatusIntent", "check đơn giúp mình"),
    ("OrderStatusIntent", "đơn đang xử lý à"),
    ("OrderStatusIntent", "bao giờ nhận được hàng"),

    # OrderDetailIntent
    ("OrderDetailIntent", "xem chi tiết đơn này"),
    ("OrderDetailIntent", "đơn này gồm gì vậy"),
    ("OrderDetailIntent", "tổng tiền bao nhiêu"),
    ("OrderDetailIntent", "tôi mua những gì"),
    ("OrderDetailIntent", "xem thông tin đơn"),

    # OrderHistoryIntent
    ("OrderHistoryIntent", "xem các đơn cũ"),
    ("OrderHistoryIntent", "lịch sử mua hàng"),
    ("OrderHistoryIntent", "những đơn đã đặt"),
    ("OrderHistoryIntent", "đơn trước của tôi đâu"),
    ("OrderHistoryIntent", "xem đơn gần đây"),

    # OrderCancelIntent
    ("OrderCancelIntent", "hủy đơn giúp mình"),
    ("OrderCancelIntent", "mình không lấy nữa"),
    ("OrderCancelIntent", "dừng đơn này đi"),
    ("OrderCancelIntent", "hủy đơn hàng nha"),
    ("OrderCancelIntent", "cancel đơn"),

    # OrderModifyIntent
    ("OrderModifyIntent", "đổi địa chỉ nhận hàng"),
    ("OrderModifyIntent", "sửa số điện thoại"),
    ("OrderModifyIntent", "đổi người nhận"),
    ("OrderModifyIntent", "chỉnh lại đơn hàng"),
    ("OrderModifyIntent", "thay đổi thông tin giao hàng"),

    # ShippingPolicyIntent
    ("ShippingPolicyIntent", "ship bao nhiêu tiền"),
    ("ShippingPolicyIntent", "giao tới hà nội mất mấy ngày"),
    ("ShippingPolicyIntent", "có giao toàn quốc không"),
    ("ShippingPolicyIntent", "thời gian giao hàng thế nào"),
    ("ShippingPolicyIntent", "ship nhanh được không"),

    # ShippingTrackingIntent
    ("ShippingTrackingIntent", "theo dõi đơn hàng"),
    ("ShippingTrackingIntent", "tra vận đơn giúp mình"),
    ("ShippingTrackingIntent", "hàng đang ở đâu"),
    ("ShippingTrackingIntent", "shipper giao tới đâu rồi"),
    ("ShippingTrackingIntent", "check hành trình đơn hàng"),

    # ReturnRequestIntent
    ("ReturnRequestIntent", "muốn đổi trả sản phẩm"),
    ("ReturnRequestIntent", "máy lỗi thì đổi sao"),
    ("ReturnRequestIntent", "trả hàng được không"),
    ("ReturnRequestIntent", "chính sách đổi trả thế nào"),
    ("ReturnRequestIntent", "đổi máy mới được chứ"),

    # RefundStatusIntent
    ("RefundStatusIntent", "hoàn tiền tới đâu rồi"),
    ("RefundStatusIntent", "đã refund chưa"),
    ("RefundStatusIntent", "khi nào nhận lại tiền"),
    ("RefundStatusIntent", "tiền hoàn về tài khoản chưa"),
    ("RefundStatusIntent", "kiểm tra hoàn tiền"),

    # WarrantyPolicyIntent
    ("WarrantyPolicyIntent", "bảo hành mấy tháng"),
    ("WarrantyPolicyIntent", "chính sách bảo hành sao"),
    ("WarrantyPolicyIntent", "lỗi phần cứng xử lý thế nào"),
    ("WarrantyPolicyIntent", "bảo hành ở đâu"),
    ("WarrantyPolicyIntent", "được bảo hành chính hãng không"),

    # WarrantyClaimIntent
    ("WarrantyClaimIntent", "gửi bảo hành giúp mình"),
    ("WarrantyClaimIntent", "máy bị lỗi rồi"),
    ("WarrantyClaimIntent", "cần mang đi bảo hành"),
    ("WarrantyClaimIntent", "tạo yêu cầu bảo hành"),
    ("WarrantyClaimIntent", "bảo hành sản phẩm này"),

    # ComplaintIntent
    ("ComplaintIntent", "mình muốn phản ánh"),
    ("ComplaintIntent", "dịch vụ chán quá"),
    ("ComplaintIntent", "giao hàng lâu vậy"),
    ("ComplaintIntent", "shop xử lý kiểu gì thế"),
    ("ComplaintIntent", "tôi không hài lòng"),

    # GreetingIntent
    ("GreetingIntent", "hi"),
    ("GreetingIntent", "alo shop"),
    ("GreetingIntent", "chào shop nha"),
    ("GreetingIntent", "xin chào bạn"),
    ("GreetingIntent", "hello shop"),

    # StoreInfoIntent
    ("StoreInfoIntent", "cửa hàng ở đâu"),
    ("StoreInfoIntent", "có chi nhánh nào không"),
    ("StoreInfoIntent", "mấy giờ mở cửa"),
    ("StoreInfoIntent", "địa chỉ shop là gì"),
    ("StoreInfoIntent", "cuối tuần có mở không"),

    # HumanHandoffIntent
    ("HumanHandoffIntent", "cho gặp nhân viên"),
    ("HumanHandoffIntent", "chuyển mình sang tư vấn viên"),
    ("HumanHandoffIntent", "nói chuyện với người thật"),
    ("HumanHandoffIntent", "cần hỗ trợ trực tiếp"),
    ("HumanHandoffIntent", "gặp CSKH"),

    # FallbackIntent
    ("FallbackIntent", "kể chuyện ma đi"),
    ("FallbackIntent", "thời tiết hôm nay thế nào"),
    ("FallbackIntent", "ai là tổng thống mỹ"),
    ("FallbackIntent", "hướng dẫn nấu bún bò"),
    ("FallbackIntent", "viết code python cho tôi"),
]


class ComprehensiveFakeMedusaClient:
    def __init__(self):
        self.products = [
            {"id": "prod_1", "title": "iPhone 16", "handle": "iphone-16", "metadata": {"chip": "A18"}, "variants": [{"title": "Default", "calculated_price": {"calculated_amount": 19990000, "currency_code": "vnd"}}]},
            {"id": "prod_2", "title": "iPhone 17", "handle": "iphone-17", "metadata": {"chip": "A19"}, "variants": [{"title": "Default", "calculated_price": {"calculated_amount": 22990000, "currency_code": "vnd"}}]},
            {"id": "prod_3", "title": "iPhone 11", "handle": "iphone-11", "variants": [{"title": "Default", "calculated_price": {"calculated_amount": 6990000, "currency_code": "vnd"}}]},
            {"id": "prod_4", "title": "Samsung Galaxy S26 Ultra", "handle": "samsung-galaxy-s26-ultra", "variants": [{"title": "Default", "calculated_price": {"calculated_amount": 32990000, "currency_code": "vnd"}}]},
            {"id": "prod_5", "title": "OPPO Find X8 Pro", "handle": "oppo-find-x8-pro", "variants": [{"title": "Default", "calculated_price": {"calculated_amount": 22990000, "currency_code": "vnd"}}]},
            {"id": "prod_6", "title": "Xiaomi 15 Ultra", "handle": "xiaomi-15-ultra", "variants": [{"title": "Default", "calculated_price": {"calculated_amount": 26990000, "currency_code": "vnd"}}]},
        ]

    async def list_products(self, query=None, limit=150):
        if not query:
            return self.products[:limit]
        q = query.lower()
        results = [p for p in self.products if q in p["title"].lower() or q in p["handle"].lower()]
        return results[:limit]

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


@pytest.mark.parametrize("expected_intent, text", TEST_CASES)
def test_webhook_regression_loop(expected_intent, text):
    fake_medusa = ComprehensiveFakeMedusaClient()
    fake_gemini = FakeRecommendationGeminiClient()

    app.dependency_overrides[get_medusa_client] = lambda: fake_medusa
    app.dependency_overrides[get_gemini_client] = lambda: fake_gemini

    try:
        client = TestClient(app)
        response = client.post(
            "/lexv2/webhook",
            json={
                "sessionState": {
                    "intent": {
                        "name": expected_intent,
                        "slots": {},
                    },
                    "sessionAttributes": {
                        "customer_access_token": "test-token",
                        "current_product_name": "iPhone 16",
                        "current_order_code": "ORD-1001",
                    }
                },
                "inputTranscript": text,
            },
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        body = response.json()
        
        resolved_intent = body["sessionState"]["sessionAttributes"].get("resolved_intent")
        
        expected_norm = expected_intent.lower().replace("intent", "")
        resolved_norm = (resolved_intent or "").lower().replace("intent", "").replace("_", "")
        
        is_correct = resolved_norm == expected_norm
        
        if expected_norm == "promotion" and resolved_norm == "bonus":
            is_correct = True
        if expected_norm == "humanhandoff" and resolved_norm == "humanhandover":
            is_correct = True
        if expected_norm == "orderstatus" and resolved_norm == "ordertracking":
            is_correct = True
        if expected_norm == "shippingtracking" and resolved_norm == "ordertracking":
            is_correct = True
            
        assert is_correct, f"Query '{text}': expected {expected_intent}, got {resolved_intent}"
        
        if expected_intent == "FallbackIntent":
            assert fake_gemini.recommendation_called is False
            assert body["sessionState"]["sessionAttributes"]["resolved_intent"] == "fallback"
            assert body["sessionState"]["sessionAttributes"]["resolution_source"] == "local_nlu"
            
    finally:
        app.dependency_overrides.clear()
