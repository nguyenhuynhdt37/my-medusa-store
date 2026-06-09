import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"
import { broadcastChatEvent } from "../../../../utils/chat-realtime"

const SYSTEM_RETURN_TO_BOT_MESSAGE = "Nhân viên đã kết thúc hỗ trợ. Trợ lý AI sẽ tiếp tục hỗ trợ bạn."

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const { id } = req.params
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  
  const conversation = await chatModuleService.updateChatConversations({
    id,
    status: "BOT_HANDLED",
    assigned_admin_id: null,
    escalation_reason: null,
    admin_metadata: {
      unread_admin_count: 0,
      failed_response_count: 0,
    },
  })

  const message = await chatModuleService.createChatMessages({
    conversation_id: id,
    sender_type: "bot",
    sender_id: "system",
    content: SYSTEM_RETURN_TO_BOT_MESSAGE,
    metadata: {
      system: true,
      event: "returned_to_bot",
    },
  })

  console.info("[RETURN_TO_BOT]", {
    conversation_id: id,
  })

  await broadcastChatEvent(id, "conversation.status.updated", { conversation }, false)
  await broadcastChatEvent(id, "chat.message.created", { ...message, conversation_id: id }, false)

  return res.json({ conversation })
}
