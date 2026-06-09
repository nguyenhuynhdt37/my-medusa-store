import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { z } from "zod"
import { CHAT_MODULE } from "../../../../../modules/chat"

export const AUTHENTICATE = false

const LOG_PREFIX = "[chat:admin:presence]"

export const GET = async (req: MedusaRequest, res: MedusaResponse) => {
  const { id } = req.params
  const chatModuleService = req.scope.resolve(CHAT_MODULE)

  const presences = await chatModuleService.listChatPresences({ conversation_id: id })
  return res.json({ presences })
}

export const POST = async (req: MedusaRequest, res: MedusaResponse) => {
  const { id } = req.params
  console.info(`${LOG_PREFIX} request received`, { conversation_id: id })

  const schema = z.object({
    client_key: z.string(),
    user_id: z.string().nullable().optional(),
    guest_id: z.string().nullable().optional(),
    user_type: z.string().optional(),
    name: z.string().nullable().optional(),
    online: z.boolean().optional(),
    last_seen_at: z.string().optional(),
  })

  const parsed = schema.safeParse(req.body)
  if (!parsed.success) {
    console.error(`${LOG_PREFIX} invalid payload`, parsed.error.flatten())
    return res.status(400).json({ error: parsed.error })
  }

  const chatModuleService = req.scope.resolve(CHAT_MODULE)

  const { last_seen_at: lastSeenStr, ...restData } = parsed.data
  const last_seen_at = lastSeenStr ? new Date(lastSeenStr) : undefined

  // try to find existing presence by conversation + client_key
  const existing = await chatModuleService.listChatPresences({ conversation_id: id, client_key: parsed.data.client_key })
  let presence
  if (existing && existing.length > 0) {
    presence = await chatModuleService.updateChatPresences({
      ...restData,
      id: existing[0].id,
      conversation: id,
      last_seen_at,
    })
  } else {
    presence = await chatModuleService.createChatPresences({
      ...restData,
      conversation: id,
      last_seen_at,
    })
  }

  return res.json({ presence })
}
