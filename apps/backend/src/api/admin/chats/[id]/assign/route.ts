import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const { id } = req.params
  const adminId = (req as any).auth_context?.actor_id
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  
  const conversation = await chatModuleService.updateChatConversations({
    id: id,
    status: "IN_PROGRESS",
    assigned_admin_id: adminId,
    admin_started_at: new Date(),
    admin_metadata: {
      unread_admin_count: 0,
    },
  })

  console.info("[ADMIN_TAKEOVER]", {
    conversation_id: id,
    admin_id: adminId,
  })

  return res.json({ conversation })
}
