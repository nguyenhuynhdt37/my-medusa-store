from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass
class EscalationResult:
    escalate: bool
    reason: str
    confidence: float | None = None


KEYWORD_GROUPS: list[tuple[str, list[str]]] = [
    ("complaint", ["khieu nai", "phan anh", "khong hai long", "chat luong kem", "phuc vu te"]),
    ("return_request", ["doi hang", "tra hang", "hoan hang"]),
    ("refund_request", ["hoan tien", "refund", "tra lai tien"]),
    ("payment_failed", ["thanh toan that bai", "bi tru tien", "khong thanh toan duoc"]),
    ("abnormal_order", ["giao sai", "giao thieu", "don hang mat", "chua nhan duoc hang"]),
    (
        "human_handoff",
        [
            "gap nhan vien",
            "gap nguoi that",
            "gap admin",
            "ho tro truc tiep",
            "noi chuyen voi nhan vien",
            "nhan vien dau",
            "admin dau",
            "cho gap nguoi",
        ],
    ),
]


def normalize(value: str | None) -> str:
    text = (value or "").replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text)).strip()


def should_escalate_to_admin(
    *,
    message: str,
    intent: str | None = None,
    confidence: float | None = None,
    failed_response_count: int = 0,
) -> EscalationResult:
    normalized_message = normalize(message)
    normalized_intent = normalize(intent)
    is_fallback_intent = normalized_intent in {"fallbackintent", "fallback"} or "fallback" in normalized_intent

    if normalized_intent == "humanhandoffintent" or "handover" in normalized_intent:
        return EscalationResult(True, "human_handoff", confidence)

    for reason, keywords in KEYWORD_GROUPS:
        if any(keyword in normalized_message for keyword in keywords):
            return EscalationResult(True, reason, confidence)

    if is_fallback_intent:
        return EscalationResult(False, "fallback_prompt", confidence)

    if failed_response_count >= 3:
        return EscalationResult(True, "repeated_ai_failure", confidence)

    if confidence is not None and confidence < 0.7:
        return EscalationResult(True, "low_confidence", confidence)

    return EscalationResult(False, "ai_handled", confidence)
