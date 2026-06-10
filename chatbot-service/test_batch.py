import asyncio
import traceback
from app.services.intent_service import IntentService
from app.clients.medusa_client import get_medusa_client
from app.clients.gemini_client import get_gemini_client
from app.schemas.lexv2 import LexV2Request


TEST_CASES = [
    # GreetingIntent
    ("Chào bạn", "greeting"),
    ("Xin chào", "greeting"),
    ("Hi shop", "greeting"),
    ("Hey", "greeting"),

    # ProductPriceIntent
    ("iPhone 16 giá bao nhiêu", "product_price"),
    ("áo thun bao tiền", "product_price"),
    ("giá điện thoại Samsung", "product_price"),
    ("Quần jeans bao nhiêu vậy", "product_price"),
    ("son môi bao nhiêu", "product_price"),

    # ProductSearchIntent
    ("tìm giày Nike", "product_search"),
    ("có áo phông trắng không", "product_search"),
    ("cho mình xem váy", "product_search"),
    ("còn hàng không", "inventory"),
    ("sản phẩm cho nam", "product_search"),

    # OrderStatusIntent
    ("kiểm tra đơn hàng", "order_tracking"),
    ("đơn hàng của tôi", "order_tracking"),
    ("ship đến đâu rồi", "shipping_policy"),
    ("đơn hàng 12345", "order_tracking"),

    # CartIntent (không có trong service → product_search hoặc fallback)
    ("thêm vào giỏ hàng", "fallback"),
    ("xem giỏ hàng", "product_search"),
    ("mua hàng", "fallback"),
    ("checkout", "fallback"),

    # ComplaintIntent (không có trong service → fallback hoặc product_search)
    ("hàng không đúng mô tả", "fallback"),
    ("sản phẩm bị lỗi", "product_search"),
    ("tôi muốn khiếu nại", "fallback"),

    # ReturnRefundIntent (không có trong service → fallback)
    ("muốn trả hàng", "fallback"),
    ("hoàn tiền", "fallback"),
    ("đổi size", "fallback"),

    # FallbackIntent (người dùng hỏi lung tung)
    ("ok cậu", "fallback"),
    ("abc xyz 123", "fallback"),
    ("làm sao để nấu phở", "fallback"),
]


async def run_test(questions: list[tuple[str, str]]):
    medusa = get_medusa_client()
    gemini = get_gemini_client()
    service = IntentService(medusa_client=medusa, gemini_client=gemini)

    results = []
    for text, expected_intent in questions:
        try:
            req = LexV2Request(
                sessionState={"intent": {"name": "FallbackIntent"}},
                inputTranscript=text,
                sessionId="test_batch_001"
            )
            res = await service.handle(req)
            actual_intent = res.session_info.parameters.get("resolved_intent", "fallback")
            match = "✓" if actual_intent == expected_intent else "✗"
            response_text = None
            if res.messages:
                response_text = res.messages[0].content
            results.append({
                "text": text,
                "expected": expected_intent,
                "actual": actual_intent,
                "match": match,
                "response_text": response_text,
                "error": None,
            })
        except Exception as e:
            results.append({
                "text": text,
                "expected": expected_intent,
                "actual": "ERROR",
                "match": "✗",
                "dialog_action": None,
                "slots": None,
                "response_text": None,
                "error": str(e),
            })

    return results


async def main():
    print(f"\n{'='*80}")
    print(f"CHẠY {len(TEST_CASES)} TEST CASES")
    print(f"{'='*80}\n")

    results = await run_test(TEST_CASES)

    # Summary
    passed = sum(1 for r in results if r["match"] == "✓")
    failed = sum(1 for r in results if r["match"] == "✗")
    errors = sum(1 for r in results if r["error"])

    print(f"\n{'='*80}")
    print(f"TỔNG KẾT: {passed}/{len(results)} passed, {failed} failed, {errors} errors")
    print(f"{'='*80}\n")

    # Detail by intent
    from collections import defaultdict
    by_intent = defaultdict(list)
    for r in results:
        by_intent[r["expected"]].append(r)

    for intent, items in by_intent.items():
        passed_intent = sum(1 for i in items if i["match"] == "✓")
        print(f"\n[{intent}] {passed_intent}/{len(items)} passed")
        for item in items:
            status = "✓" if item["match"] == "✓" else "✗"
            if item["error"]:
                print(f"  {status} '{item['text']}' -> ERROR: {item['error'][:80]}")
            else:
                print(f"  {status} '{item['text']}' -> {item['actual']}")
                if item["response_text"]:
                    print(f"      Response: {item['response_text'][:100]}")


if __name__ == "__main__":
    asyncio.run(main())
