export type ChatMessage = {
  id: string;
  content: string;
  sender_type: "customer" | "guest" | "bot" | "admin";
  created_at: string;
  conversation_id?: string;
};

export type ChatConversation = {
  id: string;
  customer_id?: string | null;
  guest_id?: string | null;
  channel?: "WEB" | "MESSENGER";
  external_user_id?: string | null;
  customer_name?: string | null;
  customer_email?: string | null;
  status:
    | "BOT_HANDLED"
    | "WAITING_ADMIN"
    | "IN_PROGRESS"
    | "RESOLVED"
    | "CLOSED";
  last_message_at?: string | null;
  last_message_preview?: string | null;
  last_message_sender?: ChatMessage["sender_type"] | null;
  escalation_reason?: string | null;
  created_at?: string | null;
  admin_metadata?: {
    unread_admin_count?: number;
    last_customer_message_at?: string;
    last_admin_message_at?: string;
    auto_returned_at?: string;
    auto_return_reason?: string;
    customer_phone?: string;
    total_orders?: number;
    total_spent?: number;
    latest_order_id?: string;
    latest_order_at?: string;
    joined_at?: string;
    browser?: string;
    device?: string;
    country?: string;
    ip?: string;
    first_seen_at?: string;
  } | null;
};

export type ChatStatus = ChatConversation["status"];

export type ChatStats = {
  total_conversations: number;
  ai_handled_conversations: number;
  escalated_conversations: number;
  ai_resolution_rate: number;
  average_escalation_time_minutes: number | null;
  human_resolution_time_minutes: number | null;
};

export type ChatPresenceMap = Record<
  string,
  { online: boolean; last_seen_at?: string | null }
>;

export type ChatStatusFilter = "WAITING_ADMIN" | "IN_PROGRESS" | "CLOSED";

export type ChatView = "inbox" | "reports";

export type TranslateOptions = Record<string, unknown>;

export type Translate = (
  key: string,
  fallbackOrOptions?: string | TranslateOptions,
) => string;

export type StatusMeta = {
  label: string;
  shortLabel: string;
  description: string;
  badgeColor: "green" | "orange" | "blue" | "grey";
  dotClassName: string;
};
