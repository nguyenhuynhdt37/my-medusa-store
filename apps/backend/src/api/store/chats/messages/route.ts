import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { z } from "zod"
import { CHAT_MODULE } from "../../../../modules/chat"
import { CHAT_STATUSES, isAdminVisibleChatStatus } from "../../../../modules/chat/status"
import { runChatAutoReturn } from "../../../utils/chat-auto-return"
import { syncGuestChatToCustomer } from "../../../utils/chat-guest-merge"
import { broadcastChatEvent } from "../../../utils/chat-realtime"

const LOG_PREFIX = "[chat:store:messages]"

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  console.info(`${LOG_PREFIX} request received`, {
    method: req.method,
    path: req.path,
  })

  const schema = z.object({
    conversation_id: z.string().optional().nullable(),
    guest_id: z.string().optional().nullable(),
    sender_type: z.enum(["customer", "guest", "bot", "admin"]),
    content: z.string(),
    metadata: z.any().optional(),
    conversation_status: z.enum(CHAT_STATUSES).optional(),
    escalation_reason: z.string().optional().nullable(),
    ai_confidence: z.number().optional().nullable(),
    failed_response_count: z.number().int().optional().nullable(),
    channel: z.enum(["WEB", "MESSENGER"]).optional(),
    external_user_id: z.string().optional().nullable(),
    external_message_id: z.string().optional().nullable(),
  })

  const parsed = schema.safeParse(req.body)
  if (!parsed.success) {
    console.error(`${LOG_PREFIX} invalid payload`, parsed.error.flatten())
    return res.status(400).json({ error: parsed.error })
  }

  const data = parsed.data
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  await runChatAutoReturn(chatModuleService)

  const customerId = (req as any).auth_context?.actor_type === "customer" ? (req as any).auth_context.actor_id : null
  const guestId = data.guest_id || null
  const conversationId = data.conversation_id || null
  const channel = data.channel || "WEB"
  const externalUserId = data.external_user_id || null
  let mergeResult = null as Awaited<ReturnType<typeof syncGuestChatToCustomer>> | null

  console.info(`${LOG_PREFIX} payload received`, {
    conversation_id: conversationId,
    guest_id: guestId,
    sender_type: data.sender_type,
    customer_id: customerId,
    content_length: data.content.length,
    conversation_status: data.conversation_status,
    escalation_reason: data.escalation_reason,
    channel,
    external_user_id: externalUserId,
  })

  if (!customerId && !guestId) {
    console.error(`${LOG_PREFIX} missing identity`, {
      conversation_id: conversationId,
      guest_id: guestId,
      customer_id: customerId,
    })
    return res.status(400).json({ error: "Missing customer_id or guest_id" })
  }

  if (customerId && guestId) {
    mergeResult = await syncGuestChatToCustomer(chatModuleService, {
      guestId,
      customerId,
    })
  }

  let conversation: any = null

  if (conversationId) {
    try {
      const existingConversation = await chatModuleService.retrieveChatConversation(conversationId)
      const ownsConversation =
        (customerId && existingConversation.customer_id === customerId) ||
        (guestId && existingConversation.guest_id === guestId)

      if (!ownsConversation) {
        console.error(`${LOG_PREFIX} conversation ownership rejected`, {
          conversation_id: conversationId,
          guest_id: guestId,
          customer_id: customerId,
        })
        return res.status(403).json({ error: "Conversation does not belong to this user" })
      }

      if (existingConversation.status === "CLOSED") {
        console.error(`${LOG_PREFIX} conversation is closed`, {
          conversation_id: conversationId,
        })
        return res.status(400).json({ error: "Conversation is closed" })
      }

      conversation = customerId && guestId && existingConversation.guest_id === guestId
        ? await chatModuleService.retrieveChatConversation(existingConversation.id)
        : existingConversation
      if (conversation.channel !== channel || (externalUserId && conversation.external_user_id !== externalUserId)) {
        conversation = await chatModuleService.updateChatConversations({
          id: conversation.id,
          channel,
          external_user_id: externalUserId || conversation.external_user_id || null,
        })
      }
      console.info(`${LOG_PREFIX} existing conversation accepted`, {
        conversation_id: conversation.id,
      })
    } catch (err) {
      console.error(`${LOG_PREFIX} conversation not found`, {
        conversation_id: conversationId,
        error: err instanceof Error ? err.message : err,
      })
      return res.status(404).json({ error: "Conversation not found" })
    }
  }

  // Find the current active conversation. When both ids are present, prefer the
  // guest conversation that was just merged so refresh/login never forks history.
  if (!conversation) {
    const primaryFilters: any = externalUserId
      ? { channel, external_user_id: externalUserId }
      : guestId
        ? { guest_id: guestId }
        : { customer_id: customerId }
    let conversations = await chatModuleService.listChatConversations(primaryFilters, {
      order: { last_message_at: "DESC", updated_at: "DESC" },
    })
    conversation = conversations.find((c: any) => c.status !== "CLOSED")

    if (!conversation && customerId && guestId) {
      const fallbackFilters = { customer_id: customerId }
      conversations = await chatModuleService.listChatConversations(fallbackFilters, {
        order: { last_message_at: "DESC", updated_at: "DESC" },
      })
      conversation = conversations.find((c: any) => c.status !== "CLOSED")
    }

    console.info(`${LOG_PREFIX} conversation lookup completed`, {
      filters: primaryFilters,
      found: conversations.length,
      selected_conversation_id: conversation?.id,
      merge_result: mergeResult,
    })
  }

  if (!conversation) {
    conversation = await chatModuleService.createChatConversations({
      customer_id: customerId,
      guest_id: guestId, // Always keep guest_id linked if available
      channel,
      external_user_id: externalUserId,
    })
    console.info(`${LOG_PREFIX} conversation created`, {
      conversation_id: conversation.id,
      customer_id: conversation.customer_id,
      guest_id: conversation.guest_id,
    })
  }

  let message
  try {
    message = await chatModuleService.createChatMessages({
      conversation_id: conversation.id,
      sender_type: data.sender_type,
      sender_id: customerId || guestId,
      customer_id: customerId,
      guest_id: guestId,
      channel,
      external_message_id: data.external_message_id || null,
      content: data.content,
      metadata: data.metadata || null,
    })
  } catch (err) {
    console.error(`${LOG_PREFIX} insert failed`, {
      conversation_id: conversation.id,
      sender_type: data.sender_type,
      error: err instanceof Error ? err.message : err,
    })
    throw err
  }

  console.info(`${LOG_PREFIX} insert completed`, {
    message_id: message.id,
    conversation_id: conversation.id,
    sender_type: message.sender_type,
    content_length: message.content.length,
    created_at: message.created_at,
  })
  console.info("[CHAT_SAVE]", {
    guest_id: guestId,
    customer_id: customerId,
    conversation_id: conversation.id,
    message_id: message.id,
    sender_type: message.sender_type,
  })

  // Update last_message_at
  const previousStatus = conversation.status
  const nextStatus = data.conversation_status || conversation.status || "BOT_HANDLED"
  const previousMetadata = (conversation.admin_metadata || {}) as Record<string, any>
  const now = new Date()
  const unreadAdminCount =
    nextStatus === "WAITING_ADMIN" && !isAdminVisibleChatStatus(previousStatus)
      ? 1
      : isAdminVisibleChatStatus(nextStatus) && ["customer", "guest"].includes(data.sender_type)
        ? Number(previousMetadata.unread_admin_count || 0) + 1
        : previousMetadata.unread_admin_count || 0
  const adminMetadata = {
    ...previousMetadata,
    unread_admin_count: unreadAdminCount,
    failed_response_count: data.failed_response_count ?? previousMetadata.failed_response_count ?? 0,
    ai_confidence: data.ai_confidence ?? previousMetadata.ai_confidence ?? null,
    ...(["customer", "guest"].includes(data.sender_type) ? { last_customer_message_at: now.toISOString() } : {}),
    ...(nextStatus === "WAITING_ADMIN"
      ? {
        auto_returned_at: null,
        auto_return_reason: null,
        support_request_cancelled_at: null,
      }
      : {}),
  }

  const conversationUpdate: Record<string, any> = {
    id: conversation.id,
    customer_id: customerId || conversation.customer_id,
    guest_id: guestId || conversation.guest_id,
    channel,
    external_user_id: externalUserId || conversation.external_user_id || null,
    status: nextStatus,
    last_message_at: now,
    admin_metadata: adminMetadata,
  }

  if (data.escalation_reason) {
    conversationUpdate.escalation_reason = data.escalation_reason
  }

  if (nextStatus === "WAITING_ADMIN" && !conversation.escalated_at) {
    conversationUpdate.escalated_at = new Date()
  }

  conversation = await chatModuleService.updateChatConversations(conversationUpdate)
  console.info(`${LOG_PREFIX} conversation timestamp updated`, {
    conversation_id: conversation.id,
    message_id: message.id,
    previous_status: previousStatus,
    next_status: nextStatus,
    unread_admin_count: adminMetadata.unread_admin_count,
  })

  const notifyAdmin = isAdminVisibleChatStatus(conversation.status)

  if (notifyAdmin) {
    console.info("[ESCALATED_TO_ADMIN]", {
      conversation_id: conversation.id,
      message_id: message.id,
      reason: conversation.escalation_reason,
      status: conversation.status,
    })
  } else {
    console.info("[AI_HANDLED]", {
      conversation_id: conversation.id,
      message_id: message.id,
      status: conversation.status,
    })
  }

  // Emit SSE event for Admin only after a conversation is visible to Admin.
  let eventBus: any = null
  try {
    eventBus = req.scope.resolve("event_bus_module")
  } catch (err) {
    console.warn("Event bus module is not available for chat message event")
  }

  if (eventBus && notifyAdmin) {
    await (eventBus as any).emit({
      name: "chat.message.created",
      data: { conversation_id: conversation.id, message_id: message.id }
    })
    console.info(`${LOG_PREFIX} event emitted`, {
      conversation_id: conversation.id,
      message_id: message.id,
    })
  }

  const broadcastResult = await broadcastChatEvent(
    conversation.id,
    "chat.message.created",
    { ...message, conversation_id: conversation.id },
    notifyAdmin
  )
  console.info(`${LOG_PREFIX} websocket broadcast completed`, {
    conversation_id: conversation.id,
    message_id: message.id,
    ok: broadcastResult.ok,
    status: broadcastResult.status,
    notify_admin: notifyAdmin,
    response: broadcastResult.body,
  })

  console.info(`${LOG_PREFIX} response sent`, {
    conversation_id: conversation.id,
    message_id: message.id,
  })

  return res.json({ conversation, message, merge: mergeResult })
}
