import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const { id } = req.params
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  
  const conversation = await chatModuleService.updateChatConversations({
    id: id,
    status: "WAITING_ADMIN",
    escalated_at: new Date(),
    escalation_reason: "manual_admin_handover",
  })

  console.info("[ESCALATED_TO_ADMIN]", {
    conversation_id: id,
    reason: "manual_admin_handover",
  })

  return res.json({ conversation })
}
