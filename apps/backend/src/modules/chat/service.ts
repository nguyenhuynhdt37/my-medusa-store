import { MedusaService } from "@medusajs/framework/utils"
import { ChatSession } from "./models/chat-session"
import { ChatMessage } from "./models/chat-message"

class ChatService extends MedusaService({
  ChatSession,
  ChatMessage,
}) {}

export default ChatService
