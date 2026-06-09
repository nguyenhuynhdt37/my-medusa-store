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
    console.error(`[ADMIN_TAKEOVER_BROADCAST_FAILED] ${event}`, {
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
  const adminId = (req as any).auth_context?.actor_id
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  const currentConversation = await chatModuleService.retrieveChatConversation(id)
  const previousMetadata = (currentConversation.admin_metadata || {}) as Record<string, any>
  const now = new Date()
  
  const conversation = await chatModuleService.updateChatConversations({
    id: id,
    status: "IN_PROGRESS",
    assigned_admin_id: adminId,
    admin_started_at: now,
    admin_metadata: {
      ...previousMetadata,
      unread_admin_count: 0,
      takeover_started_at: now.toISOString(),
    },
  })

  console.info("[ADMIN_TAKEOVER]", {
    conversation_id: id,
    admin_id: adminId,
  })

  const message = await chatModuleService.createChatMessages({
    conversation_id: id,
    sender_type: "bot",
    sender_id: "system",
    content: "Nhân viên đã tiếp nhận hỗ trợ. Trợ lý AI sẽ tạm dừng phản hồi.",
    metadata: {
      system: true,
      event: "admin_takeover",
    },
  })

  await broadcastEvent(id, "conversation.status.updated", { conversation })
  await broadcastEvent(id, "chat.message.created", { ...message, conversation_id: id })

  return res.json({ conversation })
}
