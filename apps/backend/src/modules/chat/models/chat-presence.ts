import { model } from "@medusajs/framework/utils"
import { ChatConversation } from "./chat-conversation"

export const ChatPresence = model.define("chat_presence", {
  id: model.id().primaryKey(),
  client_key: model.text().nullable(),
  user_id: model.text().nullable(),
  guest_id: model.text().nullable(),
  user_type: model.text(),
  name: model.text().nullable(),
  online: model.boolean().default(false),
  last_seen_at: model.dateTime().nullable(),
  conversation: model.belongsTo(() => ChatConversation, { mappedBy: "presences" }),
})
