import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"
import { broadcastChatEvent } from "../../../../utils/chat-realtime"

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

  await broadcastChatEvent(id, "conversation.status.updated", { conversation }, true)
  await broadcastChatEvent(id, "chat.message.created", { ...message, conversation_id: id }, true)

  return res.json({ conversation })
}
