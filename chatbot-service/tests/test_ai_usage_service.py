from app.core.config import settings
from app.services.ai_usage_service import (
    cost_context_from_request_attributes,
    gemini_cost,
    lambda_cost,
    lex_cost,
)


def test_lex_cost_uses_text_request_count(monkeypatch):
    monkeypatch.setattr(settings, "lex_text_request_price_usd", 0.00075)

    assert lex_cost(3) == 0.00225


def test_gemini_cost_uses_prompt_and_candidate_tokens(monkeypatch):
    monkeypatch.setattr(settings, "gemini_input_price_per_1m_tokens_usd", 0.30)
    monkeypatch.setattr(settings, "gemini_output_price_per_1m_tokens_usd", 2.50)

    assert gemini_cost(prompt_tokens=1000, completion_tokens=500) == 0.00155


def test_lambda_cost_uses_invocation_duration_and_memory(monkeypatch):
    monkeypatch.setattr(settings, "lambda_request_price_per_1m_usd", 0.20)
    monkeypatch.setattr(settings, "lambda_duration_price_per_gb_second_usd", 0.0000166667)

    assert lambda_cost(duration_ms=1000, memory_mb=1024, request_count=1) == 0.00001687


def test_cost_context_reads_lex_request_attributes():
    context = cost_context_from_request_attributes(
        {
            "conversation_id": "conv_1",
            "customer_id": "cus_1",
            "guest_id": "",
            "external_user_id": "psid_1",
            "channel": "MESSENGER",
            "session_id": "fb_psid_1",
        }
    )

    assert context["conversation_id"] == "conv_1"
    assert context["customer_id"] == "cus_1"
    assert context["external_user_id"] == "psid_1"
    assert context["channel"] == "MESSENGER"


def test_cost_context_infers_messenger_psid_from_session_id():
    context = cost_context_from_request_attributes({}, fallback_session_id="fb_psid_2")

    assert context["external_user_id"] == "psid_2"
    assert context["channel"] == "MESSENGER"
