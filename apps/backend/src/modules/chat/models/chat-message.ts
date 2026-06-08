import { model } from "@medusajs/framework/utils"
import { ChatSession } from "./chat-session"

export const ChatMessage = model.define("chat_message", {
  id: model.id().primaryKey(),
  sender: model.enum(["user", "bot", "human"]),
  text: model.text(),
  payload: model.json().nullable(),
  session: model.belongsTo(() => ChatSession, { mappedBy: "messages" }),
})
