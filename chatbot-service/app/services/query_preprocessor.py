from __future__ import annotations

import re
import unicodedata

from app.services.intent_nlu import expand_product_abbreviations


def prepare_text_for_lex(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return expand_product_abbreviations(normalized)
