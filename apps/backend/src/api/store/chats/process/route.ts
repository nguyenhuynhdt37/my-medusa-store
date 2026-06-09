import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { z } from "zod"
import { CHAT_MODULE } from "../../../../modules/chat"
import { CHAT_STATUSES, isAdminVisibleChatStatus } from "../../../../modules/chat/status"
import { broadcastChatEvent } from "../../../utils/chat-realtime"
import { syncGuestChatToCustomer } from "../../../utils/chat-guest-merge"
import { sendMessengerMessage } from "../../../utils/messenger"

const LOG_PREFIX = "[chat:store:process]"

const aiServiceUrl = () =>
  (process.env.CHATBOT_SERVICE_URL || "http://chatbot-service:8080").replace(/\/webhook$/, "").replace(/\/$/, "")

const callAiService = async ({
  conversation,
  message,
  authorization,
}: {
  conversation: any
  message: string
  authorization?: string
}) => {
  const response = await fetch(`${aiServiceUrl()}/ai/process`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(authorization ? { Authorization: authorization } : {}),
    },
    body: JSON.stringify({
      conversation_id: conversation.id,
      message,
      customer_context: {
        customer_id: conversation.customer_id,
        guest_id: conversation.guest_id,
        channel: conversation.channel || "WEB",
        external_user_id: conversation.external_user_id || null,
      },
      session_context: {
        status: conversation.status,
        admin_metadata: conversation.admin_metadata || {},
      },
    }),
  })

  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(`AI service failed with HTTP ${response.status}: ${JSON.stringify(body)}`)
  }
  return body
}

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const schema = z.object({
    message: z.string().min(1),
    conversation_id: z.string().optional().nullable(),
    guest_id: z.string().optional().nullable(),
    channel: z.enum(["WEB", "MESSENGER"]).optional(),
    external_user_id: z.string().optional().nullable(),
    external_message_id: z.string().optional().nullable(),
    metadata: z.any().optional(),
  })

  const parsed = schema.safeParse(req.body)
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error })
  }

  const data = parsed.data
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  const customerId = (req as any).auth_context?.actor_type === "customer" ? (req as any).auth_context.actor_id : null
  const guestId = data.guest_id || null
  const channel = data.channel || "WEB"
  const externalUserId = data.external_user_id || null
  const authorization = req.headers.authorization

  console.info(`${LOG_PREFIX} request received`, {
    conversation_id: data.conversation_id || null,
    guest_id: guestId,
    customer_id: customerId,
    channel,
    external_user_id: externalUserId,
    content_length: data.message.length,
  })

  if (!customerId && !guestId) {
    return res.status(400).json({ error: "Missing customer_id or guest_id" })
  }

  if (customerId && guestId) {
    await syncGuestChatToCustomer(chatModuleService, { guestId, customerId })
  }

  let conversation: any = null
  if (data.conversation_id) {
    const existing = await chatModuleService.retrieveChatConversation(data.conversation_id)
    const ownsConversation =
      (customerId && existing.customer_id === customerId) ||
      (guestId && existing.guest_id === guestId) ||
      (externalUserId && existing.external_user_id === externalUserId)

    if (!ownsConversation) {
      return res.status(403).json({ error: "Conversation does not belong to this user" })
    }
    if (existing.status === "CLOSED") {
      return res.status(400).json({ error: "Conversation is closed" })
    }
    conversation = existing
  }

  if (!conversation) {
    const filters: any = externalUserId
      ? { channel, external_user_id: externalUserId }
      : guestId
        ? { guest_id: guestId }
        : { customer_id: customerId }
    const conversations = await chatModuleService.listChatConversations(filters, {
      order: { last_message_at: "DESC", updated_at: "DESC" },
    })
    conversation = conversations.find((item: any) => item.status !== "CLOSED") || null
  }

  if (!conversation) {
    conversation = await chatModuleService.createChatConversations({
      customer_id: customerId,
      guest_id: guestId,
      channel,
      external_user_id: externalUserId,
    })
  } else if (conversation.channel !== channel || (externalUserId && conversation.external_user_id !== externalUserId)) {
    conversation = await chatModuleService.updateChatConversations({
      id: conversation.id,
      channel,
      external_user_id: externalUserId || conversation.external_user_id || null,
    })
  }

  const now = new Date()
  const userMessage = await chatModuleService.createChatMessages({
    conversation_id: conversation.id,
    sender_type: customerId ? "customer" : "guest",
    sender_id: customerId || guestId,
    customer_id: customerId,
    guest_id: guestId,
    channel,
    external_message_id: data.external_message_id || null,
    content: data.message,
    metadata: data.metadata || null,
  })

  conversation = await chatModuleService.updateChatConversations({
    id: conversation.id,
    customer_id: customerId || conversation.customer_id,
    guest_id: guestId || conversation.guest_id,
    channel,
    external_user_id: externalUserId || conversation.external_user_id || null,
    last_message_at: now,
    admin_metadata: {
      ...((conversation.admin_metadata || {}) as Record<string, any>),
      last_customer_message_at: now.toISOString(),
    },
  })

  console.info("[CHAT_SAVE]", {
    guest_id: guestId,
    customer_id: customerId,
    conversation_id: conversation.id,
    message_id: userMessage.id,
    sender_type: userMessage.sender_type,
  })

  if (["IN_PROGRESS", "RESOLVED", "CLOSED"].includes(conversation.status)) {
    const notifyAdmin = isAdminVisibleChatStatus(conversation.status)
    await broadcastChatEvent(conversation.id, "chat.message.created", { ...userMessage, conversation_id: conversation.id }, notifyAdmin)
    return res.json({
      guestId,
      conversationId: conversation.id,
      conversationStatus: conversation.status,
      userMessage,
      messages: [],
      intent: "HumanHandover",
    })
  }

  let aiResult: any
  try {
    aiResult = await callAiService({
      conversation,
      message: data.message,
      authorization,
    })
  } catch (err) {
    console.error(`${LOG_PREFIX} ai service failed`, {
      conversation_id: conversation.id,
      error: err instanceof Error ? err.message : err,
    })
    aiResult = {
      reply: "Xin lỗi, hệ thống AI đang gặp sự cố tạm thời. Bạn thử lại sau giúp mình nhé.",
      messages: [{ text: "Xin lỗi, hệ thống AI đang gặp sự cố tạm thời. Bạn thử lại sau giúp mình nhé." }],
      intent: "AIServiceError",
      confidence: null,
      escalation: { escalate: true, reason: "ai_service_error", confidence: null },
      metadata: { ai: { intent: "AIServiceError" } },
    }
  }

  const escalation = aiResult.escalation || { escalate: false, reason: "ai_handled" }
  const nextStatus = escalation.escalate ? "WAITING_ADMIN" : "BOT_HANDLED"
  const previousStatus = conversation.status
  const previousMetadata = (conversation.admin_metadata || {}) as Record<string, any>
  const unreadAdminCount =
    nextStatus === "WAITING_ADMIN" && !isAdminVisibleChatStatus(previousStatus)
      ? 1
      : isAdminVisibleChatStatus(nextStatus)
        ? Number(previousMetadata.unread_admin_count || 0) + 1
        : previousMetadata.unread_admin_count || 0

  conversation = await chatModuleService.updateChatConversations({
    id: conversation.id,
    status: nextStatus,
    escalation_reason: escalation.escalate ? escalation.reason : null,
    escalated_at: nextStatus === "WAITING_ADMIN" && !conversation.escalated_at ? new Date() : conversation.escalated_at,
    last_message_at: now,
    admin_metadata: {
      ...previousMetadata,
      unread_admin_count: unreadAdminCount,
      failed_response_count: aiResult.metadata?.ai?.failed_response_count ?? previousMetadata.failed_response_count ?? 0,
      ai_confidence: aiResult.confidence ?? previousMetadata.ai_confidence ?? null,
      last_customer_message_at: now.toISOString(),
    },
  })

  const notifyAdmin = isAdminVisibleChatStatus(conversation.status)
  await broadcastChatEvent(conversation.id, "conversation.status.updated", { conversation }, notifyAdmin)
  await broadcastChatEvent(conversation.id, "chat.message.created", { ...userMessage, conversation_id: conversation.id }, notifyAdmin)

  const savedBotMessages: Array<{
    id: string
    text: string
    created_at: Date
    payload?: unknown
  }> = []
  for (const aiMessage of aiResult.messages || []) {
    const text = (aiMessage.text || "").trim()
    if (!text) continue

    const botMessage = await chatModuleService.createChatMessages({
      conversation_id: conversation.id,
      sender_type: "bot",
      sender_id: "ai",
      customer_id: customerId,
      guest_id: guestId,
      channel,
      content: text,
      metadata: {
        ...(aiResult.metadata || {}),
        ...(aiMessage.payload ? { payload: aiMessage.payload } : {}),
      },
    })
    savedBotMessages.push({
      id: botMessage.id,
      text: botMessage.content,
      created_at: botMessage.created_at,
      payload: botMessage.metadata?.payload,
    })
    await broadcastChatEvent(conversation.id, "chat.message.created", { ...botMessage, conversation_id: conversation.id }, notifyAdmin)

    if (channel === "MESSENGER" && externalUserId) {
      await sendMessengerMessage(externalUserId, botMessage.content, aiMessage.payload)
    }
  }

  console.info(escalation.escalate ? "[ESCALATED_TO_ADMIN]" : "[AI_HANDLED]", {
    conversation_id: conversation.id,
    reason: escalation.reason,
    status: conversation.status,
  })

  return res.json({
    guestId,
    conversationId: conversation.id,
    conversationStatus: conversation.status,
    userMessage,
    escalation,
    intent: aiResult.intent,
    confidence: aiResult.confidence,
    messages: savedBotMessages,
  })
}
