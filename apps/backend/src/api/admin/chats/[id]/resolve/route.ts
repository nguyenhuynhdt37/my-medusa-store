import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const { id } = req.params
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  
  const conversation = await chatModuleService.updateChatConversations({
    id,
    status: "RESOLVED",
    resolved_at: new Date(),
    admin_metadata: {
      unread_admin_count: 0,
    },
  })

  console.info("[CONVERSATION_CLOSED]", {
    conversation_id: id,
    status: "RESOLVED",
  })

  return res.json({ conversation })
}

