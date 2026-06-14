from __future__ import annotations

import random
import re
from difflib import SequenceMatcher
from typing import Any

from app.clients.gemini_client import GeminiClient
from app.clients.medusa_client import MedusaClient
from app.core.config import settings
from app.core.debug_log import trace
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
from app.services.ai_usage_service import cost_context_from_request_attributes, record_gemini_usage
from app.services.escalation import is_explicit_handoff_request
from app.services.intent_nlu import (
    curated_intent_for_text,
    expand_product_abbreviations,
    extract_budget,
    extract_budget_range,
    extract_product_name_direct,
    infer_intent_from_text,
    is_generic_product_reference,
    is_product_context_followup,
    is_probable_off_topic_text,
    is_reset_intent,
    normalize_resolved_intent,
    normalize_text,
    parse_confidence,
)


KNOWN_PRODUCT_BRANDS = {
    "apple",
    "iphone",
    "samsung",
    "samsung galaxy",
    "xiaomi",
    "oppo",
    "vivo",
    "realme",
    "google pixel",
}


class IntentService:
    PRODUCT_PARAMETER_NAMES = ["product", "product_name", "productName", "product_title", "item"]
    PRODUCT_A_PARAMETER_NAMES = ["product_a", "productA", "first_product", "firstProduct"]
    PRODUCT_B_PARAMETER_NAMES = ["product_b", "productB", "second_product", "secondProduct"]
    SEARCH_PARAMETER_NAMES = ["query", "search", "keyword", "category", "style", "need", "product_type", "productType"]
    ORDER_PARAMETER_NAMES = ["order_id", "orderId", "order_code", "orderCode", "order", "current_order_code"]
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
    PRODUCT_CONTEXT_KEYS = [
        "product",
        "product_name",
        "productName",
        "product_title",
        "item",
        "query",
        "search",
        "keyword",
        "category",
        "style",
        "need",
        "product_type",
        "productType",
        "current_product_id",
        "current_product_handle",
        "current_product_name",
        "current_product_price",
        "current_product_url",
        "current_search_query",
        "last_product_names",
        "product_a_name",
        "product_b_name",
        "history_products",
        "product_context_turns_remaining",
    ]
    ORDER_CONTEXT_KEYS = [
        "order_id",
        "orderId",
        "order_code",
        "orderCode",
        "order",
        "current_order_code",
        "current_order_status",
        "current_order_total",
        "order_context_turns_remaining",
    ]

    def __init__(self, medusa_client: MedusaClient, gemini_client: GeminiClient | None = None) -> None:
        self.medusa_client = medusa_client
        self.gemini_client = gemini_client

    async def handle(
        self,
        request: DialogflowCXRequest,
        authorization_header: str | None = None,
    ) -> DialogflowCXResponse:
        trace(
            "INTENT_SERVICE_REQUEST",
            {
                "session_id": getattr(request, "session_id", None),
                "text": request.text,
                "lex_intent": request.intent_name(),
                "request": request.model_dump(by_alias=True),
                "has_authorization": bool(authorization_header),
            },
        )
        cost_context = cost_context_from_request_attributes(
            getattr(request, "request_attributes", None),
            fallback_session_id=getattr(request, "session_id", None),
        )
        lex_intent = request.intent_name().lower()
        text_intent, gemini_confidence = await self._resolve_local_or_ai_intent(request, lex_intent, cost_context)
        trace(
            "INTENT_SERVICE_RESOLVED_INTENT",
            {
                "session_id": getattr(request, "session_id", None),
                "lex_intent": lex_intent,
                "text_intent": text_intent,
                "gemini_confidence": gemini_confidence,
                "cost_context": cost_context,
            },
        )

        if is_reset_intent(request.text):
            cleared_params = {k: None for k in request_session_parameters(request).keys()}
            cleared_params["search_status"] = "reset_success"
            response = text_response("Đã xoá lịch sử trò chuyện. Mình có thể giúp gì tiếp theo cho bạn?", cleared_params)
            trace(
                "INTENT_SERVICE_RESET_RESPONSE",
                {
                    "session_id": getattr(request, "session_id", None),
                    "response": response.model_dump(by_alias=True),
                },
            )
            return response

        try:
            response = await self._dispatch_intent(
                request,
                lex_intent=lex_intent,
                text_intent=text_intent,
                cost_context=cost_context,
                authorization_header=authorization_header,
            )
        except (
            AuthenticationRequiredError,
            ProductNotFoundError,
            MissingOrderCodeError,
            OrderNotFoundError,
            MedusaTimeoutError,
            MedusaAPIError,
        ) as exc:
            response = self._error_response(request, exc)
            trace(
                "INTENT_SERVICE_ERROR_RESPONSE",
                {
                    "session_id": getattr(request, "session_id", None),
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                    "response": response.model_dump(by_alias=True),
                },
            )

        trace(
            "INTENT_SERVICE_DISPATCH_RESPONSE",
            {
                "session_id": getattr(request, "session_id", None),
                "lex_intent": lex_intent,
                "text_intent": text_intent,
                "response": response.model_dump(by_alias=True),
            },
        )

        self._apply_context_boundary(request, response, lex_intent, text_intent)
        self._annotate_response(response, request.intent_name(), text_intent, gemini_confidence)
        finalized = await self._finalize_response(request, lex_intent, response, cost_context)
        trace(
            "INTENT_SERVICE_RESPONSE",
            {
                "session_id": getattr(request, "session_id", None),
                "response": finalized.model_dump(by_alias=True),
            },
        )
        return finalized

    def _apply_context_boundary(
        self,
        request: DialogflowCXRequest,
        response: DialogflowCXResponse,
        lex_intent: str,
        text_intent: str | None,
    ) -> None:
        effective_intent = text_intent or normalize_resolved_intent(request.intent_name()) or lex_intent
        product_intents = {
            "product_search",
            "product_price",
            "product_recommendation",
            "product_availability",
            "inventory",
            "product_compare",
            "product_spec",
            "product_camera",
            "product_battery",
            "product_gaming",
            "bonus",
            "warranty_policy",
            "shipping_policy",
            "installment",
            "payment_method",
            "cart_add_item",
            "cart_view",
            "cart_update",
            "checkout_start",
        }
        order_intents = {
            "order_tracking",
            "shipping_tracking",
            "order_detail",
            "order_history",
            "order_list",
            "order_cancel",
            "order_modify",
            "refund_status",
            "complaint",
        }
        product_aftercare_intents = {"return_request", "warranty_claim"}
        neutral_intents = {
            "smalltalk_affirmation",
            "smalltalk_negation",
            "smalltalk_compliment",
        }

        if effective_intent in neutral_intents:
            return
        if effective_intent in product_intents:
            self._clear_response_context(response, self.ORDER_CONTEXT_KEYS)
            return
        if effective_intent in order_intents:
            self._clear_response_context(response, self.PRODUCT_CONTEXT_KEYS)
            return
        if effective_intent in product_aftercare_intents:
            self._clear_response_context(response, self.ORDER_CONTEXT_KEYS)
            return

        # Greeting, store information, shipping policy, handoff and fallback
        # start a separate topic. Do not let a later ambiguous question revive
        # product/order entities from an earlier conversation branch.
        self._clear_response_context(
            response,
            self.PRODUCT_CONTEXT_KEYS + self.ORDER_CONTEXT_KEYS,
        )

    @staticmethod
    def _clear_response_context(response: DialogflowCXResponse, keys: list[str]) -> None:
        for key in keys:
            response.session_info.parameters[key] = None

    async def _resolve_local_or_ai_intent(
        self,
        request: DialogflowCXRequest,
        lex_intent: str,
        cost_context: dict[str, Any] | None,
    ) -> tuple[str | None, float | None]:
        text_intent = infer_intent_from_text(request.text)
        curated_intent = curated_intent_for_text(request.text)
        if curated_intent:
            trace(
                "INTENT_SERVICE_CURATED_INTENT",
                {
                    "text": request.text,
                    "lex_intent": lex_intent,
                    "curated_intent": curated_intent,
                },
            )
            return curated_intent, None
        if is_probable_off_topic_text(request.text):
            trace(
                "INTENT_SERVICE_LOCAL_INTENT",
                {
                    "text": request.text,
                    "text_intent": "fallback",
                    "reason": "probable_off_topic",
                },
            )
            return "fallback", None

        safe_overrides = {
            "human_handover",
            "smalltalk_affirmation",
            "smalltalk_negation",
            "smalltalk_compliment",
            "top_expensive",
            "top_cheap",
            "best_sellers",
            "product_recommendation",
            "complaint",
            "order_cancel",
            "order_detail",
            "order_history",
            "order_list",
            "order_modify",
            "refund_status",
            "return_request",
            "warranty_claim",
            "cart_add_item",
            "cart_update",
            "cart_view",
            "checkout_start",
            "installment",
            "payment_method",
            "shipping_tracking",
            "store_info",
            "product_availability",
            "inventory",
            "product_camera",
            "product_battery",
            "product_gaming",
            "product_spec",
            "product_compare",
            "bonus",
            "shipping_policy",
            "warranty_policy",
        }
        lex_canonical = normalize_resolved_intent(request.intent_name())
        if text_intent in safe_overrides and text_intent != lex_canonical:
            return text_intent, None

        lex_is_fallback = "fallback" in lex_intent or "default negative" in lex_intent

        # Lex is authoritative once it selected a concrete intent. The local
        # classifier exists to recover FallbackIntent requests, not to replace
        # a trained Lex decision with broader legacy keyword rules.
        if not lex_is_fallback:
            trace(
                "INTENT_SERVICE_LEX_INTENT_ACCEPTED",
                {
                    "text": request.text,
                    "lex_intent": lex_intent,
                },
            )
            return None, None

        if text_intent:
            trace(
                "INTENT_SERVICE_LOCAL_INTENT",
                {
                    "text": request.text,
                    "text_intent": text_intent,
                    "reason": "local_nlu",
                },
            )
            return text_intent, None

        return "fallback", None

    async def _dispatch_intent(
        self,
        request: DialogflowCXRequest,
        *,
        lex_intent: str,
        text_intent: str | None,
        cost_context: dict[str, Any] | None,
        authorization_header: str | None,
    ) -> DialogflowCXResponse:
        effective_intent = text_intent or normalize_resolved_intent(request.intent_name()) or lex_intent
        
        order_intents = {
            "order_tracking",
            "shipping_tracking",
            "order_detail",
            "order_history",
            "order_list",
            "order_cancel",
            "order_modify",
            "refund_status",
            "complaint",
            "warranty_claim",
            "return_request",
        }
        if effective_intent in order_intents:
            extracted_code = extract_order_code_from_text(request.text, request)
            if extracted_code:
                set_request_parameter(request, "order_id", extracted_code)
        trace(
            "INTENT_SERVICE_DISPATCH_START",
            {
                "session_id": getattr(request, "session_id", None),
                "lex_intent": lex_intent,
                "text_intent": text_intent,
                "effective_intent": effective_intent,
                "text": request.text,
                "session_parameters": request_session_parameters(request),
            },
        )
        if self._is_handover_intent(request, lex_intent, text_intent):
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "human_handover", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.human_handover()
        if effective_intent == "greeting" or lex_intent in {"xin chao", "hello", "hi"}:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "greeting", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.greeting()
        if effective_intent == "fallback":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "fallback", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.fallback()
        if effective_intent in {"smalltalk_affirmation", "smalltalk_negation", "smalltalk_compliment"}:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": effective_intent, "lex_intent": lex_intent, "text_intent": text_intent})
            return self._smalltalk_response(effective_intent)
        if (
            effective_intent not in {
                "product_recommendation",
                "product_spec",
                "product_camera",
                "product_battery",
                "product_gaming",
            }
            and self._looks_like_product_context_bleed(request, lex_intent, text_intent)
        ):
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "context_bleed_fallback", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.fallback()
        if effective_intent in {"top_expensive", "top_cheap", "best_sellers"}:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "product_ranking", "ranking": effective_intent, "lex_intent": lex_intent})
            return await self.product_ranking(request, ranking=effective_intent)
        if effective_intent == "store_info":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "store_info", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.store_info()
        if effective_intent in {"payment_method", "installment"}:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "payment_installment", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.payment_or_installment(request)
        if effective_intent in {"cart_add_item", "cart_view", "cart_update", "checkout_start"}:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "cart_checkout_guidance", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.cart_or_checkout_guidance(request, effective_intent)
        if effective_intent in {
            "order_cancel",
            "order_modify",
            "return_request",
            "refund_status",
            "warranty_claim",
            "complaint",
        }:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "aftercare_handoff", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.aftercare_handoff(request, effective_intent)
        if effective_intent == "product_compare":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "product_compare", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.product_compare(request)
        if effective_intent in {"inventory", "product_availability"}:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "inventory_status", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.inventory_status(request)
        if effective_intent == "product_price":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "product_price", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.product_price(request)
        if effective_intent in {"product_spec", "product_camera", "product_battery", "product_gaming"}:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "product_advice", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.product_advice(request, effective_intent)
        if effective_intent == "product_recommendation":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "product_recommendation", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.product_recommendation(request)
        if effective_intent == "bonus":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "bonus", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.bonus(request)
        if effective_intent == "shipping_policy":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "shipping_policy", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.shipping_policy()
        if effective_intent == "warranty_policy":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "warranty_policy", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.warranty_policy(request)
        if effective_intent == "product_search" or lex_intent == "search":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "product_search", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.product_search(request)
        if effective_intent == "order_detail":
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "order_detail", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.order_detail(request, authorization_header=authorization_header)
        if effective_intent in {"order_list", "order_history"}:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "order_list", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.order_list(request, authorization_header=authorization_header)
        if effective_intent in {"order_tracking", "shipping_tracking"}:
            lex_canonical = normalize_resolved_intent(request.intent_name())
            if (
                text_intent in {"order_tracking", "shipping_tracking"}
                or lex_canonical in {"order_tracking", "shipping_tracking"}
                or is_order_tracking_request(request)
            ):
                trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "order_tracking", "lex_intent": lex_intent, "text_intent": text_intent})
                return await self.order_tracking(request, authorization_header=authorization_header)
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "order_tracking_fallback", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.fallback()
        if "fallback" in lex_intent:
            trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "unresolved_fallback", "lex_intent": lex_intent, "text_intent": text_intent})
            return await self.fallback()
        trace("INTENT_SERVICE_DISPATCH_BRANCH", {"branch": "default_fallback", "lex_intent": lex_intent, "text_intent": text_intent})
        return await self.fallback()

    def _is_handover_intent(self, request: DialogflowCXRequest, lex_intent: str, text_intent: str | None) -> bool:
        if text_intent == "human_handover":
            return True
        if request.text and not is_explicit_handoff_request(request.text):
            return False
        return "humanhandover" in lex_intent or "human_handover" in lex_intent or "handover" in lex_intent or "handoff" in lex_intent

    def _looks_like_product_context_bleed(
        self,
        request: DialogflowCXRequest,
        lex_intent: str,
        text_intent: str | None,
    ) -> bool:
        if text_intent:
            return False

        product_intent_tokens = [
            "product",
            "price",
            "inventory",
            "stock",
            "warranty",
            "promotion",
            "discount",
            "bonus",
            "recommend",
            "search",
        ]
        if not any(token in lex_intent for token in product_intent_tokens):
            return False

        if request.get_parameter(
            self.PRODUCT_PARAMETER_NAMES
            + self.PRODUCT_A_PARAMETER_NAMES
            + self.PRODUCT_B_PARAMETER_NAMES
            + self.SEARCH_PARAMETER_NAMES
            + ["promo_code", "promoCode", "code"]
        ):
            return False

        if (
            extract_product_name_from_text(request.text)
            or extract_product_name_direct(request.text)
            or extract_product_search_query_from_text(request.text)
            or extract_promotion_product_from_text(request.text)
            or any(extract_product_compare_names_from_text(request.text))
            or extract_single_compare_target_from_text(request.text)
        ):
            return False

        return not is_product_context_followup(request.text)

    @staticmethod
    def _smalltalk_response(text_intent: str) -> DialogflowCXResponse:
        messages = {
            "smalltalk_affirmation": "Dạ vâng, mình ở đây. Bạn cần hỗ trợ thông tin gì về sản phẩm, giá cả hay ưu đãi không ạ?",
            "smalltalk_negation": "Dạ vâng. Vậy nếu bạn cần tìm hiểu sản phẩm hay có thắc mắc nào khác thì cứ nhắn cho mình nhé!",
            "smalltalk_compliment": "Cảm ơn bạn nha. Mình là trợ lý ảo của shop, mình có thể hỗ trợ bạn xem sản phẩm, giá, ưu đãi hoặc đơn hàng nhé!",
        }
        parameters = {"search_status": text_intent} if text_intent == "smalltalk_compliment" else None
        return text_response(messages[text_intent], parameters)

    def _error_response(self, request: DialogflowCXRequest, exc: Exception) -> DialogflowCXResponse:
        if isinstance(exc, AuthenticationRequiredError):
            return self._authentication_required_response(request)
        if isinstance(exc, ProductNotFoundError):
            return text_response(
                "Mình chưa tìm thấy sản phẩm phù hợp. Bạn có thể nhập tên sản phẩm cụ thể hơn không?",
                {"search_status": "product_not_found"},
            )
        if isinstance(exc, MissingOrderCodeError):
            return text_response(
                "Bạn vui lòng cung cấp mã đơn hàng (ví dụ: mã số trên email) để mình kiểm tra tình trạng giúp bạn nhé.",
                {"search_status": "missing_order_code"},
            )
        if isinstance(exc, OrderNotFoundError):
            return text_response("Mình chưa tìm thấy đơn hàng này. Bạn kiểm tra lại mã đơn hàng giúp mình nhé.", {"search_status": "order_not_found"})
        if isinstance(exc, MedusaTimeoutError):
            return text_response("Hệ thống đang phản hồi chậm. Bạn vui lòng thử lại sau ít phút nhé.", {"search_status": "timeout"})
        if isinstance(exc, MedusaAPIError) and exc.status_code in {401, 403}:
            return text_response("Phiên đăng nhập của bạn không hợp lệ hoặc đã hết hạn. Bạn vui lòng đăng nhập lại nhé.", {"search_status": "invalid_authentication"})
        return text_response("Mình chưa thể kết nối hệ thống bán hàng lúc này. Bạn vui lòng thử lại sau.", {"search_status": "medusa_api_error"})

    @staticmethod
    def _annotate_response(
        response: DialogflowCXResponse,
        lex_intent: str,
        text_intent: str | None,
        gemini_confidence: float | None,
    ) -> None:
        search_status = str(response.session_info.parameters.get("search_status") or "")
        resolved_intent = (
            "fallback"
            if search_status == "fallback"
            else text_intent or normalize_resolved_intent(lex_intent) or lex_intent
        )
        resolution_source = "gemini" if gemini_confidence is not None else ("local_nlu" if text_intent else "lex")
        response.session_info.parameters["resolved_intent"] = resolved_intent
        response.session_info.parameters["resolution_source"] = resolution_source
        response.session_info.parameters["ai_confidence"] = (
            gemini_confidence if gemini_confidence is not None
            else (0.5 if resolved_intent == "fallback" else 1.0)
        )

    @staticmethod
    def _authentication_required_response(request: DialogflowCXRequest) -> DialogflowCXResponse:
        channel = request.request_attributes.get("channel") if getattr(request, "request_attributes", None) else None
        if channel == "MESSENGER":
            return text_response(
                "Bạn cần đăng nhập để tra cứu thông tin đơn hàng. Vui lòng truy cập website cửa hàng của chúng mình tại "
                f"{settings.storefront_base_url}/vn/account/orders để kiểm tra tình trạng đơn hàng nhé.",
                {"search_status": "authentication_required"},
            )
        return text_response(
            "Bạn cần đăng nhập trước khi tra cứu thông tin đơn hàng. "
            "Mình chỉ có thể trả lời thông tin sản phẩm công khai khi chưa đăng nhập.",
            {"search_status": "authentication_required"},
        )

    async def greeting(self) -> DialogflowCXResponse:
        greetings = [
            "Xin chào! Mình là Medusan, trợ lý ảo của shop. Mình có thể giúp gì cho bạn hôm nay?\n(Bạn có thể gõ /h để gặp nhân viên, hoặc /b để gọi lại bot)",
            "Chào bạn, mình là Medusan. Mình có thể hỗ trợ bạn tìm điện thoại hoặc kiểm tra đơn hàng ạ?\n(Bạn có thể gõ /h để gặp nhân viên, hoặc /b để gọi lại bot)",
            "Medusan xin chào! Bạn cần hỗ trợ tư vấn sản phẩm hay hỏi về khuyến mãi không?\n(Bạn có thể gõ /h để gặp nhân viên, hoặc /b để gọi lại bot)",
            "Hi bạn, mình là trợ lý Medusan. Mình có thể hỗ trợ bạn tra giá, kiểm tra tồn kho hoặc trạng thái đơn hàng nhé!\n(Bạn có thể gõ /h để gặp nhân viên, hoặc /b để gọi lại bot)"
        ]
        return text_response(random.choice(greetings), {"search_status": "greeting"})

    async def fallback(self) -> DialogflowCXResponse:
        return text_response(
            "Mình chưa hiểu rõ yêu cầu của bạn. Bạn có thể hỏi về sản phẩm, giá, ưu đãi, giao hàng hoặc đơn hàng để mình hỗ trợ nhé. Nếu cần gặp người thật, bạn nhập /h.",
            {"search_status": "fallback"},
        )

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

    async def store_info(self) -> DialogflowCXResponse:
        return text_response(
            "\n".join(
                [
                    "Thông tin cửa hàng:",
                    f"- Website: {settings.storefront_base_url}",
                    "- Hỗ trợ online: 8:00-22:00 hằng ngày.",
                    "- Bạn có thể đặt hàng trực tiếp trên website hoặc nhắn /h để gặp nhân viên.",
                    "- Với yêu cầu cần xác minh tài khoản, shop sẽ cần bạn đăng nhập trước.",
                ]
            ),
            {"search_status": "store_info"},
        )

    async def payment_or_installment(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        product_name = self._resolve_product_name(request)
        if product_name and not is_specific_catalog_query(product_name):
            product_name = None
        product_line = f" với {product_name}" if product_name else ""
        return text_response(
            "\n".join(
                [
                    f"Shop hỗ trợ các phương thức thanh toán{product_line}:",
                    "- COD khi nhận hàng.",
                    "- Chuyển khoản ngân hàng.",
                    "- Ví điện tử/Momo/VNPAY nếu checkout đang bật cổng thanh toán tương ứng.",
                    "- Thẻ tín dụng và trả góp tuỳ chương trình tại thời điểm đặt hàng.",
                    "Bạn có thể thêm sản phẩm vào giỏ rồi chọn phương thức thanh toán ở bước checkout. Nếu cần duyệt trả góp, nhập /h để nhân viên hỗ trợ.",
                ]
            ),
            {
                "search_status": "payment_installment_policy",
                "current_product_name": product_name,
            },
        )

    async def product_advice(self, request: DialogflowCXRequest, intent: str) -> DialogflowCXResponse:
        product_name = self._resolve_product_name(request)
        if product_name:
            products = await self.medusa_client.list_products(query=product_name, limit=12)
            if not products:
                products = await self.medusa_client.list_products(limit=250)
            product = self._find_best_product(product_name, products)
            if not product:
                raise ProductNotFoundError()
            return self._product_advice_response(product, intent)

        response = await self.product_recommendation(request)
        response.session_info.parameters["search_status"] = intent
        return response

    async def cart_or_checkout_guidance(self, request: DialogflowCXRequest, intent: str) -> DialogflowCXResponse:
        product_name = self._resolve_product_name(request)
        if intent in {"cart_add_item", "checkout_start"}:
            product_hint = f" sản phẩm {product_name}" if product_name else " sản phẩm bạn muốn mua"
            message = (
                f"Để đặt{product_hint}, bạn mở trang sản phẩm trên website, chọn màu/dung lượng, thêm vào giỏ rồi thanh toán. "
                "Hiện bot chưa tự thay đổi giỏ hàng thay bạn để tránh đặt nhầm sản phẩm hoặc phiên bản."
            )
        elif intent == "cart_view":
            message = "Bạn có thể xem giỏ hàng trực tiếp trên website. Nếu đang đăng nhập, giỏ hàng sẽ giữ các sản phẩm bạn đã chọn."
        else:
            message = "Bạn có thể cập nhật số lượng hoặc xoá sản phẩm trong giỏ hàng ở website trước khi thanh toán."

        return text_response(
            message,
            {
                "search_status": "cart_checkout_guidance",
                "current_product_name": product_name,
            },
        )

    async def aftercare_handoff(self, request: DialogflowCXRequest, intent: str) -> DialogflowCXResponse:
        order_code = request.get_parameter(self.ORDER_PARAMETER_NAMES)
        product_name = self._resolve_product_name(request)
        if intent == "complaint":
            action = "ghi nhận khiếu nại"
        elif intent == "order_cancel":
            action = "kiểm tra điều kiện huỷ đơn"
        elif intent == "order_modify":
            action = "kiểm tra khả năng sửa thông tin đơn"
        elif intent == "refund_status":
            action = "kiểm tra trạng thái hoàn tiền"
        elif intent == "return_request":
            action = "kiểm tra điều kiện đổi trả"
        elif intent == "warranty_claim":
            action = "tiếp nhận yêu cầu bảo hành"
        else:
            action = "kiểm tra yêu cầu của bạn"

        details = []
        if order_code:
            details.append(f"mã đơn {order_code}")
        if product_name:
            details.append(f"sản phẩm {product_name}")
        detail_text = f" ({', '.join(details)})" if details else ""

        return text_response(
            f"Mình sẽ chuyển nhân viên để {action}{detail_text}. Các yêu cầu này cần xác minh đơn hàng/tài khoản nên bot chưa tự xử lý trực tiếp. Bạn nhập /h hoặc để lại số điện thoại để shop liên hệ.",
            {
                "handover_requested": True,
                "search_status": "aftercare_handoff",
                "current_order_code": order_code,
                "current_product_name": product_name,
            },
        )

    async def _finalize_response(
        self,
        request: DialogflowCXRequest,
        intent: str,
        response: DialogflowCXResponse,
        cost_context: dict[str, Any] | None = None,
    ) -> DialogflowCXResponse:
        merge_session_parameters(request, response)

        lex_intent_name = "FallbackIntent"
        if request.session_state.get("intent") and request.session_state["intent"].get("name"):
            lex_intent_name = request.session_state["intent"]["name"]
        
        response.sessionState.intent.name = lex_intent_name

        text_message = first_text_message(response)
        final_text = text_message or ""
        trace(
            "INTENT_SERVICE_FINALIZE_DECISION",
            {
                "session_id": getattr(request, "session_id", None),
                "lex_intent": lex_intent_name,
                "resolved_intent": intent,
                "gemini_present": bool(self.gemini_client),
                "gemini_enabled": bool(self.gemini_client and self.gemini_client.is_enabled()),
                "has_text_message": bool(text_message),
                "session_parameters": response.session_info.parameters,
            },
        )
        response.session_info.parameters["bot_final_message"] = final_text
        return response

    async def _resolve_intent_with_gemini(
        self,
        request: DialogflowCXRequest,
        lex_intent: str,
        cost_context: dict[str, Any] | None = None,
    ) -> tuple[str | None, float | None]:
        if (
            not self.gemini_client
            or not self.gemini_client.is_enabled()
            or not hasattr(self.gemini_client, "resolve_customer_intent")
        ):
            trace(
                "INTENT_SERVICE_GEMINI_INTENT_SKIPPED",
                {
                    "reason": "gemini_disabled_missing_or_method_unavailable",
                    "lex_intent": lex_intent,
                    "text": request.text,
                },
            )
            return None, None

        try:
            trace(
                "INTENT_SERVICE_GEMINI_INTENT_START",
                {
                    "lex_intent": lex_intent,
                    "text": request.text,
                    "session_parameters": request_session_parameters(request),
                },
            )
            if hasattr(self.gemini_client, "resolve_customer_intent_with_usage"):
                resolution, usage_metadata = await self.gemini_client.resolve_customer_intent_with_usage(
                    lex_intent=lex_intent,
                    user_text=request.text,
                    session_parameters=request_session_parameters(request),
                )
                await record_gemini_usage(
                    cost_context=cost_context,
                    operation="intent_resolution",
                    model=getattr(self.gemini_client, "model", "gemini"),
                    intent=normalize_resolved_intent(resolution.get("intent")) or lex_intent,
                    usage_metadata=usage_metadata,
                )
            else:
                resolution = await self.gemini_client.resolve_customer_intent(
                    lex_intent=lex_intent,
                    user_text=request.text,
                    session_parameters=request_session_parameters(request),
                )
                usage_metadata = None
            trace(
                "INTENT_SERVICE_GEMINI_INTENT_RESULT",
                {
                    "resolution": resolution,
                    "usage_metadata": usage_metadata,
                },
            )
        except GeminiAPIError as exc:
            trace(
                "INTENT_SERVICE_GEMINI_INTENT_ERROR",
                {
                    "lex_intent": lex_intent,
                    "text": request.text,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                },
            )
            return None, None

        confidence = parse_confidence(resolution.get("confidence"))
        resolved_intent = normalize_resolved_intent(resolution.get("intent"))
        trace(
            "INTENT_SERVICE_GEMINI_INTENT_DECISION",
            {
                "raw_resolution": resolution,
                "resolved_intent": resolved_intent,
                "confidence": confidence,
            },
        )
        if confidence < 0.65 or not resolved_intent:
            return None, confidence
        if resolved_intent == "human_handover" and not is_explicit_handoff_request(request.text):
            return None, confidence

        product_name = clean_optional_text(resolution.get("product_name"))
        if product_name:
            set_request_parameter(request, "product_name", product_name)

        product_b_name = clean_optional_text(resolution.get("product_b_name"))
        if product_b_name:
            set_request_parameter(request, "product_b", product_b_name)

        order_code = clean_optional_text(resolution.get("order_code"))
        if order_code:
            set_request_parameter(request, "order_id", order_code)

        return resolved_intent, confidence

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

        # Expand abbreviations before searching (e.g., "ip15" -> "iPhone 15")
        expanded_name = expand_product_abbreviations(product_name)

        products = await self.medusa_client.list_products(query=expanded_name)
        if not products:
            products = await self.medusa_client.list_products(limit=250)

        product = self._find_best_product(expanded_name, products)

        # If no exact match but query is generic (e.g., just "iPhone"), show a product list
        if not product:
            ranked = self._rank_products(expanded_name, products)
            if not ranked:
                ranked = self._find_brand_fallback_products(expanded_name, products)
            if ranked:
                return self._products_list_response(
                    ranked[:5],
                    title="Sản phẩm phù hợp",
                    intro=f"Mình tìm thấy một số sản phẩm liên quan đến \"{product_name}\":",
                    status="product_list_fallback",
                    query=product_name,
                )
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
        budget = extract_budget(request.text)
        query = normalize_catalog_query(query)

        # Validate if this is actually a product search (prevents Lex V2 context bleed on 429 errors)
        if not query and budget is None:
            # If no product or budget mentioned, it must at least match a generic search phrase
            if infer_intent_from_text(request.text) != "product_search":
                return await self.fallback()

        products = await self.medusa_client.list_products(query=query, limit=50)
        if products and query:
            ranked_products = self._rank_products(query, products)
            if not ranked_products and is_specific_catalog_query(query):
                raise ProductNotFoundError()
            products = ranked_products or products
        if not products and query:
            products = await self.medusa_client.list_products(limit=50)
            ranked_products = self._rank_products(query, products)
            if not ranked_products and is_specific_catalog_query(query):
                raise ProductNotFoundError()
            products = ranked_products if ranked_products else products

        if budget is not None:
            products = [p for p in products if self._get_lowest_price(p) <= budget]

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
        all_products = await self.medusa_client.list_products(limit=150)
        
        if self.gemini_client and self.gemini_client.is_enabled():
            try:
                res = await self.gemini_client.generate_product_recommendation(request.text or "", all_products)
                recommended_ids = res.get("recommended_product_ids") or []
                message = res.get("recommendation_message")
                
                recommended_products = []
                for p_id in recommended_ids:
                    matching = next((p for p in all_products if p.get("id") == p_id), None)
                    if matching:
                        recommended_products.append(matching)
                        
                if recommended_products and message:
                    return self._products_list_response(
                        recommended_products[:4],
                        title="Gợi ý sản phẩm",
                        intro=message,
                        status="recommendation_success",
                        query=request.text,
                    )
            except Exception as e:
                print(f"Gemini recommendation error: {e}", flush=True)
                pass

        query = request.get_parameter(self.SEARCH_PARAMETER_NAMES + self.PRODUCT_PARAMETER_NAMES)
        query = query or extract_product_search_query_from_text(request.text)
        min_budget, max_budget = extract_budget_range(request.text)
        query = normalize_catalog_query(query)

        products = await self.medusa_client.list_products(query=query, limit=50)
        
        if min_budget is not None or max_budget is not None:
            products = [
                product
                for product in products
                if (min_budget is None or self._get_lowest_price(product) >= min_budget)
                and (max_budget is None or self._get_lowest_price(product) <= max_budget)
            ]

        if not products:
            if query and is_specific_catalog_query(query):
                raise ProductNotFoundError()
            products = await self.medusa_client.list_products(limit=50)
            if min_budget is not None or max_budget is not None:
                products = [
                    product
                    for product in products
                    if (min_budget is None or self._get_lowest_price(product) >= min_budget)
                    and (max_budget is None or self._get_lowest_price(product) <= max_budget)
                ]

        if query:
            ranked_products = self._rank_products(query, products)
            if not ranked_products and is_specific_catalog_query(query):
                raise ProductNotFoundError()
            products = ranked_products or products

        if not products:
            raise ProductNotFoundError()

        return self._products_list_response(
            products[:4],
            title="Gợi ý sản phẩm",
            intro="Dựa trên nhu cầu của bạn, mình gợi ý các sản phẩm này:",
            status="recommendation_success",
            query=query,
        )

    def _product_advice_response(self, product: dict[str, Any], intent: str) -> DialogflowCXResponse:
        title = str(product.get("title") or "Sản phẩm")
        metadata = product.get("metadata") or {}
        fields = {
            "product_spec": [
                ("Chip/hiệu năng", ["chip", "performance", "processor"]),
                ("RAM", ["ram"]),
                ("Màn hình", ["display", "screen", "refresh_rate"]),
                ("eSIM", ["esim", "sim"]),
            ],
            "product_camera": [
                ("Camera", ["camera"]),
                ("Chụp đêm", ["night_camera", "night_mode"]),
                ("Video", ["video", "stabilization"]),
                ("Selfie", ["selfie", "front_camera"]),
            ],
            "product_battery": [
                ("Pin", ["battery", "battery_life"]),
                ("Sạc", ["charging", "fast_charging"]),
            ],
            "product_gaming": [
                ("Hiệu năng", ["chip", "performance"]),
                ("Gaming", ["gaming", "use_case"]),
                ("Tản nhiệt", ["cooling", "thermal"]),
                ("Màn hình", ["display", "refresh_rate"]),
            ],
        }
        labels = {
            "product_spec": "Thông số",
            "product_camera": "Camera",
            "product_battery": "Pin và sạc",
            "product_gaming": "Khả năng chơi game",
        }
        lines = [f"{labels.get(intent, 'Thông tin')} của {title}:"]
        available = 0
        for label, keys in fields.get(intent, []):
            value = metadata_text(metadata, keys)
            if value != "Chưa cập nhật":
                available += 1
            lines.append(f"- {label}: {value}")
        if available == 0:
            lines.append("Shop chưa cập nhật đủ dữ liệu kỹ thuật chi tiết cho mẫu này.")
        return text_response(
            "\n".join(lines),
            {
                "current_product_id": product.get("id"),
                "current_product_handle": product.get("handle"),
                "current_product_name": title,
                "search_status": intent,
            },
        )

    async def inventory_status(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        product_name = self._resolve_product_name(request)
        print(f"DEBUG INVENTORY: resolved product_name='{product_name}'", flush=True)
        if not product_name:
            raise ProductNotFoundError()

        products = await self.medusa_client.list_products(query=product_name, limit=8)
        if not products:
            products = await self.medusa_client.list_products(limit=250)

        product = self._find_best_product(product_name, products)
        if not product:
            ranked = self._rank_products(product_name, products)
            if not ranked:
                ranked = self._find_brand_fallback_products(product_name, products)
            if ranked:
                return self._products_list_response(
                    ranked[:5],
                    title="Sản phẩm phù hợp",
                    intro=f"Mình chưa tìm thấy \"{product_name}\". Bạn có thể tham khảo các sản phẩm tương tự của cùng thương hiệu:",
                    status="product_list_fallback",
                    query=product_name,
                )
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

        extracted = extract_product_compare_names_from_text(request.text)
        if extracted[0] and extracted[1]:
            product_a_name, product_b_name = extracted
        else:
            product_a_name = product_a_name or extracted[0]
            product_b_name = product_b_name or extracted[1]

        if not product_a_name and not product_b_name:
            product_b_name = extract_single_compare_target_from_text(request.text)
            if product_b_name:
                product_a_name = (
                    request.get_parameter(self.CONTEXT_PRODUCT_PARAMETER_NAMES)
                    if is_product_context_followup(request.text)
                    else None
                )
        elif not product_a_name and product_b_name:
            product_a_name = (
                request.get_parameter(self.CONTEXT_PRODUCT_PARAMETER_NAMES)
                if is_product_context_followup(request.text)
                else None
            )
        elif product_a_name and not product_b_name:
            product_b_name = extract_single_compare_target_from_text(request.text)

        if not product_a_name or not product_b_name:
            raise ProductNotFoundError()

        products = await self.medusa_client.list_products(limit=100)
        product_a = self._find_best_product(product_a_name, products) if product_a_name else None
        product_b = self._find_best_product(product_b_name, products) if product_b_name else None

        if not product_a or not product_b:
            normalized_text = normalize_text(request.text or "")
            sorted_products_by_len = sorted(
                products,
                key=lambda p: len(normalize_text(str(p.get("title", "")))),
                reverse=True
            )
            found_products = []
            temp_text = normalized_text
            for p in sorted_products_by_len:
                p_title = normalize_text(str(p.get("title", "")))
                if not p_title:
                    continue
                pattern = rf"\b{re.escape(p_title)}\b"
                if re.search(pattern, temp_text):
                    found_products.append(p)
                    temp_text = re.sub(pattern, " ", temp_text)
                    if len(found_products) >= 2:
                        break
            
            if len(found_products) >= 2:
                product_a = found_products[0]
                product_b = found_products[1]
            elif len(found_products) == 1:
                if not product_a:
                    product_a = found_products[0]
                elif not product_b:
                    product_b = found_products[0]

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

        first_order = orders[0]
        recent_order_code = self._display_order_code(first_order, str(first_order.get("id") or ""))
        return text_response(
            "\n".join(lines),
            {
                "order_count": len(orders),
                "current_order_code": recent_order_code,
                "search_status": "success",
            },
        )

    async def bonus(self, request: DialogflowCXRequest) -> DialogflowCXResponse:
        promo_code = request.get_parameter(["promo_code", "promoCode", "code"])
        promo_code = promo_code or extract_promo_code_from_text(request.text)
        if promo_code:
            return text_response(
                promotion_code_message(promo_code),
                {
                    "promotion_code": promo_code.upper(),
                    "promotion_status": "available",
                    "search_status": "promotion_success",
                },
            )

        generic_request = is_generic_promotion_request(request.text)
        query = None if generic_request else request.get_parameter(self.SEARCH_PARAMETER_NAMES + self.PRODUCT_PARAMETER_NAMES)
        query = query or extract_promotion_product_from_text(request.text)
        if query and is_generic_product_reference(query):
            query = None
        if not query and not generic_request:
            query = extract_product_search_query_from_text(request.text)
        if query and is_generic_product_reference(query):
            query = None
        if not query and not generic_request and is_product_context_followup(request.text):
            query = request.get_parameter(self.CONTEXT_PRODUCT_PARAMETER_NAMES)
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

        subject = f"cho {query}" if query else "cho nhóm sản phẩm này"
        return text_response(
            f"Hiện mình chưa thấy chương trình khuyến mãi áp dụng {subject}. Bạn vẫn có thể hỏi mình giá từng sản phẩm cụ thể nhé.",
            {
                "promotion_status": "none",
                "search_status": "promotion_not_found",
                "current_product_name": query,
            },
        )

    async def order_tracking(
        self,
        request: DialogflowCXRequest,
        authorization_header: str | None = None,
    ) -> DialogflowCXResponse:
        order_code = request.get_parameter(self.ORDER_PARAMETER_NAMES)
        if order_code and not is_plausible_order_code(order_code, request):
            raise MissingOrderCodeError()
        
        if not order_code:
            if is_deictic_order_reference(request.text):
                raise MissingOrderCodeError()

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

        if not order_code or not is_plausible_order_code(order_code, request):
            raise MissingOrderCodeError()

        if not customer_access_token:
            raise AuthenticationRequiredError()

        order = await self.medusa_client.find_customer_order(order_code, customer_access_token=customer_access_token)
        if not order:
            raise OrderNotFoundError()
        return order

    @staticmethod
    def _find_brand_fallback_products(query: str, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_query = normalize_text(expand_product_abbreviations(query))
        detected_brand = None
        brand_map = {
            "iphone": "iphone",
            "apple": "iphone",
            "samsung": "samsung",
            "ss": "samsung",
            "xiaomi": "xiaomi",
            "oppo": "oppo",
            "vivo": "vivo",
            "realme": "realme",
            "google": "google pixel",
            "pixel": "google pixel"
        }
        for kw, b in brand_map.items():
            if re.search(rf"\b{re.escape(kw)}\b", normalized_query):
                detected_brand = b
                break
                
        if not detected_brand:
            return []
            
        fallback_products = []
        for p in products:
            p_title = normalize_text(str(p.get("title", "")))
            p_handle = normalize_text(str(p.get("handle", "")))
            haystack = f"{p_title} {p_handle}".strip()
            if detected_brand in haystack or (detected_brand == "samsung" and "ss" in haystack):
                fallback_products.append(p)
                
        return fallback_products

    @staticmethod
    def _find_best_product(query: str, products: list[dict[str, Any]]) -> dict[str, Any] | None:
        normalized_query = normalize_text(expand_product_abbreviations(query))
        best_product: dict[str, Any] | None = None
        best_score = 0.0

        for product in products:
            title = normalize_text(str(product.get("title", "")))
            handle = normalize_text(str(product.get("handle", "")))
            haystack = f"{title} {handle}".strip()

            if not haystack:
                continue
            if not catalog_candidate_matches_query(normalized_query, haystack):
                continue
            if title in normalized_query or handle in normalized_query:
                score = 1.0
            elif normalized_query in title or normalized_query in handle:
                score = 0.8
            else:
                score = SequenceMatcher(None, normalized_query, haystack).ratio()

            if score > best_score:
                best_score = score
                best_product = product

        threshold = 0.55 if is_specific_catalog_query(normalized_query) else 0.35
        return best_product if best_score >= threshold else None

    def _rank_products(self, query: str, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_query = normalize_text(expand_product_abbreviations(query))
        scored: list[tuple[float, dict[str, Any]]] = []

        for product in products:
            title = normalize_text(str(product.get("title", "")))
            handle = normalize_text(str(product.get("handle", "")))
            description = normalize_text(str(product.get("description", "")))
            haystack = f"{title} {handle} {description}".strip()
            if not haystack:
                continue
            if not catalog_candidate_matches_query(normalized_query, haystack):
                continue
            score = catalog_match_score(normalized_query, haystack)
            scored.append((score, product))

        threshold = 0.45 if is_specific_catalog_query(normalized_query) else 0.25
        return [product for score, product in sorted(scored, key=lambda item: item[0], reverse=True) if score >= threshold]

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

    def _get_lowest_price(self, product: dict[str, Any]) -> float:
        prices = self._extract_variant_prices(product)
        if not prices:
            return float('inf')
        return float(min(prices, key=lambda item: float(item["amount"]))["amount"])

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

        markdown = f"{title}: giá từ {price_text}. Khuyến mãi: {discount_text}."

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
        if explicit_product and is_plausible_product_name(explicit_product):
            return expand_product_abbreviations(explicit_product)

        extracted_product = extract_product_name_from_text(request.text)
        if extracted_product and not is_generic_product_reference(extracted_product) and is_plausible_product_name(extracted_product):
            return expand_product_abbreviations(extracted_product)

        # Try extracting product name directly from text (handles cases like "Ip15", "iPhone 12 giá")
        direct_name = extract_product_name_direct(request.text)
        if direct_name and not is_brand_only_name(direct_name) and is_plausible_product_name(direct_name):
            return direct_name

        context_product = request.get_parameter(self.CONTEXT_PRODUCT_PARAMETER_NAMES)
        if context_product and is_product_context_followup(request.text) and is_plausible_product_name(context_product):
            return context_product
            
        history = request.get_parameter(["history_products"])
        if history and is_product_context_followup(request.text):
            items = [x.strip() for x in str(history).split("|") if x.strip() and is_plausible_product_name(x.strip())]
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
        lines = [title, intro]
        product_payloads = []

        for product in products:
            prices = self._extract_variant_prices(product)
            lowest = min(prices, key=lambda item: float(item["amount"])) if prices else None
            price_text = format_money(lowest["amount"], lowest["currency"]) if lowest else "Chưa cập nhật giá"
            product_title = product.get("title") or "Sản phẩm"
            product_url = build_product_url(product)
            image_url = product.get("thumbnail") or first_image_url(product)
            discount_text = product_promotion_hint(product)

            lines.append(f"- {product_title}: {price_text}")

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
        else:
            parameters["current_product_id"] = None
            parameters["current_product_handle"] = None
            parameters["current_product_name"] = None
            parameters["current_product_price"] = None
            parameters["current_product_url"] = None
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


def first_text_message(response: DialogflowCXResponse) -> str | None:
    if not response.fulfillment_response.messages:
        return None
    message = response.fulfillment_response.messages[0]
    if not message.text or not message.text.text:
        return None
    return message.text.text[0]


def merge_session_parameters(request: DialogflowCXRequest, response: DialogflowCXResponse) -> None:
    merged = request_session_parameters(request)
    response_parameters: dict[str, Any | None] = {}
    if response.session_info:
        for key, value in response.session_info.parameters.items():
            unwrapped = unwrap_parameter_value(value)
            response_parameters[key] = unwrapped
            if unwrapped is not None:
                merged[key] = unwrapped
            else:
                if key in merged:
                    merged[key] = None

    refresh_product_context = any(
        response_parameters.get(key)
        for key in ["current_product_name", "current_product_id", "current_product_handle", "product_a_name", "product_b_name"]
    )
    clear_product_context = any(
        key in response_parameters and response_parameters[key] is None
        for key in ["current_product_name", "history_products"]
    )
    refresh_order_context = any(
        response_parameters.get(key)
        for key in ["current_order_code", "current_order_status"]
    )
    clear_order_context = any(
        key in response_parameters and response_parameters[key] is None
        for key in ["current_order_code"]
    )

    if "current_product_name" in merged and merged["current_product_name"]:
        current = str(merged["current_product_name"])
        history = str(merged.get("history_products") or "")
        history_list = [x.strip() for x in history.split("|") if x.strip()]
        
        if current in history_list:
            history_list.remove(current)
        history_list.insert(0, current)
        
        history_list = history_list[:2]
        merged["history_products"] = " | ".join(history_list)

    apply_short_context_ttl(
        merged,
        context_keys=IntentService.PRODUCT_CONTEXT_KEYS,
        ttl_key="product_context_turns_remaining",
        refresh=refresh_product_context,
        clear=clear_product_context,
    )
    apply_short_context_ttl(
        merged,
        context_keys=IntentService.ORDER_CONTEXT_KEYS,
        ttl_key="order_context_turns_remaining",
        refresh=refresh_order_context,
        clear=clear_order_context,
    )

    if "bot_final_message" in merged:
        del merged["bot_final_message"]

    if merged:
        response.session_info = SessionInfo(parameters=merged)


def apply_short_context_ttl(
    parameters: dict[str, Any],
    *,
    context_keys: list[str],
    ttl_key: str,
    refresh: bool,
    clear: bool,
) -> None:
    if clear:
        parameters[ttl_key] = None
        return
    if refresh:
        parameters[ttl_key] = 2
        return

    has_context = any(parameters.get(key) for key in context_keys if key != ttl_key)
    if not has_context:
        parameters[ttl_key] = None
        return

    try:
        raw_turns_remaining = parameters.get(ttl_key)
        if raw_turns_remaining in {None, ""}:
            parameters[ttl_key] = 1
            return
        turns_remaining = int(raw_turns_remaining)
    except (TypeError, ValueError):
        turns_remaining = 0

    turns_remaining -= 1
    if turns_remaining <= 0:
        for key in context_keys:
            parameters[key] = None
        parameters[ttl_key] = None
    else:
        parameters[ttl_key] = turns_remaining


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


def clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return None
    return text


def normalize_catalog_query(value: Any) -> str | None:
    text = clean_optional_text(value)
    if not text:
        return None

    cleaned = strip_product_noise(text)
    if not cleaned:
        return None

    normalized = normalize_text(cleaned)
    if is_generic_product_reference(cleaned) or normalized in {"phone", "smartphone"}:
        return None
    return expand_product_abbreviations(cleaned)


def is_brand_only_name(value: str) -> bool:
    return normalize_text(value) in KNOWN_PRODUCT_BRANDS


def is_specific_catalog_query(value: str | None) -> bool:
    normalized = normalize_text(value or "")
    if not normalized:
        return False
    if is_generic_product_reference(normalized):
        return False
    return (
        any(has_brand_word(normalized, brand) for brand in KNOWN_PRODUCT_BRANDS)
        or bool(re.search(r"\b(?:iphone|ip|samsung|galaxy|ss)?\s*\d{1,2}\b", normalized))
    )


def has_brand_word(normalized: str, brand: str) -> bool:
    return re.search(rf"\b{re.escape(normalize_text(brand))}\b", normalized) is not None


def query_required_qualifiers(normalized_query: str) -> set[str]:
    qualifiers: set[str] = set()
    if re.search(r"\bpro\s+max\b", normalized_query):
        qualifiers.update({"pro", "max"})
    elif re.search(r"\bpro\b", normalized_query):
        qualifiers.add("pro")
    if re.search(r"\bultra\b", normalized_query):
        qualifiers.add("ultra")
    if re.search(r"\bplus\b", normalized_query):
        qualifiers.add("plus")
    if re.search(r"\bmini\b", normalized_query):
        qualifiers.add("mini")
    if re.search(r"\bfe\b", normalized_query):
        qualifiers.add("fe")
    return qualifiers


def query_model_numbers(normalized_query: str) -> set[str]:
    return set(re.findall(r"\b(\d{1,2})\b", normalized_query))


def catalog_candidate_matches_query(normalized_query: str, normalized_haystack: str) -> bool:
    required_qualifiers = query_required_qualifiers(normalized_query)
    if any(qualifier not in normalized_haystack for qualifier in required_qualifiers):
        return False

    query_brands = {brand for brand in KNOWN_PRODUCT_BRANDS if has_brand_word(normalized_query, brand)}
    query_brands -= {"apple"} if "iphone" in query_brands else set()
    if query_brands and not any(has_brand_word(normalized_haystack, brand) for brand in query_brands):
        return False

    numbers = query_model_numbers(normalized_query)
    if numbers and not numbers.intersection(query_model_numbers(normalized_haystack)):
        return False

    return True


def catalog_match_score(normalized_query: str, normalized_haystack: str) -> float:
    if normalized_query in normalized_haystack:
        return 1.0
    if is_samsung_s_series_query(normalized_query) and re.search(r"\bs\d{1,2}\b", normalized_haystack):
        return 0.85

    query_tokens = set(normalized_query.split())
    haystack_tokens = set(normalized_haystack.split())
    if query_tokens:
        covered = sum(
            1
            for token in query_tokens
            if token in haystack_tokens or any(candidate.startswith(token) for candidate in haystack_tokens)
        )
        token_score = covered / len(query_tokens)
    else:
        token_score = 0.0

    sequence_score = SequenceMatcher(None, normalized_query, normalized_haystack).ratio()
    return max(token_score * 0.8, sequence_score)


def is_samsung_s_series_query(normalized_query: str) -> bool:
    return has_brand_word(normalized_query, "samsung") and re.search(r"\bs\b", normalized_query) is not None


def is_plausible_product_name(value: Any) -> bool:
    if not value:
        return False
    name = str(value).strip()
    if not name:
        return False
    normalized = normalize_text(name)
    if not normalized:
        return False
    if normalized.isdigit():
        return False
    if not any(char.isalpha() for char in normalized):
        return False
    if normalized in {"co", "khong", "co gi", "nao", "gi", "cua", "cho", "dung", "va", "hay", "voi", "hoac"}:
        return False
    return True


def is_plausible_order_code(value: Any, request: DialogflowCXRequest | None = None) -> bool:
    text = clean_optional_text(value)
    if not text:
        return False
    normalized = normalize_text(text)
    if re.search(r"\bord[-\s]?\d+\b", normalized):
        return True
    if re.fullmatch(r"\d{3,}", normalized):
        return True
    if re.fullmatch(r"\d{1,2}", normalized):
        if request:
            req_text = normalize_text(request.text or "")
            order_keywords = {"don", "order", "ma", "chi tiet", "code", "dh", "status", "trang thai", "check"}
            if any(kw in req_text for kw in order_keywords):
                return True
            session_params = request_session_parameters(request)
            if session_params.get("search_status") == "missing_order_code":
                return True
        return False
    return False


def extract_order_code_from_text(text: str | None, request: DialogflowCXRequest | None = None) -> str | None:
    if not text:
        return None
    normalized = normalize_text(text)
    match = re.search(r"\bord\s?(\d+)\b", normalized)
    if match:
        return f"ORD-{match.group(1)}"
    for num_match in re.finditer(r"\b\d+\b", normalized):
        num_str = num_match.group(0)
        if is_plausible_order_code(num_str, request):
            return num_str
    return None


def extract_promo_code_from_text(text: str | None) -> str | None:
    if not text:
        return None
    normalized = normalize_text(text)
    promo_codes = {"welcome10", "android15", "phone500k", "freeship", "preorder17"}
    for code in promo_codes:
        if re.search(rf"\b{re.escape(code)}\b", normalized):
            return code.upper()
    return None


def is_order_tracking_request(request: DialogflowCXRequest) -> bool:
    order_code = request.get_parameter(IntentService.ORDER_PARAMETER_NAMES)
    if order_code:
        return is_plausible_order_code(order_code, request)

    if re.fullmatch(r"\s*\d{1,2}\s*", request.text or ""):
        return False

    if extract_product_name_direct(request.text):
        return False

    if extract_product_search_query_from_text(request.text):
        return False

    if extract_budget(request.text) is not None:
        return False

    normalized = normalize_text(request.text or "")
    if not normalized:
        return False

    if re.search(r"\bord[-\s]?\d+\b", normalized) or re.search(r"\b\d{3,}\b", normalized):
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


def is_deictic_order_reference(text: str | None) -> bool:
    normalized = normalize_text(text or "")
    return any(
        phrase in normalized
        for phrase in [
            "don nay",
            "don do",
            "don kia",
            "don vua roi",
            "order nay",
            "order do",
        ]
    )


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
        r"^(?:cho xem|xem)\s+(.+?)\??$",
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

    normalized = normalize_text(cleaned)
    for brand in KNOWN_PRODUCT_BRANDS:
        if has_brand_word(normalized, brand):
            return brand

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
        "hom nay co uu dai",
        "hôm nay có ưu đãi",
        "hom nay shop co ma giam gia",
        "hôm nay shop có mã giảm giá",
        "khuyen mai gi cho khach moi",
        "khuyến mãi gì cho khách mới",
        "chuong trinh khuyen mai gi",
        "chương trình khuyến mãi gì",
    ]
    return any(phrase in normalized for phrase in generic_phrases)


def extract_product_compare_names_from_text(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None

    cleaned = " ".join(text.strip().split())
    patterns = [
        r"^(?:so sánh|so sanh)(?:\s+giúp mình|\s+giup minh)?(?:\s+cấu hình|\s+cau hinh)?\s+(?:giữa|giua)\s+(.+?)\s+(?:và|va|với|voi)\s+(.+?)(?:\s+(?:cái nào tốt hơn|cai nao tot hon|thì sao|thi sao))?\??$",
        r"^(?:thế còn|the con)?\s*(.+?)\s+(?:so với|so voi)\s+(.+?)(?:\s+(?:thì sao|thi sao|thế nào|the nao))?\??$",
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
    # Remove common filler words
    cleaned = re.sub(
        r"\b(của|cua|mẫu|mau|sản phẩm|san pham|cho tôi|cho toi|cho mình|cho minh|giúp mình|giup minh|giùm mình|gium minh|giúp tôi|giup toi)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Remove budget numbers and units (e.g. 25 triệu, 25tr, 25trieu, 25 củ)
    cleaned = re.sub(
        r"\b\d+(?:\.\d+)?\s*(triệu|trieu|tr|củ|cu|t|m)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Remove price relationship words
    cleaned = re.sub(
        r"\b(giá|gia|tầm|tam|khoảng|khoang|dưới|duoi|trên|tren|hơn|hon|đổ lại|do lai|đổ xuống|do xuong|từ|tu|đến|den)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Remove interrogative/filler words
    cleaned = re.sub(
        r"\b(nào|nao|gì|gi|thế nào|the nao|bao nhiêu|bao nhieu|đâu|dau|máy|may)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(mới nhất|moi nhat|dòng|dong|loại|loai|model|mẫu mới|mau moi)\b",
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
