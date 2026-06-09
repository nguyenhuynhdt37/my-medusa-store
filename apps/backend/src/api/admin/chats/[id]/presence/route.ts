import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"

export const AUTHENTICATE = false

const LOG_PREFIX = "[chat:admin:presence]"

export const GET = async (req: MedusaRequest, res: MedusaResponse) => {
  const { id } = req.params
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  const presences = await chatModuleService.listChatPresences(
    { conversation_id: id },
    { order: { updated_at: "DESC" } }
  )
  console.info(`${LOG_PREFIX} read`, {
    conversation_id: id,
    count: presences.length,
  })
  return res.json({ presences })
}

export const POST = async (req: MedusaRequest, res: MedusaResponse) => {
  const { id } = req.params
  const body = (req.body || {}) as any
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  const clientKey = body.client_key
  const now = body.last_seen_at ? new Date(body.last_seen_at) : new Date()

  console.info(`${LOG_PREFIX} request received`, {
    conversation_id: id,
    client_key: clientKey || null,
    user_type: body.user_type || null,
    online: body.online ?? null,
  })

  if (!clientKey) {
    return res.status(400).json({ error: "Missing client_key" })
  }

  const existing = await chatModuleService.listChatPresences({
    conversation_id: id,
    client_key: clientKey,
  })

  const payload = {
    client_key: clientKey,
    user_id: body.user_id || null,
    guest_id: body.guest_id || null,
    user_type: body.user_type || "guest",
    name: body.name || null,
    online: Boolean(body.online),
    last_seen_at: now,
    conversation_id: id,
  }

  if (existing[0]) {
    await chatModuleService.updateChatPresences({
      id: existing[0].id,
      ...payload,
    })
  } else {
    await chatModuleService.createChatPresences(payload)
  }

  console.info("[PRESENCE_UPDATED]", {
    conversation_id: id,
    client_key: clientKey,
    user_type: payload.user_type,
    online: payload.online,
    last_seen_at: now.toISOString(),
  })

  return res.status(204).send()
}
