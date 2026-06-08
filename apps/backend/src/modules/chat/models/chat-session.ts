import { model } from "@medusajs/framework/utils"
import { ChatMessage } from "./chat-message"

export const ChatSession = model.define("chat_session", {
  id: model.id().primaryKey(),
  session_id: model.text().searchable().unique(),
  customer_id: model.text().nullable(),
  status: model.enum(["bot_active", "human_active"]).default("bot_active"),
  messages: model.hasMany(() => ChatMessage, { mappedBy: "session" })
})
