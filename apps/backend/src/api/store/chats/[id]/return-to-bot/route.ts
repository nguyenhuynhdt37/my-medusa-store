import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"

const SYSTEM_CUSTOMER_CANCEL_SUPPORT_MESSAGE = "Yêu cầu hỗ trợ đã được hủy. Trợ lý AI sẽ tiếp tục hỗ trợ bạn."

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
    console.error("[STORE_RETURN_TO_BOT_BROADCAST_FAILED]", {
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
  const guestId = (req.body as any)?.guest_id || null
  const customerId = (req as any).auth_context?.actor_type === "customer" ? (req as any).auth_context.actor_id : null
  const chatModuleService = req.scope.resolve(CHAT_MODULE)

  const current = await chatModuleService.retrieveChatConversation(id)
  const ownsConversation =
    (customerId && current.customer_id === customerId) ||
    (guestId && current.guest_id === guestId)

  if (!ownsConversation) {
    return res.status(403).json({ error: "Conversation does not belong to this user" })
  }

  if (current.status === "IN_PROGRESS") {
    return res.status(403).json({ error: "Only Admin can return an active support session to bot" })
  }

  if (current.status !== "WAITING_ADMIN") {
    return res.status(409).json({ error: "Conversation is not waiting for Admin" })
  }

  const conversation = await chatModuleService.updateChatConversations({
    id,
    status: "BOT_HANDLED",
    assigned_admin_id: null,
    admin_metadata: {
      ...((current.admin_metadata || {}) as Record<string, any>),
      unread_admin_count: 0,
      support_request_cancelled_at: new Date().toISOString(),
    },
  })

  const message = await chatModuleService.createChatMessages({
    conversation_id: id,
    sender_type: "bot",
    sender_id: "system",
    content: SYSTEM_CUSTOMER_CANCEL_SUPPORT_MESSAGE,
    metadata: {
      system: true,
      event: "customer_cancelled_support_request",
    },
  })

  await broadcastChatEvent(id, "conversation.status.updated", { conversation }, false)
  await broadcastChatEvent(id, "chat.message.created", { ...message, conversation_id: id }, false)

  return res.json({ conversation, message })
}
