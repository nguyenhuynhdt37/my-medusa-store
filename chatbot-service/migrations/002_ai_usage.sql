CREATE TABLE IF NOT EXISTS ai_usage (
  id TEXT PRIMARY KEY,
  conversation_id TEXT,
  customer_id TEXT,
  guest_id TEXT,
  external_user_id TEXT,
  channel TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT,
  operation TEXT NOT NULL,
  intent TEXT,
  request_count INTEGER NOT NULL DEFAULT 1,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  total_tokens INTEGER,
  estimated_cost_usd NUMERIC(14, 8) NOT NULL DEFAULT 0,
  unit_prices JSONB,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_usage_created_idx ON ai_usage(created_at DESC);
CREATE INDEX IF NOT EXISTS ai_usage_conversation_idx ON ai_usage(conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_usage_customer_idx ON ai_usage(customer_id, guest_id, external_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_usage_provider_idx ON ai_usage(provider, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_usage_intent_idx ON ai_usage(intent, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_usage_channel_idx ON ai_usage(channel, created_at DESC);
