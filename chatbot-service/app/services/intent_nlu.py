from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

from app.services.escalation import is_explicit_handoff_request

IntentPredicate = Callable[[str, str | None], bool]


@dataclass(frozen=True)
class IntentRule:
    intent: str
    predicate: IntentPredicate
    priority: int
    description: str


@dataclass(frozen=True)
class IntentMatch:
    intent: str
    confidence: float
    rule: str


def normalize_text(value: str) -> str:
    lowered = value.lower().replace("đ", "d")
    without_marks = "".join(
        char for char in unicodedata.normalize("NFKD", lowered)
        if not unicodedata.combining(char)
    )
    return " ".join(without_marks.replace("-", " ").replace("_", " ").split())


def contains_any(normalized: str, keywords: list[str] | set[str] | tuple[str, ...]) -> bool:
    return any(normalize_text(keyword) in normalized for keyword in keywords)


def contains_any_word(normalized: str, keywords: list[str] | set[str] | tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(normalize_text(keyword))}\b", normalized) is not None for keyword in keywords)


def has_word(normalized: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(normalize_text(word))}\b", normalized) is not None


AFFIRMATION_PHRASES = {"da", "vang", "ok", "oke", "okay", "yes"}
AFFIRMATION_PREFIXES = ("ok ", "oke ", "okay ", "vang ", "da ")
AFFIRMATION_VOCATIVES = {"cau", "ban", "shop", "nha", "nhe", "a", "ạ"}
NEGATION_PHRASES = {"khong can", "khong can dau", "thoi", "khong co gi", "ko can", "k can", "ko can dau", "khong", "ko"}
GREETING_PHRASES = {"xin chao", "chao shop", "hello", "hi", "chao", "hey", "alo", "hi shop", "hey shop"}

BOT_REFERENCES = ["ban", "bot", "medusan", "tro ly", "em"]
COMPLIMENT_SIGNALS = [
    "dep trai",
    "dep giai",
    "dep zai",
    "djp zai",
    "djp trai",
    "xinh",
    "de thuong",
    "cute",
    "gioi qua",
    "gioi ghe",
    "gioi the",
    "thong minh",
    "thong thai",
    "tuyet voi",
    "tuyet nhat",
    "dang yeu",
]
COMPARISON_SIGNALS = [" ai ", " hon ", " so voi "]

COMPARE_EXCLUDE_TERMS = [
    "tang qua", "qua tang", "co qua", "duoc qua", "qua kem", "qua gi", "tang", "kem", "bao hanh", "doi tra", "doi may", "loi 1 doi 1",
    "ship", "giao hang", "momo", "vnpay", "chuyen khoan", "cod",
    "tra gop", "gop", "chuong trinh", "khuyen mai", "uu dai", "giam gia",
    "phu kien", "cu sac", "op lung", "tai nghe", "cuong luc"
]

ECOMMERCE_SIGNALS = [
    "ao", "quan", "hoodie", "jacket", "short", "vay", "giay", "size", "mau",
    "san pham", "hang", "shop", "mua", "gia", "tien", "khuyen mai",
    "uu dai", "giam gia", "ship", "giao hang", "bao hanh", "doi tra", "don hang",
    "iphone", "samsung", "dien thoai",
]
OFF_TOPIC_SIGNALS = [
    "dep trai", "xinh", "bong da", "messi", "ronaldo", "ca si", "dien vien",
    "nau pho", "nau an", "cong thuc mon", "chuyen co tich", "ke chuyen",
]

INTENT_ALIASES = {
    "cart add item": "cart_add_item",
    "cart update": "cart_update",
    "cart view": "cart_view",
    "checkout start": "checkout_start",
    "complaint": "complaint",
    "installment": "installment",
    "order cancel": "order_cancel",
    "order detail": "order_detail",
    "order history": "order_history",
    "order modify": "order_modify",
    "payment method": "payment_method",
    "product availability": "product_availability",
    "product battery": "product_battery",
    "product camera": "product_camera",
    "product gaming": "product_gaming",
    "product search": "product_search",
    "product price": "product_price",
    "product recommendation": "product_recommendation",
    "product spec": "product_spec",
    "promotion": "bonus",
    "bonus": "bonus",
    "inventory": "inventory",
    "product compare": "product_compare",
    "refund status": "refund_status",
    "return request": "return_request",
    "shipping tracking": "shipping_tracking",
    "store info": "store_info",
    "warranty": "warranty_policy",
    "warranty claim": "warranty_claim",
    "warranty policy": "warranty_policy",
    "shipping": "shipping_policy",
    "shipping policy": "shipping_policy",
    "order status": "order_tracking",
    "order tracking": "order_tracking",
    "order list": "order_list",
    "human handover": "human_handover",
    "human handoff": "human_handover",
    "greeting": "greeting",
    "fallback": "fallback",
}
ALLOWED_INTENTS = {
    "cart_add_item",
    "cart_update",
    "cart_view",
    "checkout_start",
    "complaint",
    "greeting",
    "installment",
    "order_cancel",
    "order_detail",
    "order_history",
    "order_modify",
    "payment_method",
    "product_availability",
    "product_battery",
    "product_camera",
    "product_gaming",
    "product_search",
    "product_price",
    "product_recommendation",
    "product_spec",
    "bonus",
    "inventory",
    "product_compare",
    "refund_status",
    "return_request",
    "shipping_tracking",
    "store_info",
    "warranty_claim",
    "warranty_policy",
    "shipping_policy",
    "order_tracking",
    "order_list",
    "human_handover",
    "fallback",
}

PRODUCT_ABBREVIATIONS = {
    # iPhone patterns
    r"\bip\s*(\d+)\s*(pro\s*max|pm)\b": r"iPhone \1 Pro Max",
    r"\bip\s*(\d+)\s*(pro|p)\b": r"iPhone \1 Pro",
    r"\bip\s*(\d+)\s*(plus)\b": r"iPhone \1 Plus",
    r"\bip\s*(\d+)\s*(mini)\b": r"iPhone \1 Mini",
    r"\bip\s*(\d+)\b": r"iPhone \1",
    r"\biphone\s*(\d+)\s*(pro\s*max|pm)\b": r"iPhone \1 Pro Max",
    r"\biphone\s*(\d+)\s*(pro|p)\b": r"iPhone \1 Pro",
    r"\biphone\s*(\d+)\s*(plus)\b": r"iPhone \1 Plus",
    r"\biphone\s*(\d+)\s*(mini)\b": r"iPhone \1 Mini",
    r"\bip\b": "iPhone",

    # Samsung patterns
    r"\b(?:ss|samsung|s)\s*(?:galaxy)?\s*s?\s*(\d+)\s*(ultra|u)\b": r"Samsung Galaxy S\1 Ultra",
    r"\b(?:ss|samsung|s)\s*(?:galaxy)?\s*s?\s*(\d+)\s*(plus)\b": r"Samsung Galaxy S\1 Plus",
    r"\b(?:ss|samsung|s)\s*(?:galaxy)?\s*s?\s*(\d+)\s*(fe)\b": r"Samsung Galaxy S\1 FE",
    r"\b(?:ss|samsung|s)\s*(?:galaxy)?\s*s?\s*(\d+)\b": r"Samsung Galaxy S\1",
    r"\b(?:ss|samsung|s)\s*(?:galaxy)?\s*a\s*(\d+)\b": r"Samsung Galaxy A\1",
    r"\bss\b": "Samsung",
}


CURATED_INTENT_PHRASE_GROUPS = {
    "greeting": ["hi", "alo shop", "hello shop", "chao shop nha", "xin chao ban"],
    "product_search": [
        "kiem iphone 16 pro max", "cho xem may oppo moi nhat", "shop ban xiaomi nao ngon",
        "con dien thoai nao tam 10 cu khong", "co samsung dong s khong", "tim dien thoai duoi 15 trieu",
    ],
    "product_price": ["gia con samsung s25 ultra", "iphone 16 gia nhieu", "ban 512gb cua iphone 16 pro max bao nhieu", "may nay gia sao", "bao gia giup minh"],
    "product_availability": ["may nay het hang chua", "con hang iphone 16 khong", "con mau den khong", "con ban 256gb khong", "co san tai shop khong"],
    "product_recommendation": ["can dien thoai pin khoe", "goi y dien thoai chup anh dep", "sinh vien nen mua may nao", "tu van cho minh dien thoai choi game", "mua may duoi 12 trieu nen chon gi"],
    "product_compare": ["con nao dang tien hon", "khac nhau cho nao", "iphone 16 voi s25 cai nao ngon hon", "nen chon xiaomi hay samsung", "so sanh giup minh 2 may nay"],
    "product_spec": ["co ho tro esim khong", "cau hinh may nay the nao", "ram bao nhieu vay", "dung chip gi", "man hinh bao nhieu hz"],
    "product_camera": ["quay video co rung khong", "camera co dep khong", "chup dem on chu", "may nao selfie dep", "chup chan dung ngon khong"],
    "product_battery": ["sac day mat bao lau", "ho tro sac nhanh bao nhieu w", "dung ca ngay noi khong", "pin dung duoc may tieng", "pin co trau khong"],
    "product_gaming": ["chien pubg max setting duoc khong", "may nao gaming ngon", "co nong may khong", "choi lien quan muot khong", "choi genshin on khong"],
    "bonus": [
        "dang co sale gi khong", "co tang qua kem khong", "hom nay co uu dai gi", 
        "ap duoc ma giam gia khong", "may nay co khuyen mai khong",
        "welcome10", "android15", "phone500k", "freeship", "preorder17",
        "ma welcome10", "ma android15", "ma phone500k", "ma freeship", "ma preorder17",
        "ma giam gia welcome10", "ma giam gia android15", "ma giam gia phone500k", "ma giam gia freeship", "ma giam gia preorder17",
    ],
    "installment": ["co 0 phan tram khong", "tra gop duoc khong", "gop 12 thang duoc chu", "can tra truoc bao nhieu", "tra gop qua the tin dung nha"],
    "payment_method": ["quet the duoc khong", "cod duoc chu", "thanh toan bang vnpay duoc khong", "nhan chuyen khoan khong", "co thanh toan momo khong"],
    "cart_add_item": ["bo san pham nay vao gio", "lay con nay luon", "them iphone 16 vao gio", "mua luon 2 cai", "cho minh dat 1 may"],
    "cart_view": ["trong gio con gi", "toi dang mua gi vay", "mo gio hang", "xem gio giup minh", "kiem tra gio"],
    "cart_update": ["tang len 2 san pham", "giam con 1 cai", "bo san pham nay di", "xoa iphone khoi gio", "sua gio hang"],
    "checkout_start": ["chot don", "thanh toan luon", "dat hang ngay", "mua ngay di", "tien hanh thanh toan"],
    "order_tracking": ["hang giao chua", "don dang xu ly a", "bao gio nhan duoc hang", "don cua minh toi dau roi", "check don giup minh"],
    "order_detail": ["toi mua nhung gi", "xem chi tiet don nay", "don nay gom gi vay", "tong tien bao nhieu", "xem thong tin don"],
    "order_history": ["nhung don da dat", "don truoc cua toi dau", "xem cac don cu", "lich su mua hang", "xem don gan day"],
    "order_cancel": ["dung don nay di", "huy don giup minh", "minh khong lay nua", "huy don hang nha", "cancel don"],
    "order_modify": ["doi nguoi nhan", "chinh lai don hang", "doi dia chi nhan hang", "sua so dien thoai", "thay doi thong tin giao hang"],
    "shipping_policy": ["ship bao nhieu tien", "giao toi ha noi mat may ngay", "co giao toan quoc khong", "thoi gian giao hang the nao", "ship nhanh duoc khong"],
    "shipping_tracking": ["theo doi don hang", "hang dang o dau", "check hanh trinh don hang", "tra van don giup minh", "shipper giao toi dau roi"],
    "return_request": ["chinh sach doi tra the nao", "doi may moi duoc chu", "muon doi tra san pham", "may loi thi doi sao", "tra hang duoc khong"],
    "refund_status": ["hoan tien toi dau roi", "da refund chua", "khi nao nhan lai tien", "tien hoan ve tai khoan chua", "kiem tra hoan tien"],
    "warranty_policy": ["loi phan cung xu ly the nao", "bao hanh o dau", "bao hanh may thang", "chinh sach bao hanh sao", "duoc bao hanh chinh hang khong"],
    "warranty_claim": ["may bi loi roi", "tao yeu cau bao hanh", "gui bao hanh giup minh", "can mang di bao hanh", "bao hanh san pham nay"],
    "complaint": ["giao hang lau vay", "toi khong hai long", "minh muon phan anh", "dich vu chan qua", "shop xu ly kieu gi the"],
    "store_info": ["co chi nhanh nao khong", "cua hang o dau", "may gio mo cua", "dia chi shop la gi", "cuoi tuan co mo khong"],
    "human_handover": ["can ho tro truc tiep", "gap cskh", "cho gap nhan vien", "chuyen minh sang tu van vien", "noi chuyen voi nguoi that"],
    "fallback": ["ke chuyen ma di", "thoi tiet hom nay the nao", "ai la tong thong my", "huong dan nau bun bo", "viet code python cho toi"],
}

CURATED_INTENT_PHRASES = {
    phrase: intent
    for intent, phrases in CURATED_INTENT_PHRASE_GROUPS.items()
    for phrase in phrases
}


def curated_intent_for_text(text: str | None) -> str | None:
    return CURATED_INTENT_PHRASES.get(normalize_text(text or ""))


def normalize_resolved_intent(value: Any) -> str | None:
    if not value:
        return None
    raw = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(value)).strip()
    raw = re.sub(r"\bintent\b", "", raw, flags=re.IGNORECASE)
    normalized = normalize_text(raw)
    resolved = INTENT_ALIASES.get(normalized, normalized.replace(" ", "_"))
    return resolved if resolved in ALLOWED_INTENTS else None


def parse_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def expand_product_abbreviations(text: str) -> str:
    if not text:
        return text
    result = text.strip()
    for pattern, replacement in PRODUCT_ABBREVIATIONS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip()


def is_generic_product_reference(value: str) -> bool:
    normalized = normalize_text(value)
    return normalized in {
        "gia",
        "bao nhieu",
        "gia bao nhieu",
        "san pham",
        "dien thoai",
        "nay",
        "cai nay",
        "may nay",
        "dien thoai nay",
        "san pham nay",
        "giam",
        "giam gia",
        "uu dai",
        "khuyen mai",
        "sale",
    }


def extract_product_name_direct(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    patterns = [
        r"(?:ip|iphone)\s*(\d+)\s*(pro\s*max|pro|plus|mini)?",
        r"(?:ss|samsung)\s*(?:galaxy)?\s*(s|a)?(\d+)\s*(ultra|plus|fe)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            expanded = expand_product_abbreviations(match.group(0))
            expanded = re.sub(r"\s+", " ", expanded).strip()
            if expanded and not is_generic_product_reference(expanded):
                return expanded
    return None


def is_bot_compliment(normalized: str) -> bool:
    if not normalized:
        return False
    if any(signal in f" {normalized} " for signal in COMPARISON_SIGNALS):
        return False
    return contains_any(normalized, BOT_REFERENCES) and contains_any(normalized, COMPLIMENT_SIGNALS)


def is_affirmation(normalized: str) -> bool:
    if normalized in AFFIRMATION_PHRASES:
        return True
    if normalized.startswith(AFFIRMATION_PREFIXES):
        rest = normalized.split(maxsplit=1)[1] if " " in normalized else ""
        return not rest or rest in AFFIRMATION_VOCATIVES
    return False


def is_probable_off_topic_text(text: str | None) -> bool:
    normalized = normalize_text(text or "")
    if not normalized:
        return False
    if contains_any(normalized, ECOMMERCE_SIGNALS):
        return False
    return contains_any(normalized, OFF_TOPIC_SIGNALS)


def is_product_context_followup(text: str | None) -> bool:
    normalized = normalize_text(text or "")
    if not normalized:
        return False

    followup_signals = [
        "gia",
        "bao nhieu",
        "bao tien",
        "bn",
        "bnh",
        "con hang",
        "con khong",
        "co hang",
        "het hang",
        "ton kho",
        "khuyen mai",
        "uu dai",
        "giam gia",
        "sale",
        "bao hanh",
        "doi tra",
        "thong so",
        "cau hinh",
        "camera",
        "pin",
        "mau",
        "size",
        "dung luong",
        "phien ban",
        "mua",
        "dat hang",
        "lay",
        "so voi",
        "voi",
        "thi sao",
        "the nao",
        "con cai nay",
        "cai nay",
        "may nay",
        "dien thoai nay",
        "san pham nay",
    ]
    return contains_any(normalized, followup_signals)


def is_reset_intent(text: str | None) -> bool:
    normalized = normalize_text(text or "")
    return bool(normalized) and contains_any(
        normalized,
        ["bat dau lai", "reset", "xoa lich su", "quen di", "noi chuyen khac"],
    )


def extract_budget(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(triệu|trieu|tr|củ)\b", text.lower())
    if match:
        return float(match.group(1)) * 1000000
    return None


def extract_budget_range(text: str | None) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    normalized = normalize_text(text)
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:trieu|tr|cu)?\s*(?:den|toi|\-|–)\s*(\d+(?:\.\d+)?)\s*(?:trieu|tr|cu)",
        normalized,
    )
    if range_match:
        low = float(range_match.group(1)) * 1000000
        high = float(range_match.group(2)) * 1000000
        return min(low, high), max(low, high)

    budget = extract_budget(text)
    if budget is None:
        return None, None
    if contains_any(normalized, ["duoi", "khong qua", "toi da", "do lai", "tro xuong"]):
        return None, budget
    if contains_any(normalized, ["tren", "tu", "tro len"]):
        return budget, None
    return None, budget


def _has_brand_or_digit(normalized: str) -> bool:
    brand_keywords = {"apple", "iphone", "samsung", "xiaomi", "oppo", "vivo", "realme", "google", "pixel", "ip", "ss"}
    if any(rf"\b{re.escape(brand)}\b" in normalized or brand in normalized.split() for brand in brand_keywords):
        return True
    if re.search(r"\d+", normalized):
        return True
    return False


def _has_compare(normalized: str, _: str | None) -> bool:
    if contains_any(normalized, ["nen mua may nao", "nen mua con nao", "mua may nao", "mua con nao", "mua dien thoai nao"]):
        return False
    if contains_any(normalized, ["so sanh", "khac nhau", "tot hon", "so voi"]):
        return True
    if contains_any(normalized, ["nen mua", "chon", "mua"]) and contains_any(normalized, [" va ", " voi ", " hay ", " hoac "]):
        if contains_any_word(normalized, COMPARE_EXCLUDE_TERMS):
            return False
        return _has_brand_or_digit(normalized)
    return False


def _has_generic_listing(normalized: str, _: str | None) -> bool:
    if "co giam" in normalized or "co gia" in normalized:
        return False
    return contains_any(normalized, ["co san pham", "san pham nao", "nhung san pham", "ban co gi"]) or has_word(normalized, "co gi")


def _has_inventory(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, ["con hang", "con khong", "co san", "ton kho", "het hang", "con ko", "co ko"])


def _has_order_list(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, [
        "don nao", "don hang nao", "co dat don", "toi co dat",
        "lich su don", "don da mua", "tung mua gi", "don gan day",
    ])


def _has_order_tracking(normalized: str, _: str | None) -> bool:
    if contains_any(normalized, ["kiem tra don", "trang thai don", "don hang toi", "don cua toi", "theo doi don", "ma don"]):
        return True
    if contains_any(normalized, ["don hang", "ma don", "don"]) and contains_any(
        normalized,
        ["trang thai", "kiem tra", "check", "tracking", "o dau", "dang o dau", "den dau", "ship"],
    ):
        return True
    return bool(re.search(r"\b(?:ord[-\s]?)?\d{3,}\b", normalized) and contains_any(normalized, ["don", "ord"]))


def _has_ranking_expensive(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, ["top", "cao nhat", "dat nhat", "gia cao"]) and contains_any(normalized, ["cao nhat", "dat nhat", "gia cao"])


def _has_ranking_cheap(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, ["re nhat", "gia thap", "thap nhat"])


def _has_greeting(normalized: str, _: str | None) -> bool:
    return normalized in GREETING_PHRASES or normalized.startswith(("xin chao ", "chao ", "hi ", "hey "))


def _has_shipping(normalized: str, _: str | None) -> bool:
    if contains_any(normalized, ["bao hanh", "doi tra", "hoan hang", "tra hang"]):
        return False
    return contains_any(normalized, [
        "phi ship", "phi giao", "bao lau giao", "may ngay", "giao nhanh",
        "freeship", "mien phi van chuyen",
    ])


def _has_price(normalized: str, _: str | None) -> bool:
    if re.search(r"\biphone\s*\d+", normalized) or re.search(r"\bsamsung\s", normalized):
        return True
    if re.search(r"\b(?:ip|iphone)\b", normalized) or re.search(r"\b(?:ss|samsung)\b", normalized):
        return True
    return contains_any(normalized, ["bao nhieu tien", "bao nhieu", "bao tien", "gia"])


def _has_abbreviated_product(normalized: str, _: str | None) -> bool:
    return bool(re.search(r"\bip\s*\d+", normalized) or re.search(r"\bss\s*[sa]?\d+", normalized))


def _has_order_cancel(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, ["huy don", "cancel don", "khong mua don", "khong mua nua"])


def _has_order_modify(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, [
        "doi dia chi don", "sua dia chi", "sua so dien thoai", "doi so dien thoai",
        "doi mau san pham trong don", "sua don", "thay doi don",
    ])


def _has_shipping_tracking(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, [
        "theo doi van chuyen", "theo doi van don", "ma van don",
        "shipper toi chua", "don dang giao", "giao toi dau",
    ])


def _has_order_detail(normalized: str, _: str | None) -> bool:
    if "chi tiet" in normalized:
        if any(kw in normalized for kw in ["don", "order", "ord", "dh"]) or re.search(r"\d+", normalized):
            return True
    return contains_any(normalized, [
        "chi tiet don", "don gom", "don nay gom", "tong tien don",
        "don hang mua san pham", "don hang cua toi gom",
        "xem thong tin don", "thong tin don",
    ])



INTENT_RULES = [
    IntentRule("human_handover", lambda _n, text: is_explicit_handoff_request(text), 1000, "explicit human handoff"),
    IntentRule("complaint", lambda n, _t: contains_any(n, ["khieu nai", "phan anh", "dich vu qua te", "ho tro qua cham"]), 990, "complaint"),
    IntentRule("order_cancel", _has_order_cancel, 980, "cancel order"),
    IntentRule("order_modify", _has_order_modify, 970, "modify order"),
    IntentRule("refund_status", lambda n, _t: contains_any(n, ["hoan tien", "refund", "tien ve chua"]), 960, "refund status"),
    IntentRule("return_request", lambda n, _t: contains_any(n, ["tra hang", "hoan hang", "doi may loi", "muon tra may", "doi may", "doi hang", "doi tra"]) and not contains_any(n, ["chinh sach", "quy dinh", "quy che"]), 950, "return request"),
    IntentRule("warranty_claim", lambda n, _t: contains_any(n, ["gui bao hanh", "can bao hanh", "may bi loi", "may sap nguon"]) and not contains_any(n, ["chinh sach", "quy dinh", "quy che"]), 940, "warranty claim"),
    IntentRule("cart_add_item", lambda n, _t: contains_any(n, ["them vao gio", "cho vao gio", "add cart", "them gio"]) or (contains_any(n, ["them", "bo", "cho", "add"]) and contains_any(n, ["vao"]) and contains_any(n, ["gio", "cart"])), 935, "add cart item"),
    IntentRule("cart_update", lambda n, _t: contains_any(n, ["xoa khoi gio", "bo khoi gio", "doi so luong", "cap nhat gio", "clear gio"]), 930, "update cart"),
    IntentRule("cart_view", lambda n, _t: contains_any(n, ["xem gio", "gio hang", "trong gio", "cart cua"]), 925, "view cart"),
    IntentRule("checkout_start", lambda n, _t: contains_any(n, ["checkout", "tien hanh thanh toan", "thanh toan don", "mua ngay"]), 920, "checkout"),
    IntentRule("installment", lambda n, _t: contains_any(n, ["tra gop", "installment"]), 915, "installment"),
    IntentRule("payment_method", lambda n, _t: contains_any(n, ["thanh toan gi", "momo", "vnpay", "chuyen khoan", "cod", "khi nhan hang", "the credit", "the tin dung", "banking", "thanh toan qua", "thanh toan bang", "thanh toan"]), 910, "payment method"),
    IntentRule("shipping_tracking", _has_shipping_tracking, 905, "shipping tracking"),
    IntentRule("order_detail", _has_order_detail, 900, "order detail"),
    IntentRule("product_compare", _has_compare, 900, "compare products"),
    IntentRule("store_info", lambda n, _t: contains_any(n, ["dia chi cua hang", "shop o dau", "gio mo cua", "shop mo cua", "so dien thoai shop"]), 895, "store information"),
    IntentRule("product_recommendation", lambda n, _t: contains_any(n, ["goi y", "de xuat", "tu van", "recommend", "nen mua may nao", "nen mua con nao", "mua may nao", "mua con nao", "mua dien thoai nao", "nen mua"]), 895, "recommendation"),
    IntentRule("product_camera", lambda n, _t: contains_any(n, ["camera", "chup anh", "chup dem", "quay video"]), 890, "camera advice"),
    IntentRule("product_battery", lambda n, _t: contains_any(n, ["pin trau", "pin khoe", "sac nhanh", "pin dung lau"]), 885, "battery advice"),
    IntentRule("product_gaming", lambda n, _t: contains_any(n, ["choi game", "gaming", "pubg", "lien quan"]), 880, "gaming advice"),
    IntentRule("product_spec", lambda n, _t: contains_any(n, ["cau hinh", "thong so", "dung chip", "ram bao nhieu", "man hinh"]), 875, "product specification"),
    IntentRule("product_search", _has_generic_listing, 880, "generic product listing"),
    IntentRule("inventory", _has_inventory, 860, "inventory keywords"),
    IntentRule("order_list", _has_order_list, 850, "customer order list"),
    IntentRule("order_tracking", _has_order_tracking, 840, "order tracking"),
    IntentRule("best_sellers", lambda n, _t: contains_any(n, ["ban chay", "hot nhat", "pho bien", "mua nhieu"]), 830, "best sellers"),
    IntentRule("top_cheap", _has_ranking_cheap, 820, "cheap ranking"),
    IntentRule("top_expensive", _has_ranking_expensive, 810, "expensive ranking"),
    IntentRule("greeting", _has_greeting, 800, "greeting"),
    IntentRule("smalltalk_compliment", lambda n, _t: is_bot_compliment(n), 790, "bot compliment"),
    IntentRule("smalltalk_affirmation", lambda n, _t: is_affirmation(n), 780, "affirmation"),
    IntentRule("smalltalk_negation", lambda n, _t: n in NEGATION_PHRASES, 770, "negation"),
    IntentRule("shipping_policy", _has_shipping, 760, "shipping"),
    IntentRule("warranty_policy", lambda n, _t: contains_any(n, ["bao hanh", "doi tra", "hoan tra", "may loi"]), 750, "warranty/returns"),
    IntentRule("bonus", lambda n, _t: contains_any(n, ["khuyen mai", "uu dai", "giam gia", "sale", "chuong trinh", "welcome10", "android15", "phone500k", "freeship", "preorder17"]) or contains_any_word(n, ["tang qua", "qua tang", "co qua", "duoc qua", "qua kem", "qua gi", "tang", "kem"]), 740, "promotion"),
    IntentRule("product_search", lambda n, _t: contains_any(n, ["tim", "kiem", "search", "xem", "cho xem", "co "]), 720, "search verbs"),
    IntentRule("product_search", lambda n, _t: contains_any(n, ["san pham", "mat hang", "co san pham", "co gi"]), 710, "product nouns"),
    IntentRule("product_price", _has_price, 700, "price/product model"),
    IntentRule("product_price", _has_abbreviated_product, 690, "abbreviated product model"),
]


def classify_intent(text: str | None) -> IntentMatch | None:
    normalized = normalize_text(text or "")
    if not normalized:
        return None
    curated_intent = CURATED_INTENT_PHRASES.get(normalized)
    if curated_intent:
        return IntentMatch(intent=curated_intent, confidence=1.0, rule="curated production utterance")
    for rule in sorted(INTENT_RULES, key=lambda item: item.priority, reverse=True):
        if rule.predicate(normalized, text):
            return IntentMatch(intent=rule.intent, confidence=1.0, rule=rule.description)
    return None


def infer_intent_from_text(text: str | None) -> str | None:
    match = classify_intent(text)
    return match.intent if match else None
    return None


def infer_intent_from_text(text: str | None) -> str | None:
    match = classify_intent(text)
    return match.intent if match else None
