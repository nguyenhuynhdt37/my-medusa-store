import { model } from "@medusajs/framework/utils"
import { ChatConversation } from "./chat-conversation"

export const ChatMessage = model.define("chat_message", {
  id: model.id().primaryKey(),
  sender_type: model.enum(["customer", "guest", "bot", "admin"]),
  sender_id: model.text().nullable(),
  customer_id: model.text().searchable().nullable(),
  guest_id: model.text().searchable().nullable(),
  channel: model.enum(["WEB", "MESSENGER"]).default("WEB"),
  external_message_id: model.text().nullable(),
  content: model.text(),
  metadata: model.json().nullable(),
  conversation: model.belongsTo(() => ChatConversation, { mappedBy: "messages" }),
})
