import { MedusaService } from "@medusajs/framework/utils"
import { ChatConversation } from "./models/chat-conversation"
import { ChatMessage } from "./models/chat-message"
import { ChatPresence } from "./models/chat-presence"

class ChatService extends MedusaService({
  ChatConversation,
  ChatMessage,
  ChatPresence,
}) { }

export default ChatService
