ALTER TABLE ai_usage
  ADD COLUMN IF NOT EXISTS duration_ms DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS memory_mb INTEGER;

CREATE TABLE IF NOT EXISTS daily_ai_usage (
  date DATE PRIMARY KEY,
  lex_requests INTEGER NOT NULL DEFAULT 0,
  gemini_prompt_tokens INTEGER NOT NULL DEFAULT 0,
  gemini_completion_tokens INTEGER NOT NULL DEFAULT 0,
  lambda_invocations INTEGER NOT NULL DEFAULT 0,
  total_cost_usd NUMERIC(14, 8) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS daily_ai_usage_date_idx ON daily_ai_usage(date DESC);
