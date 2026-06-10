from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


ABUSIVE_LANGUAGE_MESSAGE = (
    "Mình có thể tiếp tục hỗ trợ nếu bạn giữ cuộc trò chuyện lịch sự. "
    "Bạn vui lòng đặt lại câu hỏi về sản phẩm, giá, khuyến mãi hoặc đơn hàng nhé."
)


@dataclass(frozen=True)
class ModerationResult:
    blocked: bool
    reason: str | None = None
    matched_term: str | None = None


BLACKLISTED_ABUSIVE_TERMS = {
    "dit",
    "dit me",
    "dm",
    "dmm",
    "du ma",
    "du me",
    "me may",
    "con cac",
    "cai lon",
    "loz",
    "lon",
    "cc",
    "cl",
    "clm",
    "clmm",
    "fuck",
    "fucking",
    "shit",
    "bitch",
}


def moderate_customer_message(message: str | None) -> ModerationResult:
    normalized = normalize_for_moderation(message)
    if not normalized:
        return ModerationResult(blocked=False)

    padded = f" {normalized} "
    for term in sorted(BLACKLISTED_ABUSIVE_TERMS, key=len, reverse=True):
        if f" {term} " in padded:
            return ModerationResult(blocked=True, reason="abusive_language", matched_term=term)

    return ModerationResult(blocked=False)


def normalize_for_moderation(value: str | None) -> str:
    text = (value or "").replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"([a-z])\1{2,}", r"\1\1", text)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text)).strip()
