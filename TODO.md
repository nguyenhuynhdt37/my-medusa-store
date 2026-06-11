# TODO: Fix Gemini always-calling + 429 rewrite issues

## Information gathered
- `/chatbot-service/app/api/chat_gateway.py` calls `infer_intent_from_text(text)` and then calls Lex; Gemini rewrite/normalization happens when `is_fallback` is true.
- However, the gateway still creates `gemini_client` via `Depends(get_gemini_client)` and doesn’t hard-disable it when rate-limited.
- `GeminiClient._generate_text_with_usage` retries on GeminiAPIError containing "429" (tenacity), but still can fail and bubble into the gateway logs.
- `IntentService._finalize_response` always rewrites the first customer-facing message through Gemini (if enabled), regardless of whether the intent is `product_price` or whether the reply is already good.

## Plan (code-level)
1. **Prevent Gemini from being called on every request**
   - In `IntentService._finalize_response`: gate rewrite behind a cheaper heuristic:
     - Only rewrite when `lex_intent` is `fallback` OR confidence is low OR message is a generic fallback.
     - Add opt-out for explicitly “easy” intents like `product_price`, `product_search`, `inventory` etc.
2. **Fix gateway flow**
   - In `chat_gateway.process_ai_request`: don’t attempt Gemini rewrite/normalization when `local_intent` is already `product_price` (or any detected specific intent).
   - Only run Gemini rewrite for fallback if Lex response truly contains fallback *and* local intent is not specific.
3. **Add rate-limit aware circuit breaker**
   - In `GeminiClient`: when a 429 occurs, set `self.enabled=False` for a short TTL (e.g., 60s) so the service stops calling Gemini until cooldown.
   - Ensure `GeminiClient.is_enabled()` respects this cooldown.
4. **Testing**
   - Run unit tests in `chatbot-service/tests` and add/adjust a test to assert Gemini rewrite is not invoked for `product_price` when local intent is recognized.

## Followup steps
- Run `pnpm`/`pytest`-related tests as per repo scripts.
- Validate by running the `/ai/process` endpoint and ensuring Gemini is not invoked for `product_price` happy-path.

