#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEX_ROOT = ROOT / "lex"
BOT_ROOT = LEX_ROOT / "EcomoiChatbot"
LOCALE_ROOT = BOT_ROOT / "BotLocales" / "en_US"


def identifier(seed: str) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    digest = hashlib.sha1(seed.encode("utf-8")).digest()
    value = int.from_bytes(digest, "big")
    return "".join(alphabet[(value >> (i * 5)) % len(alphabet)] for i in range(10))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def no_diacritics(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D")


def clean_utterance(text: str) -> str:
    text = text.replace("?", "").replace("!", "").replace(",", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def utterance_set(core: list[str], *, target: int = 60) -> list[dict[str, str]]:
    prefixes = [
        "",
        "shop ơi ",
        "shop oi ",
        "ad ơi ",
        "ad oi ",
        "bạn ơi ",
        "ban oi ",
        "cho mình hỏi ",
        "cho minh hoi ",
        "mình hỏi ",
        "minh hoi ",
    ]
    suffixes = [
        "",
        " giúp mình",
        " giup minh",
        " với shop",
        " voi shop",
        " nha",
        " nhé",
        " nhe",
        " ạ",
        " a",
    ]
    results: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> bool:
        candidate = clean_utterance(candidate)
        if candidate and candidate not in seen:
            seen.add(candidate)
            results.append(candidate)
        return len(results) >= target

    variants = [(phrase, no_diacritics(phrase)) for phrase in core]

    # Keep every authored phrase in the training set before adding conversational
    # expansions. Sequential expansion would otherwise exhaust the target on the
    # first phrase and silently discard the remaining intent examples.
    for phrase_variants in variants:
        for variant in phrase_variants:
            if add(variant):
                return [{"utterance": item} for item in results]

    for prefix in prefixes:
        for suffix in suffixes:
            for phrase_variants in variants:
                for variant in phrase_variants:
                    candidate = clean_utterance(f"{prefix}{variant}{suffix}")
                    if add(candidate):
                        return [{"utterance": item} for item in results]
    return [{"utterance": item} for item in results]


def next_step(action_type: str = "EndConversation", slot: str | None = None) -> dict:
    return {
        "sessionAttributes": None,
        "dialogAction": {
            "type": action_type,
            "slotToElicit": slot,
            "suppressNextMessage": None,
            "intentsInScope": None,
        },
        "intent": {"name": None, "slots": None},
    }


def intent_payload(name: str, description: str, utterances: list[str], slots: list[dict]) -> dict:
    slot_names = [slot["name"] for slot in slots]
    if name == "FallbackIntent":
        return {
            "name": name,
            "identifier": identifier(f"intent:{name}"),
            "displayName": None,
            "description": description,
            "parentIntentSignature": "AMAZON.FallbackIntent",
            "dialogCodeHook": {"enabled": True},
            "fulfillmentCodeHook": {
                "isActive": True,
                "postFulfillmentStatusSpecification": {
                    "failureResponse": None,
                    "failureNextStep": next_step(),
                    "successResponse": None,
                    "successNextStep": next_step(),
                    "timeoutResponse": None,
                    "timeoutNextStep": next_step(),
                },
                "fulfillmentUpdatesSpecification": None,
                "enabled": True,
            },
            "intentClosingSetting": None,
        }
    return {
        "name": name,
        "identifier": identifier(f"intent:{name}"),
        "displayName": None,
        "description": description,
        "parentIntentSignature": "AMAZON.FallbackIntent" if name == "FallbackIntent" else None,
        "sampleUtterances": utterance_set(utterances),
        "intentConfirmationSetting": None,
        "intentClosingSetting": None,
        "initialResponseSetting": {
            "conditional": None,
            "codeHook": {
                "isActive": True,
                "enableCodeHookInvocation": True,
                "invocationLabel": None,
                "postCodeHookSpecification": {
                    "failureResponse": None,
                    "failureNextStep": next_step(),
                    "failureConditional": None,
                    "successResponse": None,
                    "successNextStep": next_step("FulfillIntent"),
                    "successConditional": None,
                    "timeoutResponse": None,
                    "timeoutNextStep": next_step(),
                    "timeoutConditional": None,
                },
            },
            "nextStep": next_step("InvokeDialogCodeHook"),
            "initialResponse": None,
        },
        "inputContexts": None,
        "outputContexts": None,
        "kendraConfiguration": None,
        "qnAIntentConfiguration": None,
        "bedrockAgentIntentConfiguration": None,
        "qInConnectIntentConfiguration": None,
        "dialogCodeHook": {"enabled": True},
        "fulfillmentCodeHook": {
            "isActive": True,
            "postFulfillmentStatusSpecification": {
                "failureResponse": None,
                "failureNextStep": next_step(),
                "successResponse": None,
                "successNextStep": next_step(),
                "timeoutResponse": None,
                "timeoutNextStep": next_step(),
            },
            "fulfillmentUpdatesSpecification": None,
            "enabled": True,
        },
        "slotPriorities": [
            {"priority": index + 1, "slotName": slot_name}
            for index, slot_name in enumerate(slot_names)
        ] or None,
    }


def prompt_attempts() -> dict:
    attempt = {
        "allowedInputTypes": {"allowAudioInput": True, "allowDTMFInput": True},
        "audioAndDTMFInputSpecification": {
            "dtmfSpecification": {
                "maxLength": 513,
                "deletionCharacter": "*",
                "endCharacter": "#",
                "endTimeoutMs": 5000,
            },
            "startTimeoutMs": 4000,
            "audioSpecification": {"maxLengthMs": 15000, "endTimeoutMs": 640},
        },
        "allowInterrupt": True,
        "textInputSpecification": {"startTimeoutMs": 30000},
    }
    return {key: attempt for key in ["Initial", "Retry1", "Retry2", "Retry3", "Retry4"]}


def slot_payload(slot: dict) -> dict:
    return {
        "name": slot["name"],
        "identifier": identifier(f"slot:{slot['intent']}:{slot['name']}"),
        "description": slot.get("description"),
        "slotTypeName": slot["type"],
        "obfuscationSetting": None,
        "valueElicitationSetting": {
            "slotCaptureSetting": {
                "codeHook": None,
                "captureResponse": None,
                "captureNextStep": None,
                "captureConditional": None,
                "failureResponse": None,
                "failureNextStep": None,
                "failureConditional": None,
                "elicitationCodeHook": {
                    "enableCodeHookInvocation": True,
                    "invocationLabel": None,
                },
            },
            "slotConstraint": slot.get("constraint", "Optional"),
            "promptSpecification": {
                "messageGroupsList": [
                    {
                        "message": {
                            "ssmlMessage": None,
                            "customPayload": None,
                            "plainTextMessage": {
                                "value": slot.get("prompt", "Bạn bổ sung thêm thông tin giúp mình nhé.")
                            },
                            "imageResponseCard": None,
                        },
                        "variations": None,
                    }
                ],
                "maxRetries": 4,
                "allowInterrupt": True,
                "messageSelectionStrategy": "Random",
                "promptAttemptsSpecification": prompt_attempts(),
            },
            "defaultValueSpecification": None,
            "sampleUtterances": None,
            "waitAndContinueSpecification": None,
        },
        "multipleValuesSetting": None,
    }


def slot_type_payload(name: str, values: list[tuple[str, list[str]]], *, parent: str | None = None, regex: str | None = None) -> dict:
    expand = name in {"OrderId", "CustomerPhoneNumber", "Quantity"}
    payload = {
        "name": name,
        "identifier": identifier(f"slot-type:{name}"),
        "description": None,
        "slotTypeValues": None if parent else [
            {
                "synonyms": [{"value": synonym} for synonym in synonyms] or None,
                "sampleValue": {"value": value},
            }
            for value, synonyms in values
        ],
        "parentSlotTypeSignature": parent,
        "valueSelectionSetting": {
            "resolutionStrategy": "ORIGINAL_VALUE" if regex or parent or expand else "TOP_RESOLUTION",
            "advancedRecognitionSetting": {
                "audioRecognitionStrategy": "UseSlotValuesAsCustomVocabulary"
            } if not parent else None,
            "regexFilter": {"pattern": regex} if regex else None,
        },
    }
    return payload


PRODUCT_MODELS = [
    ("iPhone 11", ["ip11", "iphone mười một"]),
    ("iPhone 12", ["ip12", "iphone mười hai"]),
    ("iPhone 13", ["ip13"]),
    ("iPhone 14", ["ip14"]),
    ("iPhone 15", ["ip15", "iphone mười lăm"]),
    ("iPhone 15 Pro", ["ip15 pro"]),
    ("iPhone 15 Pro Max", ["ip15 prm", "ip15 promax"]),
    ("iPhone 16", ["ip16"]),
    ("iPhone 16 Plus", ["ip16 plus"]),
    ("iPhone 16 Pro", ["ip16 pro"]),
    ("iPhone 16 Pro Max", ["ip16 prm"]),
    ("iPhone 17", ["ip17"]),
    ("iPhone 17 Pro", ["ip17 pro"]),
    ("iPhone 17 Pro Max", ["ip17 prm"]),
    ("iPhone Air", ["iphone mỏng", "iphone air"]),
    ("Samsung Galaxy S24", ["s24"]),
    ("Samsung Galaxy S24 Ultra", ["s24 ultra"]),
    ("Samsung Galaxy S25", ["s25"]),
    ("Samsung Galaxy S25 Ultra", ["s25 ultra"]),
    ("Samsung Galaxy S26 Plus", ["s26 plus"]),
    ("Samsung Galaxy S26 Ultra", ["s26 ultra"]),
    ("Samsung Galaxy Z Fold7", ["fold7", "z fold 7"]),
    ("Samsung Galaxy Z Flip7", ["flip7", "z flip 7"]),
    ("Xiaomi 15 Ultra", ["mi 15 ultra"]),
    ("OPPO Find X8 Pro", ["find x8 pro"]),
    ("vivo X200 Pro", ["x200 pro"]),
    ("Nothing Phone 3", ["nothing 3"]),
    ("OnePlus 13", ["1plus 13"]),
    ("Google Pixel 10 Pro XL", ["pixel 10 pro xl"]),
]


SLOT_TYPES = {
    "BrandName": [
        ("Apple", ["iphone", "táo", "apple"]),
        ("Samsung", ["ss", "sam sung", "samsung"]),
        ("Xiaomi", ["mi", "xiaomi", "redmi"]),
        ("OPPO", ["oppo"]),
        ("Vivo", ["vivo"]),
        ("Realme", ["real me"]),
        ("OnePlus", ["one plus", "1plus"]),
        ("Google", ["pixel", "google pixel"]),
        ("Nothing", ["nothing phone"]),
    ],
    "ProductModel": PRODUCT_MODELS,
    "Color": [
        ("Đen", ["black", "màu đen"]),
        ("Trắng", ["white", "màu trắng"]),
        ("Xanh", ["blue", "xanh dương"]),
        ("Titan", ["titanium", "titan tự nhiên"]),
        ("Hồng", ["pink"]),
        ("Tím", ["purple"]),
        ("Vàng", ["gold"]),
    ],
    "Storage": [("64GB", ["64 g"]), ("128GB", ["128 g"]), ("256GB", ["256 g"]), ("512GB", ["512 g"]), ("1TB", ["1 tera"])],
    "RAM": [("4GB", []), ("6GB", []), ("8GB", []), ("12GB", []), ("16GB", []), ("24GB", [])],
    "Budget": [
        ("dưới 5 triệu", ["duoi 5 trieu", "5tr"]),
        ("dưới 10 triệu", ["duoi 10 trieu", "10tr"]),
        ("dưới 15 triệu", ["duoi 15 trieu", "15tr"]),
        ("dưới 20 triệu", ["duoi 20 trieu", "20tr"]),
        ("trên 20 triệu", ["tren 20 trieu", "cao cấp"]),
    ],
    "UsageNeed": [
        ("chơi game", ["gaming", "pubg", "liên quân", "free fire"]),
        ("học tập", ["đi học", "sinh viên"]),
        ("văn phòng", ["công việc", "work"]),
        ("chụp ảnh", ["camera đẹp", "sống ảo"]),
        ("quay video", ["vlog", "tiktok", "livestream"]),
        ("pin trâu", ["pin khoẻ", "dùng lâu"]),
        ("máy nhỏ gọn", ["compact", "gọn nhẹ"]),
    ],
    "PaymentMethod": [
        ("COD", ["tiền mặt", "thanh toán khi nhận"]),
        ("Momo", ["ví momo"]),
        ("VNPAY", ["vn pay"]),
        ("Banking", ["chuyển khoản", "bank"]),
        ("Credit Card", ["visa", "mastercard", "thẻ tín dụng"]),
        ("Installment", ["trả góp"]),
    ],
    "Province": [("Hà Nội", ["ha noi"]), ("TP Hồ Chí Minh", ["sài gòn", "hcm"]), ("Đà Nẵng", ["da nang"]), ("Cần Thơ", ["can tho"])],
    "District": [("Quận 1", ["q1"]), ("Quận 7", ["q7"]), ("Cầu Giấy", ["cau giay"]), ("Thủ Đức", ["thu duc"])],
    "PromoCode": [("WELCOME10", []), ("ANDROID15", []), ("PHONE500K", []), ("FREESHIP", []), ("PREORDER17", [])],
    "InstallmentTerm": [("3 tháng", ["3 thang"]), ("6 tháng", ["6 thang"]), ("9 tháng", ["9 thang"]), ("12 tháng", ["12 thang"])],
    "OrderId": [],
    "CustomerPhoneNumber": [],
    "Address": [("địa chỉ mới", ["dia chi moi", "nhà riêng", "công ty"])],
    "Quantity": [],
}


def slot(name: str, slot_type: str, prompt: str, constraint: str = "Optional") -> dict:
    return {"name": name, "type": slot_type, "prompt": prompt, "constraint": constraint}


INTENTS = [
    ("GreetingIntent", "Chào hỏi và mở hội thoại", ["xin chào", "hello", "hi shop", "chào shop", "shop ơi"], []),
    ("ProductSearchIntent", "Tìm điện thoại theo tên, hãng, nhu cầu, ngân sách", ["tôi muốn mua điện thoại", "muốn mua điện thoại", "tìm điện thoại", "mua điện thoại", "tìm {product_name}", "có điện thoại {brand} không", "tìm máy {need}", "điện thoại tầm {budget}", "shop có bán {product_name} không", "shop có {product_name} không"], [slot("product_name", "ProductModel", "Bạn muốn tìm mẫu điện thoại nào?"), slot("brand", "BrandName", "Bạn muốn tìm hãng nào?"), slot("need", "UsageNeed", "Bạn dùng máy cho nhu cầu gì?"), slot("budget", "Budget", "Ngân sách của bạn khoảng bao nhiêu?")]),
    ("ProductRecommendationIntent", "Tư vấn chọn điện thoại", ["tư vấn điện thoại", "gợi ý máy cho mình", "chọn giúp máy {need}", "mua máy tầm {budget}", "recommend điện thoại {brand}"], [slot("brand", "BrandName", "Bạn ưu tiên hãng nào?"), slot("budget", "Budget", "Ngân sách của bạn khoảng bao nhiêu?"), slot("need", "UsageNeed", "Bạn ưu tiên nhu cầu nào?")]),
    ("ProductPriceIntent", "Tra giá sản phẩm", ["giá {product_name}", "{product_name} bao nhiêu tiền", "bảng giá {brand}", "giá bản {storage} của {product_name}", "máy {product_name} giá sao"], [slot("product_name", "ProductModel", "Bạn muốn hỏi giá mẫu nào?"), slot("brand", "BrandName", "Bạn muốn xem giá hãng nào?"), slot("storage", "Storage", "Bạn muốn hỏi dung lượng nào?"), slot("color", "Color", "Bạn muốn hỏi màu nào?")]),
    ("ProductAvailabilityIntent", "Kiểm tra còn hàng theo mẫu, màu, dung lượng", ["{product_name} còn hàng không", "còn màu {color} của {product_name} không", "bản {storage} còn không", "shop còn máy này không", "có sẵn {product_name} không"], [slot("product_name", "ProductModel", "Bạn muốn kiểm tra mẫu nào?", "Required"), slot("color", "Color", "Bạn muốn màu nào?"), slot("storage", "Storage", "Bạn muốn dung lượng nào?"), slot("quantity", "Quantity", "Bạn cần bao nhiêu máy?")]),
    ("ProductCompareIntent", "So sánh hai mẫu điện thoại", ["so sánh {product_a} với {product_b}", "{product_a} và {product_b} máy nào tốt hơn", "nên mua {product_a} hay {product_b}", "compare {product_a} {product_b}"], [slot("product_a", "ProductModel", "Bạn muốn so sánh mẫu thứ nhất nào?"), slot("product_b", "ProductModel", "Bạn muốn so sánh với mẫu nào?")]),
    ("ProductSpecIntent", "Hỏi cấu hình, RAM, chip, màn hình", ["cấu hình {product_name}", "{product_name} ram bao nhiêu", "{product_name} dùng chip gì", "màn hình {product_name} thế nào", "thông số {product_name}"], [slot("product_name", "ProductModel", "Bạn muốn xem cấu hình mẫu nào?"), slot("ram", "RAM", "Bạn quan tâm RAM bao nhiêu?")]),
    ("ProductCameraIntent", "Hỏi camera, chụp ảnh, quay video", ["camera {product_name} đẹp không", "máy nào chụp ảnh đẹp", "điện thoại quay video tốt", "{product_name} chụp đêm ổn không"], [slot("product_name", "ProductModel", "Bạn muốn hỏi camera mẫu nào?"), slot("budget", "Budget", "Ngân sách của bạn khoảng bao nhiêu?")]),
    ("ProductBatteryIntent", "Hỏi pin và sạc", ["pin {product_name} dùng lâu không", "máy nào pin trâu", "{product_name} sạc nhanh không", "điện thoại pin khỏe tầm {budget}"], [slot("product_name", "ProductModel", "Bạn muốn hỏi pin mẫu nào?"), slot("budget", "Budget", "Ngân sách của bạn khoảng bao nhiêu?")]),
    ("ProductGamingIntent", "Tư vấn máy chơi game", ["máy chơi game tốt", "điện thoại chơi pubg mượt", "máy chơi liên quân tầm {budget}", "{product_name} chơi game ổn không"], [slot("product_name", "ProductModel", "Bạn muốn hỏi mẫu nào?"), slot("budget", "Budget", "Ngân sách của bạn khoảng bao nhiêu?")]),
    ("PromotionIntent", "Tra khuyến mãi và mã giảm giá", ["có khuyến mãi không", "mã {promo_code} dùng được không", "{product_name} có ưu đãi không", "shop có voucher gì", "giảm giá điện thoại {brand}"], [slot("product_name", "ProductModel", "Bạn muốn hỏi ưu đãi mẫu nào?"), slot("brand", "BrandName", "Bạn muốn hỏi ưu đãi hãng nào?"), slot("promo_code", "PromoCode", "Bạn muốn kiểm tra mã nào?")]),
    ("InstallmentIntent", "Tư vấn trả góp", ["mua trả góp {product_name}", "{product_name} trả góp sao", "trả góp qua thẻ tín dụng", "trả góp {installment_term} được không", "cần giấy tờ gì để trả góp"], [slot("product_name", "ProductModel", "Bạn muốn trả góp mẫu nào?"), slot("installment_term", "InstallmentTerm", "Bạn muốn trả góp trong bao lâu?"), slot("payment_method", "PaymentMethod", "Bạn muốn dùng phương thức nào?")]),
    ("PaymentMethodIntent", "Hỏi phương thức thanh toán", ["shop nhận thanh toán gì", "có cod không", "thanh toán momo được không", "có chuyển khoản không", "thẻ tín dụng có dùng được không"], [slot("payment_method", "PaymentMethod", "Bạn muốn hỏi phương thức nào?")]),
    ("CartAddItemIntent", "Thêm sản phẩm vào giỏ", ["thêm {product_name} vào giỏ", "mua {quantity} cái {product_name}", "add cart {product_name}", "lấy cho mình {product_name}", "cho vào giỏ hàng"], [slot("product_name", "ProductModel", "Bạn muốn thêm mẫu nào?", "Required"), slot("quantity", "Quantity", "Bạn muốn mua số lượng bao nhiêu?"), slot("color", "Color", "Bạn muốn màu nào?"), slot("storage", "Storage", "Bạn muốn dung lượng nào?")]),
    ("CartViewIntent", "Xem giỏ hàng", ["xem giỏ hàng", "giỏ của tôi có gì", "cart của mình", "kiểm tra giỏ hàng", "mở giỏ hàng"], []),
    ("CartUpdateIntent", "Cập nhật số lượng hoặc xoá giỏ", ["đổi số lượng trong giỏ", "xóa {product_name} khỏi giỏ", "bỏ sản phẩm trong giỏ", "cập nhật giỏ hàng", "clear giỏ hàng"], [slot("product_name", "ProductModel", "Bạn muốn cập nhật sản phẩm nào?"), slot("quantity", "Quantity", "Bạn muốn đổi thành số lượng bao nhiêu?")]),
    ("CheckoutStartIntent", "Hỗ trợ bắt đầu thanh toán", ["thanh toán đơn hàng", "checkout", "đặt hàng giúp mình", "mua ngay {product_name}", "tiến hành thanh toán"], [slot("product_name", "ProductModel", "Bạn muốn thanh toán sản phẩm nào?")]),
    ("ShippingPolicyIntent", "Chính sách vận chuyển", ["phí ship bao nhiêu", "bao lâu giao hàng", "giao về {province} mất mấy ngày", "có giao nhanh không", "freeship không"], [slot("province", "Province", "Bạn muốn giao tới tỉnh thành nào?"), slot("district", "District", "Bạn ở quận huyện nào?")]),
    ("ShippingTrackingIntent", "Theo dõi vận chuyển", ["đơn đang giao tới đâu", "theo dõi vận đơn", "shipper tới chưa", "tra vận chuyển đơn {order_id}", "mã vận đơn của tôi"], [slot("order_id", "OrderId", "Bạn cung cấp mã đơn giúp mình nhé.")]),
    ("OrderStatusIntent", "Tra trạng thái đơn hàng", ["đơn hàng của tôi đang ở đâu", "kiểm tra đơn {order_id}", "đơn em tới đâu rồi", "ad check dùm đơn hàng", "sao đơn hàng lâu vậy"], [slot("order_id", "OrderId", "Bạn vui lòng cung cấp mã đơn hàng.")]),
    ("OrderDetailIntent", "Xem chi tiết đơn hàng", ["chi tiết đơn {order_id}", "đơn này gồm những gì", "xem thông tin đơn hàng", "tổng tiền đơn {order_id}", "đơn hàng mua sản phẩm gì"], [slot("order_id", "OrderId", "Bạn vui lòng cung cấp mã đơn hàng.")]),
    ("OrderHistoryIntent", "Xem lịch sử đơn hàng", ["lịch sử đơn hàng", "các đơn đã mua", "tôi từng mua gì", "xem đơn gần đây", "danh sách đơn của tôi"], []),
    ("OrderCancelIntent", "Yêu cầu huỷ đơn", ["hủy đơn {order_id}", "tôi muốn hủy đơn {order_id}", "không mua nữa", "cancel đơn hàng", "hủy giúp đơn này", "đơn chưa giao thì hủy được không"], [slot("order_id", "OrderId", "Bạn muốn huỷ mã đơn nào?")]),
    ("OrderModifyIntent", "Đổi thông tin đơn hàng", ["đổi địa chỉ đơn {order_id}", "sửa số điện thoại nhận hàng", "đổi màu sản phẩm trong đơn", "thay đổi đơn hàng", "sửa đơn giúp mình"], [slot("order_id", "OrderId", "Bạn muốn sửa mã đơn nào?"), slot("address", "Address", "Bạn muốn đổi sang địa chỉ nào?"), slot("phone_number", "CustomerPhoneNumber", "Bạn muốn dùng số điện thoại nào?")]),
    ("ReturnRequestIntent", "Yêu cầu đổi trả", ["trả hàng như thế nào", "đổi máy lỗi", "muốn hoàn hàng", "đổi trả trong mấy ngày", "máy lỗi cần trả"], [slot("order_id", "OrderId", "Bạn cung cấp mã đơn để shop kiểm tra nhé."), slot("product_name", "ProductModel", "Bạn muốn đổi trả sản phẩm nào?")]),
    ("RefundStatusIntent", "Hỏi hoàn tiền", ["khi nào hoàn tiền", "tiền refund về chưa", "trạng thái hoàn tiền đơn {order_id}", "shop hoàn tiền giúp", "đã nhận refund chưa"], [slot("order_id", "OrderId", "Bạn cung cấp mã đơn giúp mình nhé.")]),
    ("WarrantyPolicyIntent", "Chính sách bảo hành", ["bảo hành {product_name} bao lâu", "chính sách bảo hành", "máy lỗi bảo hành sao", "đổi máy trong bao lâu", "{product_name} có bảo hành không"], [slot("product_name", "ProductModel", "Bạn muốn hỏi bảo hành mẫu nào?")]),
    ("WarrantyClaimIntent", "Tạo yêu cầu bảo hành", ["gửi bảo hành {product_name}", "máy bị lỗi cần bảo hành", "bảo hành đơn {order_id}", "shop nhận bảo hành không", "máy sập nguồn cần kiểm tra"], [slot("order_id", "OrderId", "Bạn cung cấp mã đơn giúp mình nhé."), slot("product_name", "ProductModel", "Bạn muốn bảo hành sản phẩm nào?")]),
    ("StoreInfoIntent", "Thông tin cửa hàng", ["shop ở đâu", "địa chỉ cửa hàng", "giờ mở cửa", "số điện thoại shop", "liên hệ cửa hàng"], [slot("province", "Province", "Bạn muốn tìm cửa hàng ở tỉnh thành nào?")]),
    ("ComplaintIntent", "Khiếu nại và phản ánh", ["tôi muốn khiếu nại", "dịch vụ quá tệ", "đơn giao lâu quá", "nhân viên hỗ trợ chậm", "shop xử lý giúp tôi"], []),
    ("HumanHandoffIntent", "Chuyển nhân viên", ["gặp nhân viên", "nói chuyện với người thật", "cho gặp tư vấn viên", "cần người hỗ trợ", "chuyển tổng đài"], []),
    ("FallbackIntent", "Fallback khi Lex không hiểu", [], []),
]


# Curated production utterances that were misclassified in the continuous
# single-session Lex smoke test. Keep these exact phrases in the intended class;
# utterance_set also adds accent-free variants and restrained conversational forms.
CURATED_UTTERANCES = {
    "GreetingIntent": ["hi", "alo shop", "hello shop", "chào shop nha", "xin chào bạn"],
    "ProductSearchIntent": [
        "kiếm iphone 16 pro max", "cho xem máy oppo mới nhất", "shop bán xiaomi nào ngon",
        "còn điện thoại nào tầm 10 củ không", "có samsung dòng s không",
        "tìm điện thoại dưới 15 triệu",
    ],
    "ProductRecommendationIntent": [
        "cần điện thoại pin khỏe", "gợi ý điện thoại chụp ảnh đẹp", "sinh viên nên mua máy nào",
        "tư vấn cho mình điện thoại chơi game", "mua máy dưới 12 triệu nên chọn gì",
    ],
    "ProductPriceIntent": [
        "giá con samsung s25 ultra", "iphone 16 giá nhiêu",
        "bản 512gb của iphone 16 pro max bao nhiêu", "máy này giá sao", "báo giá giúp mình",
    ],
    "ProductAvailabilityIntent": [
        "máy này hết hàng chưa", "còn hàng iphone 16 không", "còn màu đen không",
        "còn bản 256gb không", "có sẵn tại shop không",
    ],
    "ProductCompareIntent": [
        "con nào đáng tiền hơn", "khác nhau chỗ nào", "iphone 16 với s25 cái nào ngon hơn",
        "nên chọn xiaomi hay samsung", "so sánh giúp mình 2 máy này",
    ],
    "ProductSpecIntent": [
        "có hỗ trợ esim không", "cấu hình máy này thế nào", "ram bao nhiêu vậy",
        "dùng chip gì", "màn hình bao nhiêu hz",
    ],
    "ProductCameraIntent": [
        "quay video có rung không", "camera có đẹp không", "chụp đêm ổn chứ",
        "máy nào selfie đẹp", "chụp chân dung ngon không",
    ],
    "ProductBatteryIntent": [
        "sạc đầy mất bao lâu", "hỗ trợ sạc nhanh bao nhiêu w", "dùng cả ngày nổi không",
        "pin dùng được mấy tiếng", "pin có trâu không",
    ],
    "ProductGamingIntent": [
        "chiến pubg max setting được không", "máy nào gaming ngon", "có nóng máy không",
        "chơi liên quân mượt không", "chơi genshin ổn không",
    ],
    "PromotionIntent": [
        "đang có sale gì không", "có tặng quà kèm không", "hôm nay có ưu đãi gì",
        "áp được mã giảm giá không", "máy này có khuyến mãi không",
    ],
    "InstallmentIntent": [
        "có 0 phần trăm không", "trả góp được không", "góp 12 tháng được chứ",
        "cần trả trước bao nhiêu", "trả góp qua thẻ tín dụng nha",
    ],
    "PaymentMethodIntent": [
        "quẹt thẻ được không", "cod được chứ", "thanh toán bằng vnpay được không",
        "nhận chuyển khoản không", "có thanh toán momo không",
    ],
    "CartAddItemIntent": [
        "bỏ sản phẩm này vào giỏ", "lấy con này luôn", "thêm iphone 16 vào giỏ",
        "mua luôn 2 cái", "cho mình đặt 1 máy",
    ],
    "CartViewIntent": [
        "trong giỏ còn gì", "tôi đang mua gì vậy", "mở giỏ hàng", "xem giỏ giúp mình", "kiểm tra giỏ",
    ],
    "CartUpdateIntent": [
        "tăng lên 2 sản phẩm", "giảm còn 1 cái", "bỏ sản phẩm này đi",
        "xóa iphone khỏi giỏ", "sửa giỏ hàng",
    ],
    "CheckoutStartIntent": [
        "chốt đơn", "thanh toán luôn", "đặt hàng ngay", "mua ngay đi", "tiến hành thanh toán",
    ],
    "OrderStatusIntent": [
        "hàng giao chưa", "đơn đang xử lý à", "bao giờ nhận được hàng",
        "đơn của mình tới đâu rồi", "check đơn giúp mình",
    ],
    "OrderDetailIntent": [
        "tôi mua những gì", "xem chi tiết đơn này", "đơn này gồm gì vậy",
        "tổng tiền bao nhiêu", "xem thông tin đơn",
    ],
    "OrderHistoryIntent": [
        "những đơn đã đặt", "đơn trước của tôi đâu", "xem các đơn cũ",
        "lịch sử mua hàng", "xem đơn gần đây",
    ],
    "OrderCancelIntent": [
        "dừng đơn này đi", "hủy đơn giúp mình", "mình không lấy nữa", "hủy đơn hàng nha", "cancel đơn",
    ],
    "OrderModifyIntent": [
        "đổi người nhận", "chỉnh lại đơn hàng", "đổi địa chỉ nhận hàng",
        "sửa số điện thoại", "thay đổi thông tin giao hàng",
    ],
    "ShippingPolicyIntent": [
        "ship bao nhiêu tiền", "giao tới hà nội mất mấy ngày", "có giao toàn quốc không",
        "thời gian giao hàng thế nào", "ship nhanh được không",
    ],
    "ShippingTrackingIntent": [
        "theo dõi đơn hàng", "hàng đang ở đâu", "check hành trình đơn hàng",
        "tra vận đơn giúp mình", "shipper giao tới đâu rồi",
    ],
    "ReturnRequestIntent": [
        "chính sách đổi trả thế nào", "đổi máy mới được chứ", "muốn đổi trả sản phẩm",
        "máy lỗi thì đổi sao", "trả hàng được không",
    ],
    "RefundStatusIntent": [
        "hoàn tiền tới đâu rồi", "đã refund chưa", "khi nào nhận lại tiền",
        "tiền hoàn về tài khoản chưa", "kiểm tra hoàn tiền",
    ],
    "WarrantyPolicyIntent": [
        "lỗi phần cứng xử lý thế nào", "bảo hành ở đâu", "bảo hành mấy tháng",
        "chính sách bảo hành sao", "được bảo hành chính hãng không",
    ],
    "WarrantyClaimIntent": [
        "máy bị lỗi rồi", "tạo yêu cầu bảo hành", "gửi bảo hành giúp mình",
        "cần mang đi bảo hành", "bảo hành sản phẩm này",
    ],
    "ComplaintIntent": [
        "giao hàng lâu vậy", "tôi không hài lòng", "mình muốn phản ánh",
        "dịch vụ chán quá", "shop xử lý kiểu gì thế",
    ],
    "StoreInfoIntent": [
        "có chi nhánh nào không", "cửa hàng ở đâu", "mấy giờ mở cửa",
        "địa chỉ shop là gì", "cuối tuần có mở không",
    ],
    "HumanHandoffIntent": [
        "cần hỗ trợ trực tiếp", "gặp CSKH", "cho gặp nhân viên",
        "chuyển mình sang tư vấn viên", "nói chuyện với người thật",
    ],
}


FALLBACK_NEGATIVE_EXAMPLES = [
    "kể chuyện ma đi", "thời tiết hôm nay thế nào", "ai là tổng thống mỹ",
    "hướng dẫn nấu bún bò", "viết code python cho tôi",
]


def main() -> None:
    if BOT_ROOT.exists():
        shutil.rmtree(BOT_ROOT)
    (LOCALE_ROOT / "Intents").mkdir(parents=True, exist_ok=True)
    (LOCALE_ROOT / "SlotTypes").mkdir(parents=True, exist_ok=True)

    write_json(LEX_ROOT / "Manifest.json", {"metaData": {"schemaVersion": "1", "fileFormat": "LexJson", "resourceType": "BOT"}})
    write_json(
        BOT_ROOT / "Bot.json",
        {
            "name": "EcomoiChatbot",
            "version": "DRAFT",
            "description": "Production-oriented Vietnamese phone store chatbot for MedusaJS using Lex V2, Lambda and FastAPI.",
            "identifier": identifier("bot:EcomoiChatbot"),
            "errorLogSettings": {"enabled": False},
            "dataPrivacy": {"childDirected": False},
            "idleSessionTTLInSeconds": 300,
        },
    )
    write_json(
        LOCALE_ROOT / "BotLocale.json",
        {
            "name": "English (US)",
            "identifier": "en_US",
            "version": None,
            "description": "Vietnamese utterance training data for the en_US Lex locale.",
            "voiceSettings": {"voiceId": "Danielle", "engine": "neural"},
            "nluConfidenceThreshold": 0.4,
            "generativeAISettings": None,
            "speechDetectionSensitivity": "Default",
        },
    )

    for name, values in SLOT_TYPES.items():
        parent = None
        regex = None
        if name == "OrderId":
            values = [("12345", [])]
        elif name == "CustomerPhoneNumber":
            values = [("0912345678", [])]
        elif name == "Quantity":
            values = [("1", [])]
        write_json(LOCALE_ROOT / "SlotTypes" / name / "SlotType.json", slot_type_payload(name, values, parent=parent, regex=regex))

    for name, description, utterances, slots in INTENTS:
        utterances = [*utterances, *CURATED_UTTERANCES.get(name, [])]
        intent_dir = LOCALE_ROOT / "Intents" / name
        write_json(intent_dir / "Intent.json", intent_payload(name, description, utterances, slots))
        for item in slots:
            item = {**item, "intent": name}
            write_json(intent_dir / "Slots" / item["name"] / "Slot.json", slot_payload(item))

    print(f"Generated {len(INTENTS)} intents and {len(SLOT_TYPES)} slot types under {LOCALE_ROOT}")


if __name__ == "__main__":
    main()
