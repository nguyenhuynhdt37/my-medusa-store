import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { z } from "zod"
import { CHAT_MODULE } from "../../../../../modules/chat"

const LOG_PREFIX = "[chat:admin:messages]"

export const GET = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const { id } = req.params
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  
  const messages = await chatModuleService.listChatMessages(
    { conversation_id: id },
    { order: { created_at: "ASC" } }
  )

  return res.json({ messages })
}

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const { id } = req.params
  console.info(`${LOG_PREFIX} request received`, {
    method: req.method,
    conversation_id: id,
  })

  const schema = z.object({
    content: z.string(),
  })

  const parsed = schema.safeParse(req.body)
  if (!parsed.success) {
    console.error(`${LOG_PREFIX} invalid payload`, parsed.error.flatten())
    return res.status(400).json({ error: parsed.error })
  }

  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  console.info(`${LOG_PREFIX} payload received`, {
    conversation_id: id,
    sender_type: "admin",
    admin_id: (req as any).auth_context?.actor_id,
    content_length: parsed.data.content.length,
  })
  
  let message
  try {
    message = await chatModuleService.createChatMessages({
      conversation_id: id,
      sender_type: "admin",
      sender_id: (req as any).auth_context?.actor_id,
      content: parsed.data.content,
    })
  } catch (err) {
    console.error(`${LOG_PREFIX} insert failed`, {
      conversation_id: id,
      sender_type: "admin",
      error: err instanceof Error ? err.message : err,
    })
    throw err
  }

  console.info(`${LOG_PREFIX} insert completed`, {
    message_id: message.id,
    conversation_id: id,
    sender_type: message.sender_type,
    content_length: message.content.length,
    created_at: message.created_at,
  })

  await chatModuleService.updateChatConversations({
    id: id,
    status: "IN_PROGRESS",
    admin_started_at: new Date(),
    last_message_at: new Date(),
    admin_metadata: {
      unread_admin_count: 0,
    },
  })
  console.info(`${LOG_PREFIX} conversation timestamp updated`, {
    conversation_id: id,
    message_id: message.id,
  })

  let eventBus: any = null
  try {
    eventBus = req.scope.resolve("event_bus_module")
  } catch (err) {
    console.warn("Event bus module is not available for chat message event")
  }

  if (eventBus) {
    await (eventBus as any).emit({
      name: "chat.message.created",
      data: { conversation_id: id, message_id: message.id }
    })
    console.info(`${LOG_PREFIX} event emitted`, {
      conversation_id: id,
      message_id: message.id,
    })
  }

  try {
    const broadcastRes = await fetch("http://chatbot-service:8080/api/broadcast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: id,
        event: "chat.message.created",
        data: message,
        notify_admin: true,
      })
    })
    const broadcastBody = await broadcastRes.json().catch(() => null)
    console.info(`${LOG_PREFIX} websocket broadcast completed`, {
      conversation_id: id,
      message_id: message.id,
      ok: broadcastRes.ok,
      status: broadcastRes.status,
      response: broadcastBody,
    })
  } catch (err) {
    console.error(`${LOG_PREFIX} websocket broadcast failed`, {
      conversation_id: id,
      message_id: message.id,
      error: err instanceof Error ? err.message : err,
    })
  }

  console.info(`${LOG_PREFIX} response sent`, {
    conversation_id: id,
    message_id: message.id,
  })

  return res.json({ message })
}
