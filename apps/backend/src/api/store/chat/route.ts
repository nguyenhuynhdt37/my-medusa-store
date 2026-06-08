import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { z } from "zod"
import { CHAT_MODULE } from "../../../modules/chat"

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const schema = z.object({
    session_id: z.string(),
    customer_id: z.string().optional().nullable(),
    sender: z.enum(["user", "bot", "human"]),
    text: z.string(),
    payload: z.any().optional(),
  })

  const parsed = schema.safeParse(req.body)
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error })
  }

  const data = parsed.data
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  
  // Tìm hoặc tạo session
  const sessions = await chatModuleService.listChatSessions({
    session_id: data.session_id,
  })
  
  let session = sessions[0]
  if (!session) {
    session = await chatModuleService.createChatSessions({
      session_id: data.session_id,
      customer_id: data.customer_id || null,
    })
  }

  // Tạo message
  const message = await chatModuleService.createChatMessages({
    session_id: session.id,
    sender: data.sender,
    text: data.text,
    payload: data.payload || null,
  })

  return res.json({ session, message })
}
