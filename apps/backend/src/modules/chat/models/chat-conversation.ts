import { model } from "@medusajs/framework/utils"
import { ChatMessage } from "./chat-message"
import { CHAT_STATUSES } from "../status"

export const ChatConversation = model.define("chat_conversation", {
  id: model.id().primaryKey(),
  customer_id: model.text().searchable().nullable(),
  guest_id: model.text().searchable().nullable(),
  customer_name: model.text().searchable().nullable(),
  customer_email: model.text().searchable().nullable(),
  status: model.enum([...CHAT_STATUSES]).default("BOT_HANDLED"),
  assigned_admin_id: model.text().nullable(),
  escalation_reason: model.text().nullable(),
  admin_metadata: model.json().nullable(),
  escalated_at: model.dateTime().nullable(),
  admin_started_at: model.dateTime().nullable(),
  resolved_at: model.dateTime().nullable(),
  closed_at: model.dateTime().nullable(),
  last_message_at: model.dateTime().nullable(),
  messages: model.hasMany(() => ChatMessage, { mappedBy: "conversation" })
  ,
  presences: model.hasMany(() => (require("./chat-presence").ChatPresence), { mappedBy: "conversation" })
})
