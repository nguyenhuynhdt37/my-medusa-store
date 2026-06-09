import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"

const broadcastEvent = async (conversationId: string, event: string, data: any) => {
  try {
    await fetch("http://chatbot-service:8080/api/broadcast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        event,
        data,
        notify_admin: true,
      }),
    })
  } catch (err) {
    console.error(`[CONVERSATION_CLOSE_BROADCAST_FAILED] ${event}`, {
      conversation_id: conversationId,
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
  const currentConversation = await chatModuleService.retrieveChatConversation(id)
  const previousMetadata = (currentConversation.admin_metadata || {}) as Record<string, any>
  
  const conversation = await chatModuleService.updateChatConversations({
    id: id,
    status: "BOT_HANDLED",
    assigned_admin_id: null,
    escalation_reason: null,
    admin_metadata: {
      ...previousMetadata,
      unread_admin_count: 0,
      failed_response_count: 0,
    },
    closed_at: new Date(),
  })

  console.info("[CONVERSATION_CLOSED_AND_RETURNED_TO_BOT]", {
    conversation_id: id,
  })

  const message = await chatModuleService.createChatMessages({
    conversation_id: id,
    sender_type: "bot",
    sender_id: "system",
    content: "👨‍💼 Nhân viên đã kết thúc hỗ trợ.\n🤖 Trợ lý Medusan sẽ tiếp tục hỗ trợ bạn.",
    metadata: {
      system: true,
      event: "returned_to_bot",
    },
  })

  await broadcastEvent(id, "conversation.status.updated", { conversation })
  await broadcastEvent(id, "chat.message.created", { ...message, conversation_id: id })

  return res.json({ conversation })
}
