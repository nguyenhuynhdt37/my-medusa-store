DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversation_status') THEN
    CREATE TYPE conversation_status AS ENUM ('BOT_ACTIVE', 'WAITING_AGENT', 'AGENT_ASSIGNED', 'AGENT_ACTIVE', 'CLOSED');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversation_owner') THEN
    CREATE TYPE conversation_owner AS ENUM ('BOT', 'AGENT', 'SYSTEM');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_direction') THEN
    CREATE TYPE message_direction AS ENUM ('INBOUND', 'OUTBOUND');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sender_type') THEN
    CREATE TYPE sender_type AS ENUM ('CUSTOMER', 'BOT', 'AGENT', 'SYSTEM');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_status') THEN
    CREATE TYPE message_status AS ENUM ('RECEIVED', 'PROCESSING', 'PROCESSED', 'SENT', 'FAILED');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assignment_status') THEN
    CREATE TYPE assignment_status AS ENUM ('ACTIVE', 'RELEASED', 'TRANSFERRED');
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  channel TEXT NOT NULL,
  channel_account_id TEXT NOT NULL,
  external_user_id TEXT NOT NULL,
  external_conversation_id TEXT,
  customer_id TEXT,
  guest_id TEXT,
  status conversation_status NOT NULL DEFAULT 'BOT_ACTIVE',
  current_owner conversation_owner NOT NULL DEFAULT 'BOT',
  assigned_agent_id TEXT,
  last_message_at TIMESTAMPTZ,
  last_customer_message_at TIMESTAMPTZ,
  last_agent_message_at TIMESTAMPTZ,
  last_bot_message_at TIMESTAMPTZ,
  handover_reason TEXT,
  handover_at TIMESTAMPTZ,
  returned_to_bot_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (channel, channel_account_id, external_user_id)
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  channel TEXT NOT NULL,
  external_message_id TEXT,
  direction message_direction NOT NULL,
  sender_type sender_type NOT NULL,
  sender_id TEXT,
  content_type TEXT NOT NULL DEFAULT 'text',
  content TEXT,
  payload JSONB,
  intent TEXT,
  confidence DOUBLE PRECISION,
  status message_status NOT NULL,
  error_message TEXT,
  correlation_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at TIMESTAMPTZ,
  metadata JSONB
);

CREATE UNIQUE INDEX IF NOT EXISTS messages_channel_external_message_id_uidx
  ON messages(channel, external_message_id)
  WHERE external_message_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS conversation_assignments (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  agent_id TEXT NOT NULL,
  assigned_by TEXT,
  status assignment_status NOT NULL DEFAULT 'ACTIVE',
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  released_at TIMESTAMPTZ,
  metadata JSONB
);

CREATE TABLE IF NOT EXISTS conversation_events (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  actor_type sender_type NOT NULL,
  actor_id TEXT,
  from_status conversation_status,
  to_status conversation_status,
  reason TEXT,
  payload JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversations_status_last_message_idx ON conversations(status, last_message_at DESC);
CREATE INDEX IF NOT EXISTS conversations_channel_status_idx ON conversations(channel, status);
CREATE INDEX IF NOT EXISTS conversations_assigned_agent_status_idx
  ON conversations(assigned_agent_id, status, last_message_at DESC)
  WHERE assigned_agent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS messages_conversation_created_idx ON messages(conversation_id, created_at ASC);
CREATE INDEX IF NOT EXISTS conversation_events_conversation_created_idx ON conversation_events(conversation_id, created_at ASC);
CREATE INDEX IF NOT EXISTS conversation_assignments_conversation_status_idx ON conversation_assignments(conversation_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS conversation_assignments_one_active_uidx
  ON conversation_assignments(conversation_id)
  WHERE status = 'ACTIVE';
