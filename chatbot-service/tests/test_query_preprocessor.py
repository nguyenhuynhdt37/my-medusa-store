import unicodedata

from app.services.query_preprocessor import prepare_text_for_lex


def test_prepare_text_for_lex_normalizes_spacing_and_product_abbreviation():
    assert prepare_text_for_lex("  ip15   giá bao nhiêu  ") == "iPhone 15 giá bao nhiêu"


def test_prepare_text_for_lex_preserves_vietnamese_accents():
    text = "phí ship bao nhiêu"

    assert prepare_text_for_lex(text) == text


def test_prepare_text_for_lex_normalizes_unicode_to_nfc():
    decomposed = unicodedata.normalize("NFD", "điện thoại")

    assert prepare_text_for_lex(decomposed) == "điện thoại"
