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
]
COMPARISON_SIGNALS = [" ai ", " hon", " voi ", " va "]

ECOMMERCE_SIGNALS = [
    "ao", "quan", "hoodie", "jacket", "short", "vay", "giay", "size", "mau",
    "san pham", "hang", "shop", "mua", "gia", "tien", "khuyen mai",
    "uu dai", "giam gia", "ship", "giao hang", "bao hanh", "doi tra", "don hang",
    "iphone", "samsung", "dien thoai",
]
OFF_TOPIC_SIGNALS = ["dep trai", "xinh", "bong da", "messi", "ronaldo", "ca si", "dien vien"]

INTENT_ALIASES = {
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
ALLOWED_INTENTS = {
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

PRODUCT_ABBREVIATIONS = {
    r"\bip\s*(\d+)": r"iPhone \1",
    r"\bip\s+(pro\s*max)": r"iPhone \1",
    r"\bip\s+(pro)": r"iPhone \1",
    r"\bip\s+(plus)": r"iPhone \1",
    r"\bip\b": "iPhone",
    r"\bss\s*(s\s*\d+)": r"Samsung Galaxy \1",
    r"\bss\s*(a\s*\d+)": r"Samsung Galaxy \1",
    r"\bss\b": "Samsung",
    r"\bsamsung\s+(s\s*\d+)": r"Samsung Galaxy \1",
    r"\bsamsung\s+(a\s*\d+)": r"Samsung Galaxy \1",
}


def normalize_resolved_intent(value: Any) -> str | None:
    if not value:
        return None
    normalized = normalize_text(str(value))
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
        "gia", "bao nhieu", "gia bao nhieu", "san pham", "dien thoai",
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
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            expanded = expand_product_abbreviations(cleaned)
            expanded = re.sub(
                r"\s*(?:gia|giá|bao nhieu|bao nhiêu|the nao|thế nào|bnh|bn|em|ạ|ah|nha|nhé|a|à)\s*",
                " ",
                expanded,
                flags=re.IGNORECASE,
            ).strip()
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


def _has_compare(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, ["so sanh", "khac nhau", "tot hon", "nen mua"]) and contains_any(normalized, [" va ", " voi "])


def _has_generic_listing(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, ["co san pham", "san pham nao", "nhung san pham", "ban co gi", "co gi"])


def _has_inventory(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, ["con hang", "con khong", "co san", "ton kho", "het hang", "con ko", "co ko"])


def _has_order_list(normalized: str, _: str | None) -> bool:
    return contains_any(normalized, ["don nao", "don hang nao", "co dat don", "toi co dat"])


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
    return contains_any(normalized, ["ship", "van chuyen", "phi ship", "freeship", "mien phi van chuyen"])


def _has_price(normalized: str, _: str | None) -> bool:
    if re.search(r"\biphone\s*\d+", normalized) or re.search(r"\bsamsung\s", normalized):
        return True
    if re.search(r"\b(?:ip|iphone)\b", normalized) or re.search(r"\b(?:ss|samsung)\b", normalized):
        return True
    return contains_any(normalized, ["bao nhieu tien", "bao nhieu", "bao tien", "gia"])


def _has_abbreviated_product(normalized: str, _: str | None) -> bool:
    return bool(re.search(r"\bip\s*\d+", normalized) or re.search(r"\bss\s*[sa]?\d+", normalized))


INTENT_RULES = [
    IntentRule("human_handover", lambda _n, text: is_explicit_handoff_request(text), 1000, "explicit human handoff"),
    IntentRule("product_compare", _has_compare, 900, "compare products"),
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
    IntentRule("bonus", lambda n, _t: contains_any(n, ["khuyen mai", "uu dai", "giam gia", "sale", "chuong trinh"]), 740, "promotion"),
    IntentRule("product_recommendation", lambda n, _t: contains_any(n, ["goi y", "de xuat", "tu van", "recommend"]), 730, "recommendation"),
    IntentRule("product_search", lambda n, _t: contains_any(n, ["tim", "kiem", "search", "xem", "cho xem", "co "]), 720, "search verbs"),
    IntentRule("product_search", lambda n, _t: contains_any(n, ["san pham", "mat hang", "co san pham", "co gi"]), 710, "product nouns"),
    IntentRule("product_price", _has_price, 700, "price/product model"),
    IntentRule("product_price", _has_abbreviated_product, 690, "abbreviated product model"),
]


def classify_intent(text: str | None) -> IntentMatch | None:
    normalized = normalize_text(text or "")
    if not normalized:
        return None
    for rule in sorted(INTENT_RULES, key=lambda item: item.priority, reverse=True):
        if rule.predicate(normalized, text):
            return IntentMatch(intent=rule.intent, confidence=1.0, rule=rule.description)
    return None


def infer_intent_from_text(text: str | None) -> str | None:
    match = classify_intent(text)
    return match.intent if match else None
