from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "tmp"


CASES: list[tuple[str, str]] = [
    ("ProductSearchIntent", "kiếm iphone 16 pro max"),
    ("ProductSearchIntent", "có samsung dòng s không"),
    ("ProductSearchIntent", "tìm điện thoại dưới 15 triệu"),
    ("ProductSearchIntent", "cho xem máy oppo mới nhất"),
    ("ProductSearchIntent", "shop bán xiaomi nào ngon"),
    ("ProductSearchIntent", "còn điện thoại nào tầm 10 củ không"),
    ("ProductPriceIntent", "iphone 16 giá nhiêu"),
    ("ProductPriceIntent", "giá con samsung s25 ultra"),
    ("ProductPriceIntent", "bản 512gb của iphone 16 pro max bao nhiêu"),
    ("ProductPriceIntent", "máy này giá sao"),
    ("ProductPriceIntent", "báo giá giúp mình"),
    ("ProductAvailabilityIntent", "còn hàng iphone 16 không"),
    ("ProductAvailabilityIntent", "còn màu đen không"),
    ("ProductAvailabilityIntent", "máy này hết hàng chưa"),
    ("ProductAvailabilityIntent", "còn bản 256gb không"),
    ("ProductAvailabilityIntent", "có sẵn tại shop không"),
    ("ProductRecommendationIntent", "tư vấn cho mình điện thoại chơi game"),
    ("ProductRecommendationIntent", "mua máy dưới 12 triệu nên chọn gì"),
    ("ProductRecommendationIntent", "cần điện thoại pin khỏe"),
    ("ProductRecommendationIntent", "gợi ý điện thoại chụp ảnh đẹp"),
    ("ProductRecommendationIntent", "sinh viên nên mua máy nào"),
    ("ProductCompareIntent", "iphone 16 với s25 cái nào ngon hơn"),
    ("ProductCompareIntent", "nên chọn xiaomi hay samsung"),
    ("ProductCompareIntent", "so sánh giúp mình 2 máy này"),
    ("ProductCompareIntent", "con nào đáng tiền hơn"),
    ("ProductCompareIntent", "khác nhau chỗ nào"),
    ("ProductSpecIntent", "cấu hình máy này thế nào"),
    ("ProductSpecIntent", "ram bao nhiêu vậy"),
    ("ProductSpecIntent", "dùng chip gì"),
    ("ProductSpecIntent", "màn hình bao nhiêu hz"),
    ("ProductSpecIntent", "có hỗ trợ esim không"),
    ("ProductCameraIntent", "camera có đẹp không"),
    ("ProductCameraIntent", "chụp đêm ổn chứ"),
    ("ProductCameraIntent", "quay video có rung không"),
    ("ProductCameraIntent", "máy nào selfie đẹp"),
    ("ProductCameraIntent", "chụp chân dung ngon không"),
    ("ProductBatteryIntent", "pin dùng được mấy tiếng"),
    ("ProductBatteryIntent", "pin có trâu không"),
    ("ProductBatteryIntent", "sạc đầy mất bao lâu"),
    ("ProductBatteryIntent", "hỗ trợ sạc nhanh bao nhiêu w"),
    ("ProductBatteryIntent", "dùng cả ngày nổi không"),
    ("ProductGamingIntent", "chơi liên quân mượt không"),
    ("ProductGamingIntent", "chiến pubg max setting được không"),
    ("ProductGamingIntent", "máy nào gaming ngon"),
    ("ProductGamingIntent", "chơi genshin ổn không"),
    ("ProductGamingIntent", "có nóng máy không"),
    ("PromotionIntent", "đang có sale gì không"),
    ("PromotionIntent", "hôm nay có ưu đãi gì"),
    ("PromotionIntent", "áp được mã giảm giá không"),
    ("PromotionIntent", "có tặng quà kèm không"),
    ("PromotionIntent", "máy này có khuyến mãi không"),
    ("InstallmentIntent", "trả góp được không"),
    ("InstallmentIntent", "góp 12 tháng được chứ"),
    ("InstallmentIntent", "cần trả trước bao nhiêu"),
    ("InstallmentIntent", "có 0 phần trăm không"),
    ("InstallmentIntent", "trả góp qua thẻ tín dụng nha"),
    ("PaymentMethodIntent", "nhận chuyển khoản không"),
    ("PaymentMethodIntent", "có thanh toán momo không"),
    ("PaymentMethodIntent", "quẹt thẻ được không"),
    ("PaymentMethodIntent", "cod được chứ"),
    ("PaymentMethodIntent", "thanh toán bằng vnpay được không"),
    ("CartAddItemIntent", "thêm iphone 16 vào giỏ"),
    ("CartAddItemIntent", "mua luôn 2 cái"),
    ("CartAddItemIntent", "cho mình đặt 1 máy"),
    ("CartAddItemIntent", "bỏ sản phẩm này vào giỏ"),
    ("CartAddItemIntent", "lấy con này luôn"),
    ("CartViewIntent", "mở giỏ hàng"),
    ("CartViewIntent", "xem giỏ giúp mình"),
    ("CartViewIntent", "trong giỏ còn gì"),
    ("CartViewIntent", "tôi đang mua gì vậy"),
    ("CartViewIntent", "kiểm tra giỏ"),
    ("CartUpdateIntent", "tăng lên 2 sản phẩm"),
    ("CartUpdateIntent", "giảm còn 1 cái"),
    ("CartUpdateIntent", "bỏ sản phẩm này đi"),
    ("CartUpdateIntent", "xóa iphone khỏi giỏ"),
    ("CartUpdateIntent", "sửa giỏ hàng"),
    ("CheckoutStartIntent", "thanh toán luôn"),
    ("CheckoutStartIntent", "đặt hàng ngay"),
    ("CheckoutStartIntent", "mua ngay đi"),
    ("CheckoutStartIntent", "chốt đơn"),
    ("CheckoutStartIntent", "tiến hành thanh toán"),
    ("OrderStatusIntent", "đơn của mình tới đâu rồi"),
    ("OrderStatusIntent", "hàng giao chưa"),
    ("OrderStatusIntent", "check đơn giúp mình"),
    ("OrderStatusIntent", "đơn đang xử lý à"),
    ("OrderStatusIntent", "bao giờ nhận được hàng"),
    ("OrderDetailIntent", "xem chi tiết đơn này"),
    ("OrderDetailIntent", "đơn này gồm gì vậy"),
    ("OrderDetailIntent", "tổng tiền bao nhiêu"),
    ("OrderDetailIntent", "tôi mua những gì"),
    ("OrderDetailIntent", "xem thông tin đơn"),
    ("OrderHistoryIntent", "xem các đơn cũ"),
    ("OrderHistoryIntent", "lịch sử mua hàng"),
    ("OrderHistoryIntent", "những đơn đã đặt"),
    ("OrderHistoryIntent", "đơn trước của tôi đâu"),
    ("OrderHistoryIntent", "xem đơn gần đây"),
    ("OrderCancelIntent", "hủy đơn giúp mình"),
    ("OrderCancelIntent", "mình không lấy nữa"),
    ("OrderCancelIntent", "dừng đơn này đi"),
    ("OrderCancelIntent", "hủy đơn hàng nha"),
    ("OrderCancelIntent", "cancel đơn"),
    ("OrderModifyIntent", "đổi địa chỉ nhận hàng"),
    ("OrderModifyIntent", "sửa số điện thoại"),
    ("OrderModifyIntent", "đổi người nhận"),
    ("OrderModifyIntent", "chỉnh lại đơn hàng"),
    ("OrderModifyIntent", "thay đổi thông tin giao hàng"),
    ("ShippingPolicyIntent", "ship bao nhiêu tiền"),
    ("ShippingPolicyIntent", "giao tới hà nội mất mấy ngày"),
    ("ShippingPolicyIntent", "có giao toàn quốc không"),
    ("ShippingPolicyIntent", "thời gian giao hàng thế nào"),
    ("ShippingPolicyIntent", "ship nhanh được không"),
    ("ShippingTrackingIntent", "theo dõi đơn hàng"),
    ("ShippingTrackingIntent", "tra vận đơn giúp mình"),
    ("ShippingTrackingIntent", "hàng đang ở đâu"),
    ("ShippingTrackingIntent", "shipper giao tới đâu rồi"),
    ("ShippingTrackingIntent", "check hành trình đơn hàng"),
    ("ReturnRequestIntent", "muốn đổi trả sản phẩm"),
    ("ReturnRequestIntent", "máy lỗi thì đổi sao"),
    ("ReturnRequestIntent", "trả hàng được không"),
    ("ReturnRequestIntent", "chính sách đổi trả thế nào"),
    ("ReturnRequestIntent", "đổi máy mới được chứ"),
    ("RefundStatusIntent", "hoàn tiền tới đâu rồi"),
    ("RefundStatusIntent", "đã refund chưa"),
    ("RefundStatusIntent", "khi nào nhận lại tiền"),
    ("RefundStatusIntent", "tiền hoàn về tài khoản chưa"),
    ("RefundStatusIntent", "kiểm tra hoàn tiền"),
    ("WarrantyPolicyIntent", "bảo hành mấy tháng"),
    ("WarrantyPolicyIntent", "chính sách bảo hành sao"),
    ("WarrantyPolicyIntent", "lỗi phần cứng xử lý thế nào"),
    ("WarrantyPolicyIntent", "bảo hành ở đâu"),
    ("WarrantyPolicyIntent", "được bảo hành chính hãng không"),
    ("WarrantyClaimIntent", "gửi bảo hành giúp mình"),
    ("WarrantyClaimIntent", "máy bị lỗi rồi"),
    ("WarrantyClaimIntent", "cần mang đi bảo hành"),
    ("WarrantyClaimIntent", "tạo yêu cầu bảo hành"),
    ("WarrantyClaimIntent", "bảo hành sản phẩm này"),
    ("ComplaintIntent", "mình muốn phản ánh"),
    ("ComplaintIntent", "dịch vụ chán quá"),
    ("ComplaintIntent", "giao hàng lâu vậy"),
    ("ComplaintIntent", "shop xử lý kiểu gì thế"),
    ("ComplaintIntent", "tôi không hài lòng"),
    ("GreetingIntent", "hi"),
    ("GreetingIntent", "alo shop"),
    ("GreetingIntent", "chào shop nha"),
    ("GreetingIntent", "xin chào bạn"),
    ("GreetingIntent", "hello shop"),
    ("StoreInfoIntent", "cửa hàng ở đâu"),
    ("StoreInfoIntent", "có chi nhánh nào không"),
    ("StoreInfoIntent", "mấy giờ mở cửa"),
    ("StoreInfoIntent", "địa chỉ shop là gì"),
    ("StoreInfoIntent", "cuối tuần có mở không"),
    ("HumanHandoffIntent", "cho gặp nhân viên"),
    ("HumanHandoffIntent", "chuyển mình sang tư vấn viên"),
    ("HumanHandoffIntent", "nói chuyện với người thật"),
    ("HumanHandoffIntent", "cần hỗ trợ trực tiếp"),
    ("HumanHandoffIntent", "gặp CSKH"),
    ("FallbackIntent", "kể chuyện ma đi"),
    ("FallbackIntent", "thời tiết hôm nay thế nào"),
    ("FallbackIntent", "ai là tổng thống mỹ"),
    ("FallbackIntent", "hướng dẫn nấu bún bò"),
    ("FallbackIntent", "viết code python cho tôi"),
]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def first_message(response: dict[str, Any]) -> str:
    chunks = []
    for message in response.get("messages") or []:
        content = message.get("content")
        if content:
            chunks.append(str(content))
    return "\n".join(chunks).strip()


def expected_matches(expected: str, actual_lex: str, resolved: str) -> bool:
    if expected == "FallbackIntent":
        return "fallback" in actual_lex.lower() or resolved == "fallback"
    return actual_lex == expected


def main() -> int:
    load_dotenv(ROOT / ".env")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    guest_id = f"guest_lex_smoke_{timestamp}"
    conversation_id = f"conv_lex_smoke_{timestamp}"

    bot_id = os.environ.get("LEX_BOT_ID")
    alias_id = os.environ.get("LEX_BOT_ALIAS_ID")
    locale_id = os.environ.get("LEX_LOCALE_ID", "en_US")
    region = os.environ.get("AWS_REGION", "ap-southeast-1")
    if not bot_id or not alias_id:
        raise RuntimeError("Missing LEX_BOT_ID or LEX_BOT_ALIAS_ID.")

    client = boto3.client("lexv2-runtime", region_name=region)
    rows: list[dict[str, Any]] = []

    print(json.dumps({
        "conversation_id": conversation_id,
        "guest_id": guest_id,
        "bot_id": bot_id,
        "bot_alias_id": alias_id,
        "locale_id": locale_id,
        "case_count": len(CASES),
    }, ensure_ascii=False), flush=True)

    for index, (expected, text) in enumerate(CASES, start=1):
        started = time.perf_counter()
        row: dict[str, Any] = {
            "index": index,
            "expected_intent": expected,
            "text": text,
            "conversation_id": conversation_id,
            "guest_id": guest_id,
        }
        try:
            response = client.recognize_text(
                botId=bot_id,
                botAliasId=alias_id,
                localeId=locale_id,
                sessionId=conversation_id,
                text=text,
                requestAttributes={
                    "conversation_id": conversation_id,
                    "guest_id": guest_id,
                    "channel": "WEB",
                    "session_id": conversation_id,
                    "original_text": text,
                },
            )
            session_state = response.get("sessionState") or {}
            intent = session_state.get("intent") or {}
            attrs = session_state.get("sessionAttributes") or {}
            actual_lex = str(intent.get("name") or "")
            resolved = str(attrs.get("resolved_intent") or "")
            message = first_message(response)
            row.update(
                {
                    "ok": expected_matches(expected, actual_lex, resolved),
                    "actual_lex_intent": actual_lex,
                    "resolved_intent": resolved,
                    "resolution_source": attrs.get("resolution_source"),
                    "search_status": attrs.get("search_status"),
                    "current_product_name": attrs.get("current_product_name"),
                    "current_order_code": attrs.get("current_order_code"),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "message_preview": message.replace("\n", " ")[:240],
                    "error": "",
                }
            )
        except Exception as exc:
            row.update(
                {
                    "ok": False,
                    "actual_lex_intent": "",
                    "resolved_intent": "",
                    "resolution_source": "",
                    "search_status": "",
                    "current_product_name": "",
                    "current_order_code": "",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "message_preview": "",
                    "error": f"{exc.__class__.__name__}: {exc}",
                }
            )
        rows.append(row)
        print(
            f"{index:03d}/{len(CASES)} "
            f"{'OK' if row['ok'] else 'FAIL'} "
            f"expected={expected} actual={row['actual_lex_intent']} "
            f"resolved={row['resolved_intent']} status={row['search_status']} text={text}",
            flush=True,
        )
        time.sleep(0.05)

    json_path = OUTPUT_DIR / f"lex_continuous_intent_smoke_{timestamp}.json"
    csv_path = OUTPUT_DIR / f"lex_continuous_intent_smoke_{timestamp}.csv"
    summary_path = OUTPUT_DIR / f"lex_continuous_intent_smoke_{timestamp}_summary.json"

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    passed = sum(1 for row in rows if row["ok"])
    by_expected: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = by_expected.setdefault(row["expected_intent"], {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += 1 if row["ok"] else 0

    summary = {
        "conversation_id": conversation_id,
        "guest_id": guest_id,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "by_expected_intent": by_expected,
        "json_path": str(json_path),
        "csv_path": str(csv_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if passed == total else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
