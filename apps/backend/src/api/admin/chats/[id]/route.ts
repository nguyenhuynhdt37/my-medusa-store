import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../modules/chat"

export const GET = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const { id } = req.params
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  
  const conversation = await chatModuleService.retrieveChatConversation(id)
  
  if (!conversation) {
    return res.status(404).json({ error: "Conversation not found" })
  }

  return res.json({ conversation })
}
