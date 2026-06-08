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
    status: "CLOSED",
    closed_at: new Date(),
  })

  console.info("[CONVERSATION_CLOSED]", {
    conversation_id: id,
  })

  return res.json({ conversation })
}
