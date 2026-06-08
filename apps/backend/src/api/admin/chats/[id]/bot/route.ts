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
    status: "BOT_HANDLED",
    assigned_admin_id: null,
    escalation_reason: null,
    admin_metadata: {
      unread_admin_count: 0,
      failed_response_count: 0,
    },
  })

  console.info("[RETURN_TO_BOT]", {
    conversation_id: id,
  })

  return res.json({ conversation })
}

