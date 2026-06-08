from __future__ import annotations

import random
import re
from difflib import SequenceMatcher
from typing import Any

from app.clients.gemini_client import GeminiClient
from app.clients.medusa_client import MedusaClient
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationRequiredError,
    GeminiAPIError,
    MedusaAPIError,
    MedusaTimeoutError,
    OrderNotFoundError,
    MissingOrderCodeError,
    ProductNotFoundError,
)
from app.schemas.lexv2 import (
    DialogflowCXRequest,
    DialogflowCXResponse,
    DialogflowParameterValue,
    SessionInfo,
    rich_response,
    text_response,
)


class IntentService:
    PRODUCT_PARAMETER_NAMES = ["product", "product_name", "productName", "product_title", "item"]
    PRODUCT_A_PARAMETER_NAMES = ["product_a", "productA", "first_product", "firstProduct"]
    PRODUCT_B_PARAMETER_NAMES = ["product_b", "productB", "second_product", "secondProduct"]
    SEARCH_PARAMETER_NAMES = ["query", "search", "keyword", "category", "style", "need", "product_type", "productType"]
    ORDER_PARAMETER_NAMES = ["order_id", "orderId", "order_code", "orderCode", "order"]
    CUSTOMER_TOKEN_PARAMETER_NAMES = [
        "customer_access_token",
        "customerAccessToken",
        "access_token",
        "accessToken",
        "auth_token",
        "authToken",
        "authorization",
    ]
    CONTEXT_PRODUCT_PARAMETER_NAMES = ["current_product_name", "currentProductName"]

    def __init__(self, medusa_client: MedusaClient, gemini_client: GeminiClient | None = None) -> None:
        self.medusa_client = medusa_client
        self.gemini_client = gemini_client

    async def handle(
        self,
        request: DialogflowCXRequest,
        authorization_header: str | None = None,
    ) -> DialogflowCXResponse:
        intent = request.intent_name().lower()
        text_intent = infer_intent_from_text(request.text)
        if not text_intent:
            text_intent = await self._resolve_intent_with_gemini(request, intent)

        try:
            if is_reset_intent(request.text):
                cleared_params = {k: None for k in request_session_parameters(request).keys()}
                cleared_params["search_status"] = "reset_success"
                response = text_response("Đã xoá lịch sử trò chuyện. Mình có thể giúp gì tiếp theo cho bạn?", cleared_params)
                return response
            elif (
                text_intent == "human_handover"
                or "humanhandover" in intent
                or "human_handover" in intent
                or "handover" in intent
            ):
                response = await self.human_handover()
            elif text_intent == "greeting" or "greeting" in intent or intent in {"xin chao", "hello", "hi"}:
                response = await self.greeting()
            elif text_intent in {"top_expensive", "top_cheap", "best_sellers"}:
                response = await self.product_ranking(request, ranking=text_intent)
            elif text_intent == "product_compare" or "productcompare" in intent or "product_compare" in intent:
                response = await self.product_compare(request)
            elif text_intent == "inventory" or "inventory" in intent or "stock" in intent:
                response = await self.inventory_status(request)
            elif text_intent == "product_price" or "productprice" in intent or "product_price" in intent or "price" in intent:
                response = await self.product_price(request)
            elif (
                text_intent == "product_recommendation"
                or "productrecommendation" in intent
                or "product_recommendation" in intent
                or "recommend" in intent
            ):
                response = await self.product_recommendation(request)
            elif text_intent == "bonus" or "bonus" in intent or "promotion" in intent or "discount" in intent or "khuyenmai" in intent:
                response = await self.bonus(request)
            elif text_intent == "shipping_policy" or "shippingpolicy" in intent or "shipping_policy" in intent:
                response = await self.shipping_policy()
            elif text_intent == "warranty_policy" or "warrantypolicy" in intent or "warranty_policy" in intent:
                response = await self.warranty_policy(request)
            elif text_intent == "product_search" or "productsearch" in intent or "product_search" in intent or intent == "search":
                response = await self.product_search(request)
            elif "orderdetail" in intent or "order_detail" in intent:
                response = await self.order_detail(request, authorization_header=authorization_header)
            elif text_intent == "order_list":
                response = await self.order_list(request, authorization_header=authorization_header)
            elif text_intent == "fallback":
                response = await self.fallback()
            elif (
                "orderstatus" in intent
                or "order_status" in intent
                or "ordertracking" in intent
                or "order_tracking" in intent
                or "tracking" in intent
            ):
                if is_order_tracking_request(request):
                    response = await self.order_tracking(request, authorization_header=authorization_header)
                else:
                    response = await self.fallback()
            else:
                response = await self.fallback()
        except AuthenticationRequiredError:
            response = text_response(
                "Bạn cần đăng nhập trước khi tra cứu thông tin đơn hàng. "
                "Mình chỉ có thể trả lời thông tin sản phẩm công khai khi chưa đăng nhập.",
                {"search_status": "authentication_required"},
            )
        except ProductNotFoundError:
            response = text_response(
                "Mình chưa tìm thấy sản phẩm phù hợp. Bạn có thể nhập tên sản phẩm cụ thể hơn không?",
                {"search_status": "product_not_found"},
            )
        except MissingOrderCodeError:
            response = text_response(
                "Bạn vui lòng cung cấp mã đơn hàng (ví dụ: mã số trên email) để mình kiểm tra tình trạng giúp bạn nhé.",
                {"search_status": "missing_order_code"},
            )
        except OrderNotFoundError:
            response = text_response(
                "Mình chưa tìm thấy đơn hàng này. Bạn kiểm tra lại mã đơn hàng giúp mình nhé.",
                {"search_status": "order_not_found"},
            )
        except MedusaTimeoutError:
            response = text_response(
                "Hệ thống đang phản hồi chậm. Bạn vui lòng thử lại sau ít phút nhé.",
                {"search_status": "timeout"},
            )
        except MedusaAPIError as exc:
            if exc.status_code in {401, 403}:
                response = text_response(
                    "Phiên đăng nhập của bạn không hợp lệ hoặc đã hết hạn. Bạn vui lòng đăng nhập lại nhé.",
                    {"search_status": "invalid_authentication"},
                )
            else:
                response = text_response(
                    "Mình chưa thể kết nối hệ thống bán hàng lúc này. Bạn vui lòng thử lại sau.",
                    {"search_status": "medusa_api_error"},
                )

        response.session_info.parameters["resolved_intent"] = text_intent or "fallback"
        response.session_info.parameters["ai_confidence"] = 0.5 if (text_intent == "fallback" or not text_intent) else 1.0

        return await self._finalize_response(request, intent, response)

    async def greeting(self) -> DialogflowCXResponse:
        greetings = [
            "Xin chào! Mình là Medusan, trợ lý ảo của shop. Mình có thể giúp gì cho bạn hôm nay?",
            "Chào bạn, mình là Medusan. Mình có thể hỗ trợ bạn tìm điện thoại hoặc kiểm tra đơn hàng ạ?",
            "Medusan xin chào! Bạn cần hỗ trợ tư vấn sản phẩm hay hỏi về khuyến mãi không?",
            "Hi bạn, mình là trợ lý Medusan. Mình có thể hỗ trợ bạn tra giá, kiểm tra tồn kho hoặc trạng thái đơn hàng nhé!"
        ]
        return text_response(random.choice(greetings))

    async def fallback(self) -> DialogflowCXResponse:
        return text_response("Mình chưa hiểu yêu cầu của bạn. Bạn có thể hỏi giá sản phẩm hoặc trạng thái đơn hàng nhé.")

    async def shipping_policy(self) -> DialogflowCXResponse:
        return text_response(
            "\n".join(
                [
                    "Chính sách giao hàng của shop:",
                    "- Giao hàng tiêu chuẩn: 2-3 ngày, phí 50.000 VNĐ.",
                    "- Giao nhanh: trong ngày hoặc trong 24 giờ, phí 120.000 VNĐ.",
                    "- Mã FREESHIP có thể miễn hoặc giảm phí vận chuyển nếu đơn đủ điều kiện.",
                    "- Shop hỗ trợ giao hàng toàn quốc cho các sản phẩm demo.",
                ]
            ),
            {
                "search_status": "shipping_policy",
                "standard_shipping_fee": "50.000 VNĐ",
                "express_shipping_fee": "120.000 VNĐ",
                "free_shipping_code": "FREESHIP",
            },
        )

    async def warranty_policy(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        product_name = self._resolve_product_name(request)
        product_title = None
        warranty_months = 12

        if product_name:
            products = await self.medusa_client.list_products(query=product_name, limit=8)
            product = self._find_best_product(product_name, products) if products else None
            if product:
                product_title = product.get("title") or product_name
                metadata = product.get("metadata") or {}
                raw_months = metadata.get("warranty_months")
                if raw_months:
                    warranty_months = int(raw_months)

        subject = f"{product_title} đang" if product_title else "Các điện thoại demo đang"
        return text_response(
            "\n".join(
                [
                    f"{subject} được bảo hành {warranty_months} tháng.",
                    "Chính sách đổi trả:",
                    "- Hỗ trợ đổi trả trong 7 ngày nếu máy lỗi, giao sai màu/phiên bản, hoặc hư hỏng khi vận chuyển.",
                    "- Máy còn nguyên seal có thể được xem xét đổi trả theo điều kiện của shop.",
                    "- Khi bảo hành hoặc đổi trả cần thông tin đơn hàng/hóa đơn.",
                ]
            ),
            {
                "search_status": "warranty_policy",
                "current_product_name": product_title,
                "warranty_months": warranty_months,
                "return_window_days": 7,
            },
        )

    async def _finalize_response(
        self,
        request: DialogflowCXRequest,
        intent: str,
        response: DialogflowCXResponse,
    ) -> DialogflowCXResponse:
        merge_session_parameters(request, response)

        lex_intent_name = "FallbackIntent"
        if request.session_state.get("intent") and request.session_state["intent"].get("name"):
            lex_intent_name = request.session_state["intent"]["name"]
        
        response.sessionState.intent.name = lex_intent_name

        if not self.gemini_client or not self.gemini_client.is_enabled():
            return response

        text_message = first_text_message(response)
        if not text_message:
            return response

        try:
            rewritten = await self.gemini_client.rewrite_customer_reply(
                intent=intent,
                user_text=request.text,
                draft_reply=text_message,
                session_parameters=response.session_info.parameters if response.session_info else None,
                payload=first_payload(response),
            )
        except GeminiAPIError:
            return response

        response.fulfillment_response.messages[0].text.text[0] = rewritten
        return response

    async def _resolve_intent_with_gemini(
        self,
        request: DialogflowCXRequest,
        lex_intent: str,
    ) -> str | None:
        if (
            not self.gemini_client
            or not self.gemini_client.is_enabled()
            or not hasattr(self.gemini_client, "resolve_customer_intent")
        ):
            return None

        try:
            resolution = await self.gemini_client.resolve_customer_intent(
                lex_intent=lex_intent,
                user_text=request.text,
                session_parameters=request_session_parameters(request),
            )
        except GeminiAPIError:
            return None

        confidence = parse_confidence(resolution.get("confidence"))
        resolved_intent = normalize_resolved_intent(resolution.get("intent"))
        if confidence < 0.65 or not resolved_intent:
            return None

        product_name = clean_optional_text(resolution.get("product_name"))
        if product_name:
            set_request_parameter(request, "product_name", product_name)

        product_b_name = clean_optional_text(resolution.get("product_b_name"))
        if product_b_name:
            set_request_parameter(request, "product_b", product_b_name)

        order_code = clean_optional_text(resolution.get("order_code"))
        if order_code:
            set_request_parameter(request, "order_id", order_code)

        return resolved_intent

    async def human_handover(self) -> DialogflowCXResponse:
        return text_response(
            "Mình sẽ chuyển bạn sang nhân viên hỗ trợ. Bạn có thể để lại số điện thoại hoặc email để shop liên hệ lại nhé.",
            {
                "handover_requested": True,
                "search_status": "human_handover",
            },
        )

    async def product_price(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        product_name = self._resolve_product_name(request)
        if not product_name:
            raise ProductNotFoundError()

        products = await self.medusa_client.list_products(query=product_name)
        if not products:
            products = await self.medusa_client.list_products()

        product = self._find_best_product(product_name, products)
        if not product:
            raise ProductNotFoundError()

        prices = self._extract_variant_prices(product)
        if not prices:
            return text_response(
                f"Mình tìm thấy {product.get('title', 'sản phẩm này')} nhưng chưa có thông tin giá.",
                {
                    "current_product_name": product.get("title", product_name),
                    "search_status": "missing_price",
                },
            )

        title = product.get("title", product_name)
        return self._product_detail_response(product, title, prices)

    async def product_search(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        query = request.get_parameter(self.SEARCH_PARAMETER_NAMES + self.PRODUCT_PARAMETER_NAMES)
        query = query or extract_product_search_query_from_text(request.text)
        products = await self.medusa_client.list_products(query=query, limit=8)
        if not products and query:
            products = await self.medusa_client.list_products(limit=8)
            ranked_products = self._rank_products(query, products)
            products = ranked_products[:5] if ranked_products else products[:5]

        if not products:
            raise ProductNotFoundError()

        return self._products_list_response(
            products[:5],
            title="Sản phẩm phù hợp",
            intro="Mình tìm thấy một số sản phẩm phù hợp:",
            status="success",
            query=query,
        )

    async def product_recommendation(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        query = request.get_parameter(self.SEARCH_PARAMETER_NAMES + self.PRODUCT_PARAMETER_NAMES)
        query = query or extract_product_search_query_from_text(request.text)
        products = await self.medusa_client.list_products(query=query, limit=12)
        if not products:
            products = await self.medusa_client.list_products(limit=12)

        if query:
            products = self._rank_products(query, products) or products

        if not products:
            raise ProductNotFoundError()

        return self._products_list_response(
            products[:4],
            title="Gợi ý sản phẩm",
            intro="Dựa trên nhu cầu của bạn, mình gợi ý các sản phẩm này:",
            status="recommendation_success",
            query=query,
        )

    async def inventory_status(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        product_name = self._resolve_product_name(request)
        print(f"DEBUG INVENTORY: resolved product_name='{product_name}'", flush=True)
        if not product_name:
            raise ProductNotFoundError()

        products = await self.medusa_client.list_products(query=product_name, limit=8)
        if not products:
            products = await self.medusa_client.list_products(limit=50)

        product = self._find_best_product(product_name, products)
        if not product:
            raise ProductNotFoundError()

        variants = product.get("variants", []) or []
        available_variants = [
            variant
            for variant in variants
            if variant.get("manage_inventory") is False or variant.get("allow_backorder") or not variant.get("deleted_at")
        ]
        title = product.get("title") or product_name
        variant_count = len(available_variants)

        if variant_count:
            sample_variants = ", ".join(str(variant.get("title") or "Default") for variant in available_variants[:6])
            extra = "" if variant_count <= 6 else f" và {variant_count - 6} phiên bản khác"
            message = (
                f"{title} hiện đang có hàng trên hệ thống với {variant_count} phiên bản"
                f" ({sample_variants}{extra}). Bạn có thể vào trang sản phẩm để chọn màu và dung lượng cụ thể."
            )
            status = "in_stock"
        else:
            message = f"{title} hiện chưa có phiên bản khả dụng trên hệ thống."
            status = "out_of_stock"

        return text_response(
            message,
            {
                "current_product_id": product.get("id"),
                "current_product_handle": product.get("handle"),
                "current_product_name": title,
                "inventory_status": status,
                "variant_count": variant_count,
                "search_status": "success",
            },
        )

    async def product_compare(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        product_a_name = request.get_parameter(self.PRODUCT_A_PARAMETER_NAMES)
        product_b_name = request.get_parameter(self.PRODUCT_B_PARAMETER_NAMES)

        if not product_a_name or not product_b_name:
            extracted = extract_product_compare_names_from_text(request.text)
            product_a_name = product_a_name or extracted[0]
            product_b_name = product_b_name or extracted[1]

        if not product_a_name and not product_b_name:
            product_b_name = extract_single_compare_target_from_text(request.text)
            if product_b_name:
                product_a_name = request.get_parameter(self.CONTEXT_PRODUCT_PARAMETER_NAMES)
        elif not product_a_name and product_b_name:
            product_a_name = request.get_parameter(self.CONTEXT_PRODUCT_PARAMETER_NAMES)
        elif product_a_name and not product_b_name:
            product_b_name = extract_single_compare_target_from_text(request.text)

        if not product_a_name or not product_b_name:
            raise ProductNotFoundError()

        products = await self.medusa_client.list_products(limit=100)
        product_a = self._find_best_product(product_a_name, products)
        product_b = self._find_best_product(product_b_name, products)
        if not product_a or not product_b:
            raise ProductNotFoundError()

        return self._product_compare_response(product_a, product_b)

    async def product_ranking(self, request: DialogflowCXRequest, ranking: str) -> DialogflowCXResponse:
        limit = extract_limit_from_text(request.text) or 5
        products = await self.medusa_client.list_products(limit=100)
        priced_products = []

        for product in products:
            prices = self._extract_variant_prices(product)
            if not prices:
                continue
            lowest = min(prices, key=lambda item: float(item["amount"]))
            priced_products.append((float(lowest["amount"]), product))

        if not priced_products:
            raise ProductNotFoundError()

        if ranking == "best_sellers":
            sorted_products = self._sort_best_seller_products([product for _, product in priced_products])
            title = "Sản phẩm bán chạy nhất"
        else:
            reverse = ranking == "top_expensive"
            sorted_products = [
                product
                for _, product in sorted(priced_products, key=lambda item: item[0], reverse=reverse)
            ]
            title = "Top sản phẩm giá cao nhất" if reverse else "Top sản phẩm giá thấp nhất"

        intro = (
            f"Mình gợi ý {min(limit, len(sorted_products))} sản phẩm nổi bật:"
            if ranking == "best_sellers"
            else f"Mình tìm thấy {min(limit, len(sorted_products))} sản phẩm theo mức giá:"
        )
        return self._products_list_response(
            sorted_products[:limit],
            title=title,
            intro=intro,
            status=ranking,
        )

    async def order_list(
        self,
        request: DialogflowCXRequest,
        authorization_header: str | None = None,
    ) -> DialogflowCXResponse:
        customer_access_token = authorization_header or request.get_parameter(self.CUSTOMER_TOKEN_PARAMETER_NAMES)
        if not customer_access_token:
            raise AuthenticationRequiredError()

        orders = await self.medusa_client.list_customer_orders(customer_access_token=customer_access_token, limit=5)
        if not orders:
            return text_response(
                "Mình chưa thấy đơn hàng nào trong tài khoản của bạn.",
                {
                    "order_count": 0,
                    "search_status": "success",
                },
            )

        lines = ["Các đơn hàng gần đây của bạn:", ""]
        for order in orders:
            display_code = self._display_order_code(order, str(order.get("id") or "đơn hàng"))
            status = self._humanize_order_status(order)
            total = order.get("total")
            currency = order.get("currency_code")
            total_text = format_money(total, currency) if total is not None and currency else "Chưa cập nhật"
            lines.append(f"- {display_code}: {status}, tổng tiền {total_text}")

        return text_response(
            "\n".join(lines),
            {
                "order_count": len(orders),
                "search_status": "success",
            },
        )

    async def bonus(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        promo_code = request.get_parameter(["promo_code", "promoCode", "code"])
        if promo_code:
            return text_response(
                promotion_code_message(promo_code),
                {
                    "promotion_code": promo_code.upper(),
                    "promotion_status": "available",
                    "search_status": "promotion_success",
                },
            )

        query = request.get_parameter(self.SEARCH_PARAMETER_NAMES + self.PRODUCT_PARAMETER_NAMES)
        query = query or extract_promotion_product_from_text(request.text)
        if not query and not is_generic_promotion_request(request.text):
            query = extract_product_search_query_from_text(request.text)
        query = query or request.get_parameter(self.CONTEXT_PRODUCT_PARAMETER_NAMES)
        if not query:
            return text_response(
                "Các mã khuyến mãi hiện có gồm WELCOME10, ANDROID15, PHONE500K, FREESHIP và PREORDER17. "
                "Bạn có thể hỏi chi tiết từng mã, ví dụ: mã FREESHIP dùng được không?",
                {
                    "promotion_status": "available",
                    "search_status": "promotion_codes_available",
                },
            )

        products = await self.medusa_client.list_products(query=query, limit=20)
        if not products and query:
            products = await self.medusa_client.list_products(limit=20)

        discounted_products = [
            product
            for product in products
            if self._product_has_promotion(product)
        ]

        if discounted_products:
            return self._products_list_response(
                discounted_products[:5],
                title="Sản phẩm đang khuyến mãi",
                intro="Mình tìm thấy các sản phẩm đang có ưu đãi:",
                status="promotion_success",
                query=query,
            )

        return text_response(
            "Hiện mình chưa thấy chương trình khuyến mãi áp dụng cho nhóm sản phẩm này. Bạn vẫn có thể hỏi mình giá từng sản phẩm cụ thể nhé.",
            {
                "promotion_status": "none",
                "search_status": "promotion_not_found",
            },
        )

    async def order_tracking(
        self,
        request: DialogflowCXRequest,
        authorization_header: str | None = None,
    ) -> DialogflowCXResponse:
        order_code = request.get_parameter(self.ORDER_PARAMETER_NAMES)
        
        if not order_code:
            customer_access_token = authorization_header or request.get_parameter(self.CUSTOMER_TOKEN_PARAMETER_NAMES)
            if not customer_access_token:
                raise AuthenticationRequiredError()
                
            orders = await self.medusa_client.list_customer_orders(customer_access_token=customer_access_token, limit=10)
            
            active_orders = []
            for o in orders:
                fulfillment_status = o.get("fulfillment_status", "not_fulfilled")
                status = o.get("status", "pending")
                if status not in ["completed", "canceled", "archived"] and fulfillment_status not in ["delivered", "canceled"]:
                    active_orders.append(o)
            
            if not active_orders:
                return text_response(
                    "Hiện tại bạn không có đơn hàng nào đang trong quá trình giao.",
                    {"search_status": "success"}
                )
                
            if len(active_orders) == 1:
                order = active_orders[0]
                status_text = self._humanize_order_status(order)
                display_code = self._display_order_code(order, str(order.get("id") or "đơn hàng"))
                return text_response(
                    f"Đơn hàng {display_code} hiện {status_text}.",
                    {
                        "current_order_code": display_code,
                        "current_order_status": status_text,
                        "search_status": "success",
                    },
                )
                
            lines = ["Bạn có các đơn hàng đang giao sau đây:", ""]
            for o in active_orders:
                display_code = self._display_order_code(o, str(o.get("id") or "đơn hàng"))
                status_text = self._humanize_order_status(o)
                total = o.get("total")
                currency = o.get("currency_code")
                total_text = format_money(total, currency) if total is not None and currency else "Chưa cập nhật"
                lines.append(f"- **{display_code}**: {status_text}, tổng tiền {total_text}")
                
            return text_response(
                "\n".join(lines),
                {"search_status": "success", "order_count": len(active_orders)}
            )

        order = await self._load_customer_order(request, authorization_header)
        order_code = str(order.get("id") or "đơn hàng")
        if request.get_parameter(self.ORDER_PARAMETER_NAMES):
            order_code = request.get_parameter(self.ORDER_PARAMETER_NAMES)

        status = self._humanize_order_status(order)
        display_code = self._display_order_code(order, order_code)
        return text_response(
            f"Đơn hàng {display_code} hiện {status}.",
            {
                "current_order_code": display_code,
                "current_order_status": status,
                "search_status": "success",
            },
        )

    async def order_detail(
        self,
        request: DialogflowCXRequest,
        authorization_header: str | None = None,
    ) -> DialogflowCXResponse:
        order = await self._load_customer_order(request, authorization_header)
        order_code = self._display_order_code(order, request.get_parameter(self.ORDER_PARAMETER_NAMES) or "đơn hàng")
        status = self._humanize_order_status(order)
        total = order.get("total")
        currency = order.get("currency_code")
        total_text = format_money(total, currency) if total is not None and currency else "Chưa cập nhật"
        created_at = str(order.get("created_at") or "Chưa cập nhật")

        return text_response(
            "\n".join(
                [
                    f"Thông tin {order_code}:",
                    f"- Trạng thái: {status}",
                    f"- Thanh toán: {order.get('payment_status') or 'Chưa cập nhật'}",
                    f"- Giao hàng: {order.get('fulfillment_status') or 'Chưa cập nhật'}",
                    f"- Tổng tiền: {total_text}",
                    f"- Ngày tạo: {created_at}",
                ]
            ),
            {
                "current_order_code": order_code,
                "current_order_status": status,
                "current_order_total": total_text,
                "search_status": "success",
            },
        )

    async def _load_customer_order(
        self,
        request: DialogflowCXRequest,
        authorization_header: str | None = None,
    ) -> dict[str, Any]:
        order_code = request.get_parameter(self.ORDER_PARAMETER_NAMES)
        customer_access_token = authorization_header or request.get_parameter(self.CUSTOMER_TOKEN_PARAMETER_NAMES)

        if not order_code:
            raise MissingOrderCodeError()

        if not customer_access_token:
            raise AuthenticationRequiredError()

        order = await self.medusa_client.find_customer_order(order_code, customer_access_token=customer_access_token)
        if not order:
            raise OrderNotFoundError()
        return order

    @staticmethod
    def _find_best_product(query: str, products: list[dict[str, Any]]) -> dict[str, Any] | None:
        normalized_query = normalize_text(query)
        best_product: dict[str, Any] | None = None
        best_score = 0.0

        for product in products:
            title = normalize_text(str(product.get("title", "")))
            handle = normalize_text(str(product.get("handle", "")))
            haystack = f"{title} {handle}".strip()

            if not haystack:
                continue
            if normalized_query in haystack or haystack in normalized_query:
                score = 1.0
            else:
                score = SequenceMatcher(None, normalized_query, haystack).ratio()

            if score > best_score:
                best_score = score
                best_product = product

        return best_product if best_score >= 0.35 else None

    def _rank_products(self, query: str, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_query = normalize_text(query)
        scored: list[tuple[float, dict[str, Any]]] = []

        for product in products:
            title = normalize_text(str(product.get("title", "")))
            handle = normalize_text(str(product.get("handle", "")))
            description = normalize_text(str(product.get("description", "")))
            haystack = f"{title} {handle} {description}".strip()
            if not haystack:
                continue
            score = 1.0 if normalized_query in haystack else SequenceMatcher(None, normalized_query, haystack).ratio()
            scored.append((score, product))

        return [product for score, product in sorted(scored, key=lambda item: item[0], reverse=True) if score >= 0.25]

    def _sort_best_seller_products(self, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(products, key=best_seller_score, reverse=True)

    @staticmethod
    def _extract_variant_prices(product: dict[str, Any]) -> list[dict[str, Any]]:
        prices: list[dict[str, Any]] = []
        for variant in product.get("variants", []) or []:
            calculated_price = variant.get("calculated_price")
            if calculated_price:
                amount = calculated_price.get("calculated_amount") or calculated_price.get("original_amount")
                original_amount = calculated_price.get("original_amount") or amount
                currency = calculated_price.get("currency_code")
                if amount is not None and currency:
                    prices.append(
                        {
                            "variant": variant.get("title") or "Default",
                            "amount": amount,
                            "original_amount": original_amount,
                            "currency": currency,
                        }
                    )
                    continue

            for price in variant.get("prices", []) or []:
                amount = price.get("amount")
                currency = price.get("currency_code")
                if amount is not None and currency:
                    prices.append(
                        {
                            "variant": variant.get("title") or "Default",
                            "amount": amount,
                            "original_amount": amount,
                            "currency": currency,
                        }
                    )

        return prices

    def _product_detail_response(
        self,
        product: dict[str, Any],
        title: str,
        prices: list[dict[str, Any]],
    ) -> DialogflowCXResponse:
        lowest = min(prices, key=lambda item: float(item["amount"]))
        price_text = format_money(lowest["amount"], lowest["currency"])
        product_url = build_product_url(product)
        image_url = product.get("thumbnail") or first_image_url(product)
        material = product.get("material") or "Chưa cập nhật"
        sizes = sorted({str(item["variant"]) for item in prices})
        size_text = ", ".join(sizes)
        discount_text = product_promotion_hint(product)
        variant_lines = build_variant_price_lines(prices)

        markdown = "\n".join(
            [
                f"### {title}",
                "",
                f"![{title}]({image_url})" if image_url else "",
                "",
                f"**Giá từ:** {price_text}",
                f"**Khuyến mãi:** {discount_text}",
                f"**Size:** {size_text}",
                f"**Chất liệu:** {material}",
                "",
                "**Bảng giá theo size:**",
                *variant_lines,
                "",
                f"[Xem chi tiết sản phẩm]({product_url})",
            ]
        ).strip()

        payload = {
            "richContent": [
                [
                    *(
                        [
                            {
                                "type": "image",
                                "rawUrl": image_url,
                                "accessibilityText": title,
                            }
                        ]
                        if image_url
                        else []
                    ),
                    {
                        "type": "info",
                        "title": title,
                        "subtitle": f"Giá từ {price_text}\nKhuyến mãi: {discount_text}\nSize: {size_text}",
                        "actionLink": product_url,
                    },
                    {
                        "type": "chips",
                        "options": [
                            {
                                "text": "Xem sản phẩm",
                                "link": product_url,
                            }
                        ],
                    },
                ]
            ],
            "product": {
                "id": product.get("id"),
                "handle": product.get("handle"),
                "title": title,
                "url": product_url,
                "image": image_url,
                "price_from": price_text,
                "discount": discount_text,
                "variants": [
                    {
                        "title": item["variant"],
                        "price": format_money(item["amount"], item["currency"]),
                        "original_price": format_money(item["original_amount"], item["currency"]),
                    }
                    for item in prices
                ],
            },
        }

        return rich_response(
            markdown,
            payload,
            {
                "current_product_id": product.get("id"),
                "current_product_handle": product.get("handle"),
                "current_product_name": title,
                "current_product_price": price_text,
                "current_product_url": product_url,
                "search_status": "success",
            },
        )

    def _resolve_product_name(self, request: DialogflowCXRequest) -> str | None:
        explicit_product = request.get_parameter(self.PRODUCT_PARAMETER_NAMES)
        if explicit_product:
            return explicit_product

        extracted_product = extract_product_name_from_text(request.text)
        if extracted_product and not is_generic_product_reference(extracted_product):
            return extracted_product

        context_product = request.get_parameter(self.CONTEXT_PRODUCT_PARAMETER_NAMES)
        if context_product:
            return context_product
            
        history = request.get_parameter(["history_products"])
        if history:
            items = [x.strip() for x in str(history).split("|") if x.strip()]
            if items:
                return items[0]

        return None

    def _products_list_response(
        self,
        products: list[dict[str, Any]],
        *,
        title: str,
        intro: str,
        status: str,
        query: str | None = None,
    ) -> DialogflowCXResponse:
        cards = []
        lines = [title, "", intro]
        product_payloads = []

        for product in products:
            prices = self._extract_variant_prices(product)
            lowest = min(prices, key=lambda item: float(item["amount"])) if prices else None
            price_text = format_money(lowest["amount"], lowest["currency"]) if lowest else "Chưa cập nhật giá"
            product_title = product.get("title") or "Sản phẩm"
            product_url = build_product_url(product)
            image_url = product.get("thumbnail") or first_image_url(product)
            discount_text = product_promotion_hint(product)

            lines.append(f"- {product_title}: {price_text} - Ưu đãi: {discount_text}")
            if image_url:
                cards.append(
                    {
                        "type": "image",
                        "rawUrl": image_url,
                        "accessibilityText": product_title,
                    }
                )
            cards.append(
                {
                    "type": "info",
                    "title": product_title,
                    "subtitle": f"Giá từ {price_text}\nKhuyến mãi: {discount_text}",
                    "actionLink": product_url,
                }
            )
            product_payloads.append(
                {
                    "id": product.get("id"),
                    "handle": product.get("handle"),
                    "title": product_title,
                    "url": product_url,
                    "image": image_url,
                    "price_from": price_text,
                    "discount": discount_text,
                }
            )

        payload = {
            "richContent": [cards],
            "products": product_payloads,
        }
        parameters = {
            "search_status": status,
            "result_count": len(products),
        }
        if query:
            parameters["current_search_query"] = query
        if len(products) == 1:
            product = products[0]
            product_title = product.get("title")
            if product_title:
                parameters["current_product_name"] = product_title
            if product.get("id"):
                parameters["current_product_id"] = product.get("id")
            if product.get("handle"):
                parameters["current_product_handle"] = product.get("handle")
        if product_payloads:
            parameters["last_product_names"] = " | ".join(product["title"] for product in product_payloads[:5])

        return rich_response("\n".join(lines), payload, parameters)

    def _product_compare_response(
        self,
        product_a: dict[str, Any],
        product_b: dict[str, Any],
    ) -> DialogflowCXResponse:
        title_a = product_a.get("title") or "Sản phẩm A"
        title_b = product_b.get("title") or "Sản phẩm B"
        prices_a = self._extract_variant_prices(product_a)
        prices_b = self._extract_variant_prices(product_b)
        price_a = lowest_price_text(prices_a)
        price_b = lowest_price_text(prices_b)
        metadata_a = product_a.get("metadata") or {}
        metadata_b = product_b.get("metadata") or {}

        comparison_fields = [
            ("Giá từ", price_a, price_b),
            ("Chip/hiệu năng", metadata_text(metadata_a, ["chip", "performance", "ai_features"]), metadata_text(metadata_b, ["chip", "performance", "ai_features"])),
            ("Camera", metadata_text(metadata_a, ["camera"]), metadata_text(metadata_b, ["camera"])),
            ("Pin/sạc", metadata_text(metadata_a, ["battery", "charging"]), metadata_text(metadata_b, ["battery", "charging"])),
            ("Điểm nổi bật", metadata_text(metadata_a, ["form_factor", "stylus", "design", "use_case", "audience"]), metadata_text(metadata_b, ["form_factor", "stylus", "design", "use_case", "audience"])),
            ("Khuyến mãi gợi ý", product_promotion_hint(product_a), product_promotion_hint(product_b)),
            ("Đánh giá", rating_text(metadata_a), rating_text(metadata_b)),
        ]

        lines = [
            f"So sánh nhanh {title_a} và {title_b}:",
            "",
            f"| Tiêu chí | {title_a} | {title_b} |",
            "|---|---|---|",
        ]
        lines.extend(f"| {label} | {left} | {right} |" for label, left, right in comparison_fields)
        lines.extend(
            [
                "",
                build_compare_recommendation(title_a, title_b, metadata_a, metadata_b, prices_a, prices_b),
            ]
        )

        return text_response(
            "\n".join(lines),
            {
                "search_status": "compare_success",
                "product_a_name": title_a,
                "product_b_name": title_b,
                "product_a_price": price_a,
                "product_b_price": price_b,
            },
        )

    def _product_has_promotion(self, product: dict[str, Any]) -> bool:
        return any(has_discount(price) for price in self._extract_variant_prices(product))

    @staticmethod
    def _humanize_order_status(order: dict[str, Any]) -> str:
        fulfillment_status = str(order.get("fulfillment_status") or "").lower()
        payment_status = str(order.get("payment_status") or "").lower()
        order_status = str(order.get("status") or "").lower()

        if fulfillment_status in {"shipped", "partially_shipped"}:
            return "đang được giao"
        if fulfillment_status in {"delivered"}:
            return "đã giao thành công"
        if fulfillment_status in {"canceled", "cancelled"} or order_status in {"canceled", "cancelled"}:
            return "đã bị hủy"
        if payment_status in {"captured", "paid"}:
            return "đã thanh toán và đang được xử lý"
        if payment_status in {"awaiting", "not_paid"}:
            return "đang chờ thanh toán"
        return "đang được xử lý"

    @staticmethod
    def _display_order_code(order: dict[str, Any], fallback: str) -> str:
        display_id = order.get("display_id")
        if display_id:
            return f"ORD-{display_id}"
        return fallback


def normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def first_text_message(response: DialogflowCXResponse) -> str | None:
    if not response.fulfillment_response.messages:
        return None
    message = response.fulfillment_response.messages[0]
    if not message.text or not message.text.text:
        return None
    return message.text.text[0]


def first_payload(response: DialogflowCXResponse) -> dict[str, Any] | None:
    for message in response.fulfillment_response.messages:
        if message.payload:
            return message.payload
    return None


def merge_session_parameters(request: DialogflowCXRequest, response: DialogflowCXResponse) -> None:
    merged = request_session_parameters(request)
    if response.session_info:
        for key, value in response.session_info.parameters.items():
            unwrapped = unwrap_parameter_value(value)
            if unwrapped is not None:
                merged[key] = unwrapped
            else:
                if key in merged:
                    merged[key] = None

    if "current_product_name" in merged and merged["current_product_name"]:
        current = str(merged["current_product_name"])
        history = str(merged.get("history_products") or "")
        history_list = [x.strip() for x in history.split("|") if x.strip()]
        
        if current in history_list:
            history_list.remove(current)
        history_list.insert(0, current)
        
        history_list = history_list[:10]
        merged["history_products"] = " | ".join(history_list)

    if merged:
        response.session_info = SessionInfo(parameters=merged)


def request_session_parameters(request: DialogflowCXRequest) -> dict[str, Any]:
    if not request.session_info:
        return {}

    parameters: dict[str, Any] = {}
    for key, value in request.session_info.parameters.items():
        unwrapped = unwrap_parameter_value(value)
        if unwrapped is not None:
            parameters[key] = unwrapped
    return parameters


def unwrap_parameter_value(value: Any) -> Any | None:
    if isinstance(value, DialogflowParameterValue):
        return value.resolved_value if value.resolved_value is not None else value.original_value
    if isinstance(value, dict):
        return value.get("resolvedValue") if value.get("resolvedValue") is not None else value.get("originalValue")
    return value


def set_request_parameter(request: DialogflowCXRequest, name: str, value: Any) -> None:
    if not request.session_info:
        request.session_info = SessionInfo(parameters={})
    request.session_info.parameters[name] = value


def parse_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_resolved_intent(value: Any) -> str | None:
    if not value:
        return None

    normalized = normalize_text(str(value))
    aliases = {
        "product search": "product_search",
        "product price": "product_price",
        "product recommendation": "product_recommendation",
        "promotion": "bonus",
        "bonus": "bonus",
        "inventory": "inventory",
        "product compare": "product_compare",
        "warranty": "warranty_policy",
        "warranty policy": "warranty_policy",
        "shipping": "shipping_policy",
        "shipping policy": "shipping_policy",
        "order status": "order_tracking",
        "order tracking": "order_tracking",
        "order list": "order_list",
        "human handover": "human_handover",
        "greeting": "greeting",
        "fallback": "fallback",
    }
    resolved = aliases.get(normalized, normalized.replace(" ", "_"))
    allowed = {
        "greeting",
        "product_search",
        "product_price",
        "product_recommendation",
        "bonus",
        "inventory",
        "product_compare",
        "warranty_policy",
        "shipping_policy",
        "order_tracking",
        "order_list",
        "human_handover",
        "fallback",
    }
    return resolved if resolved in allowed else None


def clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return None
    return text


def is_generic_product_reference(value: str) -> bool:
    normalized = normalize_text(value)
    generic_values = {
        "gia",
        "giá",
        "bao nhieu",
        "bao nhiêu",
        "gia bao nhieu",
        "giá bao nhiêu",
        "san pham",
        "sản phẩm",
        "dien thoai",
        "điện thoại",
    }
    return normalized in generic_values


def infer_intent_from_text(text: str | None) -> str | None:
    normalized = normalize_text(text or "")
    if not normalized:
        return None

    if any(keyword in normalized for keyword in ["gap nhan vien", "gặp nhân viên", "tu van vien", "tư vấn viên", "nguoi that", "người thật", "ho tro truc tiep", "hỗ trợ trực tiếp", "chuyen cho sale", "chuyển cho sale"]):
        return "human_handover"
    if any(keyword in normalized for keyword in ["so sanh", "so sánh", "khac nhau", "khác nhau", "tot hon", "tốt hơn", "nen mua", "nên mua"]) and any(separator in normalized for separator in [" va ", " và ", " voi ", " với "]):
        return "product_compare"
    if any(keyword in normalized for keyword in ["con hang", "còn hàng", "co san", "có sẵn", "ton kho", "tồn kho", "het hang", "hết hàng"]):
        return "inventory"
    if any(keyword in normalized for keyword in ["don nao", "đơn nào", "don hang nao", "đơn hàng nào", "co dat don", "có đặt đơn", "toi co dat", "tôi có đặt"]):
        return "order_list"
    if any(keyword in normalized for keyword in ["ban chay", "bán chạy", "hot nhat", "hot nhất", "pho bien", "phổ biến", "mua nhieu", "mua nhiều"]):
        return "best_sellers"
    if any(keyword in normalized for keyword in ["top", "cao nhat", "cao nhất", "dat nhat", "đắt nhất", "gia cao", "giá cao"]):
        if any(keyword in normalized for keyword in ["re nhat", "rẻ nhất", "gia thap", "giá thấp", "thap nhat", "thấp nhất"]):
            return "top_cheap"
        if any(keyword in normalized for keyword in ["cao nhat", "cao nhất", "dat nhat", "đắt nhất", "gia cao", "giá cao"]):
            return "top_expensive"
    if any(keyword in normalized for keyword in ["re nhat", "rẻ nhất", "gia thap", "giá thấp", "thap nhat", "thấp nhất"]):
        return "top_cheap"
    greeting_phrases = {"xin chao", "xin chào", "chao shop", "chào shop", "hello", "hi"}
    if normalized in greeting_phrases or normalized.startswith(("xin chao ", "xin chào ", "chao ", "chào ")):
        return "greeting"
    if any(keyword in normalized for keyword in ["giao hang", "giao hàng", "van chuyen", "vận chuyển", "phi ship", "phí ship", "freeship", "mien phi van chuyen", "miễn phí vận chuyển"]):
        return "shipping_policy"
    if any(keyword in normalized for keyword in ["bao hanh", "bảo hành", "doi tra", "đổi trả", "hoan tra", "hoàn trả", "may loi", "máy lỗi"]):
        return "warranty_policy"
    if any(keyword in normalized for keyword in ["khuyen mai", "khuyến mãi", "uu dai", "ưu đãi", "giam gia", "giảm giá", "sale", "chuong trinh", "chương trình"]):
        return "bonus"
    if any(keyword in normalized for keyword in ["gia", "giá", "bao nhieu tien", "bao nhiêu tiền", "bao nhieu", "bao nhiêu"]):
        return "product_price"
    if any(keyword in normalized for keyword in ["goi y", "gợi ý", "de xuat", "đề xuất", "tu van", "tư vấn", "recommend"]):
        return "product_recommendation"
    if any(keyword in normalized for keyword in ["tim", "tìm", "kiem", "kiếm", "search", "co ", "có "]):
        return "product_search"
    return None


def is_order_tracking_request(request: DialogflowCXRequest) -> bool:
    if request.get_parameter(IntentService.ORDER_PARAMETER_NAMES):
        return True

    normalized = normalize_text(request.text or "")
    if not normalized:
        return False

    if re.search(r"\b(?:ord[-\s]?)?\d{3,}\b", normalized):
        return True

    order_keywords = [
        "don hang",
        "đơn hàng",
        "ma don",
        "mã đơn",
        "trang thai don",
        "trạng thái đơn",
        "kiem tra don",
        "kiểm tra đơn",
        "theo doi don",
        "theo dõi đơn",
        "don cua toi",
        "đơn của tôi",
    ]
    tracking_keywords = [
        "dang o dau",
        "đang ở đâu",
        "trang thai",
        "trạng thái",
        "tracking",
        "van don",
        "vận đơn",
        "giao toi dau",
        "giao tới đâu",
    ]
    return any(keyword in normalized for keyword in order_keywords) or (
        "don" in normalized and any(keyword in normalized for keyword in tracking_keywords)
    )

def is_reset_intent(text: str | None) -> bool:
    normalized = normalize_text(text or "")
    if not normalized:
        return False
        
    reset_keywords = [
        "bat dau lai", "bắt đầu lại", "reset", "xoa lich su", "xóa lịch sử",
        "quen di", "quên đi", "noi chuyen khac", "nói chuyện khác"
    ]
    return any(keyword in normalized for keyword in reset_keywords)


def extract_product_name_from_text(text: str | None) -> str | None:
    if not text:
        return None

    cleaned = " ".join(text.strip().split())
    patterns = [
        r"^(?:giá|gia)\s+(.+?)\s+(?:bao nhiêu|bao nhieu|là bao nhiêu|la bao nhieu|bao nhiêu tiền|bao nhieu tien)\??$",
        r"^(.+?)\s+(?:giá|gia)\s+(?:bao nhiêu|bao nhieu|thế nào|the nao)\??$",
        r"^(.+?)\s+(?:bao nhiêu tiền|bao nhieu tien|bao nhiêu|bao nhieu)\??$",
        r"^(?:cho tôi biết giá|cho toi biet gia|xem giá|xem gia|báo giá|bao gia)\s+(.+?)\??$",
    ]

    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            product_name = strip_product_noise(match.group(1))
            if product_name:
                return product_name

    return None


def extract_product_search_query_from_text(text: str | None) -> str | None:
    if not text:
        return None

    cleaned = " ".join(text.strip().split())
    patterns = [
        r"^(?:tìm|tim|kiếm|kiem|search|tìm kiếm|tim kiem)\s+(.+?)\??$",
        r"^(?:gợi ý|goi y|recommend|đề xuất|de xuat|tư vấn|tu van)\s+(.+?)\??$",
        r"^(?:có|co)\s+(.+?)\s+(?:không|khong)\??$",
        r"^(?:sản phẩm|san pham)\s+(.+?)\??$",
    ]

    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            query = strip_product_noise(match.group(1))
            if query:
                return query

    product_name = extract_product_name_from_text(cleaned)
    if product_name:
        return product_name

    return None


def extract_promotion_product_from_text(text: str | None) -> str | None:
    if not text:
        return None

    cleaned = " ".join(text.strip().split())
    patterns = [
        r"^(.+?)\s+(?:có|co)\s+(?:khuyến mãi|khuyen mai|ưu đãi|uu dai|giảm giá|giam gia|sale)\s+(?:không|khong)\??$",
        r"^(?:mua|cho)\s+(.+?)\s+(?:có|co)\s+(?:mã|ma|voucher|khuyến mãi|khuyen mai|ưu đãi|uu dai).*$",
        r"^(?:khuyến mãi|khuyen mai|ưu đãi|uu dai|giảm giá|giam gia)\s+(?:cho|của|cua)\s+(.+?)\??$",
    ]

    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            product_name = strip_product_noise(match.group(1))
            if product_name:
                return product_name

    return None


def is_generic_promotion_request(text: str | None) -> bool:
    normalized = normalize_text(text or "")
    if not normalized:
        return False

    generic_phrases = [
        "co ma giam gia",
        "có mã giảm giá",
        "co khuyen mai",
        "có khuyến mãi",
        "shop co ma",
        "shop có mã",
        "chuong trinh gi",
        "chương trình gì",
        "ma nao",
        "mã nào",
        "voucher nao",
        "uu dai nao",
        "ưu đãi nào",
    ]
    return any(phrase in normalized for phrase in generic_phrases)


def extract_product_compare_names_from_text(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None

    cleaned = " ".join(text.strip().split())
    patterns = [
        r"^(?:so sánh|so sanh)\s+(.+?)\s+(?:và|va|với|voi)\s+(.+?)\??$",
        r"^(.+?)\s+(?:với|voi|và|va)\s+(.+?)\s+(?:máy nào tốt hơn|may nao tot hon|nên mua|nen mua).*$",
        r"^(?:nên mua|nen mua)\s+(.+?)\s+(?:hay|hoặc|hoac)\s+(.+?)\??$",
        r"^(?:khác nhau giữa|khac nhau giua)\s+(.+?)\s+(?:và|va|với|voi)\s+(.+?)\??$",
    ]

    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            left = strip_product_noise(match.group(1))
            right = strip_product_noise(match.group(2))
            if left and right:
                return left, right

    return None, None


def extract_single_compare_target_from_text(text: str | None) -> str | None:
    if not text:
        return None

    cleaned = " ".join(text.strip().split())
    patterns = [
        r"^(?:so với|so voi|với|voi)\s+(.+?)(?:\s+(?:thì sao|thi sao|thế nào|the nao))?\??$",
        r"^(.+?)\s+(?:thì sao|thi sao|thế nào|the nao)\??$",
    ]

    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            product_name = strip_product_noise(match.group(1))
            if product_name:
                return product_name

    return None


def extract_limit_from_text(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"\b(\d{1,2})\b", text)
    if not match:
        return None
    return max(1, min(int(match.group(1)), 10))


def strip_product_noise(value: str) -> str:
    cleaned = value.strip(" ?.!,:;")
    cleaned = re.sub(
        r"\b(của|cua|mẫu|mau|sản phẩm|san pham|cho tôi|cho toi|cho mình|cho minh)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    return " ".join(cleaned.split())


def format_money(amount: int | float, currency_code: str) -> str:
    currency = currency_code.upper()
    numeric_amount = float(amount)

    if currency == "VND":
        return f"{numeric_amount:,.0f} VNĐ".replace(",", ".")

    formatted = f"{numeric_amount:,.2f}".rstrip("0").rstrip(".")
    return f"{formatted} {currency}"


def build_product_url(product: dict[str, Any]) -> str:
    base_url = settings.storefront_base_url.rstrip("/")
    country_code = settings.storefront_country_code.strip("/") or "dk"
    handle = product.get("handle") or product.get("id")
    return f"{base_url}/{country_code}/products/{handle}"


def first_image_url(product: dict[str, Any]) -> str | None:
    images = product.get("images", []) or []
    if not images:
        return None
    return images[0].get("url")


def build_discount_text(prices: list[dict[str, Any]]) -> str:
    discounted = [
        item
        for item in prices
        if float(item.get("original_amount") or item["amount"]) > float(item["amount"])
    ]
    if not discounted:
        return "Chưa có chương trình khuyến mãi"

    best = max(
        discounted,
        key=lambda item: float(item["original_amount"]) - float(item["amount"]),
    )
    discount_amount = float(best["original_amount"]) - float(best["amount"])
    return f"Đang giảm {format_money(discount_amount, best['currency'])}"


def product_promotion_hint(product: dict[str, Any]) -> str:
    prices = []
    for variant in product.get("variants", []) or []:
        calculated_price = variant.get("calculated_price") or {}
        amount = calculated_price.get("calculated_amount")
        original_amount = calculated_price.get("original_amount")
        currency = calculated_price.get("currency_code")
        if amount is not None and original_amount is not None and currency:
            prices.append({"amount": amount, "original_amount": original_amount, "currency": currency})

    metadata = product.get("metadata") or {}
    promo_hint = metadata.get("promo_hint")
    if promo_hint and not prices:
        return "Chưa có chương trình khuyến mãi"

    return build_discount_text(prices)


def promotion_code_message(code: str) -> str:
    normalized = code.strip().upper()
    messages = {
        "WELCOME10": "Mã WELCOME10 đang khả dụng: giảm 10% cho sản phẩm áp dụng trong demo.",
        "ANDROID15": "Mã ANDROID15 đang khả dụng: giảm 15% cho các sản phẩm Android áp dụng trong demo.",
        "PHONE500K": "Mã PHONE500K đang khả dụng: giảm 500.000 VNĐ cho đơn hàng đủ điều kiện.",
        "FREESHIP": "Mã FREESHIP đang khả dụng: hỗ trợ miễn hoặc giảm phí giao hàng, tối đa 120.000 VNĐ.",
        "PREORDER17": "Mã PREORDER17 đang khả dụng: giảm 1.000.000 VNĐ cho nhóm sản phẩm đặt trước iPhone 17.",
    }
    return messages.get(normalized, f"Mình chưa có thông tin chi tiết cho mã {normalized}. Bạn có thể thử các mã WELCOME10, ANDROID15, PHONE500K, FREESHIP hoặc PREORDER17.")


def lowest_price_text(prices: list[dict[str, Any]]) -> str:
    if not prices:
        return "Chưa cập nhật"
    lowest = min(prices, key=lambda item: float(item["amount"]))
    return format_money(lowest["amount"], lowest["currency"])


def metadata_text(metadata: dict[str, Any], keys: list[str]) -> str:
    values = [str(metadata[key]) for key in keys if metadata.get(key)]
    return ", ".join(values) if values else "Chưa cập nhật"


def rating_text(metadata: dict[str, Any]) -> str:
    rating = metadata.get("rating")
    sold_count = metadata.get("sold_count")
    parts = []
    if rating is not None:
        parts.append(f"{rating}/5")
    if sold_count is not None:
        parts.append(f"đã bán {sold_count}")
    return ", ".join(parts) if parts else "Chưa cập nhật"


def build_compare_recommendation(
    title_a: str,
    title_b: str,
    metadata_a: dict[str, Any],
    metadata_b: dict[str, Any],
    prices_a: list[dict[str, Any]],
    prices_b: list[dict[str, Any]],
) -> str:
    price_a = min((float(item["amount"]) for item in prices_a), default=None)
    price_b = min((float(item["amount"]) for item in prices_b), default=None)
    camera_a = normalize_text(str(metadata_a.get("camera") or ""))
    camera_b = normalize_text(str(metadata_b.get("camera") or ""))
    battery_a = normalize_text(str(metadata_a.get("battery") or ""))
    battery_b = normalize_text(str(metadata_b.get("battery") or ""))

    if "zoom" in camera_b or "ultra" in camera_b:
        return f"Nếu bạn ưu tiên zoom/camera Android và AI, {title_b} đáng cân nhắc hơn. Nếu muốn hệ sinh thái iOS và quay chụp ổn định, chọn {title_a}."
    if "iphone" in battery_a or "pin lau" in battery_a or "pin lâu" in battery_a:
        return f"Nếu bạn ưu tiên pin và hệ sinh thái iOS, {title_a} hợp hơn. Nếu muốn trải nghiệm Android/AI, {title_b} là lựa chọn tốt."
    if price_a is not None and price_b is not None:
        cheaper = title_a if price_a <= price_b else title_b
        return f"Nếu ưu tiên giá dễ tiếp cận hơn, {cheaper} đang là lựa chọn mềm hơn trong hai mẫu."
    if camera_a or battery_b:
        return f"{title_a} và {title_b} đều là lựa chọn tốt; nên chọn theo hệ điều hành, camera và ngân sách bạn thích."
    return f"{title_a} và {title_b} đều có điểm mạnh riêng; bạn nên chọn theo hệ điều hành và ngân sách."


def has_discount(price: dict[str, Any]) -> bool:
    return float(price.get("original_amount") or price["amount"]) > float(price["amount"])


def best_seller_score(product: dict[str, Any]) -> float:
    metadata = product.get("metadata") or {}
    for key in ["sales_count", "sold_count", "sold", "purchase_count", "bestseller_score"]:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    title = normalize_text(str(product.get("title", "")))
    handle = normalize_text(str(product.get("handle", "")))
    text = f"{title} {handle}"
    score = 0.0
    for keyword, weight in {
        "hoodie": 90,
        "sweatshirt": 80,
        "t shirt": 75,
        "shorts": 70,
        "joggers": 65,
        "pants": 60,
    }.items():
        if keyword in text:
            score += weight
    prices = []
    for variant in product.get("variants", []) or []:
        calculated_price = variant.get("calculated_price") or {}
        amount = calculated_price.get("calculated_amount") or calculated_price.get("original_amount")
        if amount is not None:
            prices.append(float(amount))
    if prices:
        score += max(0, 100 - min(prices)) / 100
    return score


def build_variant_price_lines(prices: list[dict[str, Any]]) -> list[str]:
    lines = []
    for item in sorted(prices, key=lambda price: str(price["variant"])):
        price_text = format_money(item["amount"], item["currency"])
        original = float(item.get("original_amount") or item["amount"])
        amount = float(item["amount"])
        if original > amount:
            original_text = format_money(original, item["currency"])
            lines.append(f"- {item['variant']}: ~~{original_text}~~ {price_text}")
        else:
            lines.append(f"- {item['variant']}: {price_text}")
    return lines
