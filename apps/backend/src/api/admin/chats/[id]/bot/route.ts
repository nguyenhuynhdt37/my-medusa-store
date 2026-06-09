import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"

const SYSTEM_RETURN_TO_BOT_MESSAGE = "Nhân viên đã kết thúc hỗ trợ. Trợ lý AI sẽ tiếp tục hỗ trợ bạn."

const broadcastChatEvent = async (conversationId: string, event: string, data: any, notifyAdmin = false) => {
  try {
    await fetch("http://chatbot-service:8080/api/broadcast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        event,
        data,
        notify_admin: notifyAdmin,
      }),
    })
  } catch (err) {
    console.error("[RETURN_TO_BOT_BROADCAST_FAILED]", {
      conversation_id: conversationId,
      event,
      error: err instanceof Error ? err.message : err,
    })
  }
}

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
