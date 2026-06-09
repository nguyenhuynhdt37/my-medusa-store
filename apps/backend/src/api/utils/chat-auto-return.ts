const AUTO_RETURN_AFTER_MS = 5 * 60 * 1000

const WAITING_TIMEOUT_MESSAGE = "Hiện chưa có nhân viên trực tuyến. Trợ lý AI sẽ tiếp tục hỗ trợ bạn."
const IN_PROGRESS_TIMEOUT_MESSAGE = "Nhân viên hiện không phản hồi. Trợ lý AI sẽ tiếp tục hỗ trợ bạn."

const toMs = (value?: string | Date | null) => {
  if (!value) {
    return null
  }

  const ms = new Date(value).getTime()
  return Number.isFinite(ms) ? ms : null
}

const broadcastChatEvent = async (conversationId: string, event: string, data: any) => {
  try {
    await fetch("http://chatbot-service:8080/api/broadcast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        event,
        data,
        notify_admin: false,
      }),
    })
  } catch (err) {
    console.error("[AUTO_RETURN_TO_BOT_BROADCAST_FAILED]", {
      conversation_id: conversationId,
      event,
      error: err instanceof Error ? err.message : err,
    })
  }
}

const shouldReturnWaitingConversation = (conversation: any, nowMs: number) => {
  const startedAt =
    toMs(conversation.escalated_at) ||
    toMs(conversation.last_message_at) ||
    toMs(conversation.updated_at)

  return Boolean(startedAt && nowMs - startedAt >= AUTO_RETURN_AFTER_MS)
}

const shouldReturnInProgressConversation = (conversation: any, nowMs: number) => {
  const metadata = (conversation.admin_metadata || {}) as Record<string, any>
  const lastCustomerMessageAt = toMs(metadata.last_customer_message_at)
  const lastAdminMessageAt = toMs(metadata.last_admin_message_at)
  const adminStartedAt = toMs(conversation.admin_started_at)
  const pendingSince = lastCustomerMessageAt || adminStartedAt

  if (!pendingSince || nowMs - pendingSince < AUTO_RETURN_AFTER_MS) {
    return false
  }

  return !lastAdminMessageAt || lastAdminMessageAt < pendingSince
}

export const runChatAutoReturn = async (chatModuleService: any) => {
  const now = new Date()
  const nowMs = now.getTime()
  const conversations = await chatModuleService.listChatConversations(
    {},
    { order: { updated_at: "DESC" } }
  )

  const candidates = conversations.filter((conversation: any) => {
    const metadata = (conversation.admin_metadata || {}) as Record<string, any>
    if (metadata.auto_returned_at) {
      return false
    }

    if (conversation.status === "WAITING_ADMIN") {
      if (metadata.waiting_timeout_notified) return false
      return shouldReturnWaitingConversation(conversation, nowMs)
    }

    if (conversation.status === "IN_PROGRESS") {
      return shouldReturnInProgressConversation(conversation, nowMs)
    }

    return false
  })

  for (const conversation of candidates) {
    const previousStatus = conversation.status
    const metadata = (conversation.admin_metadata || {}) as Record<string, any>

    if (previousStatus === "WAITING_ADMIN") {
      const updatedConversation = await chatModuleService.updateChatConversations({
        id: conversation.id,
        admin_metadata: {
          ...metadata,
          waiting_timeout_notified: true,
        },
      })

      const message = await chatModuleService.createChatMessages({
        conversation_id: conversation.id,
        sender_type: "bot",
        sender_id: "system",
        content: WAITING_TIMEOUT_MESSAGE,
        metadata: {
          system: true,
          event: "waiting_timeout_notify",
        },
      })

      console.info("WAITING_TIMEOUT_NOTIFY", {
        conversation_id: conversation.id,
      })

      await broadcastChatEvent(conversation.id, "conversation.status.updated", { conversation: updatedConversation })
      await broadcastChatEvent(conversation.id, "chat.message.created", { ...message, conversation_id: conversation.id })
    } else {
      const reason = "admin_response_timeout"
      const updatedConversation = await chatModuleService.updateChatConversations({
        id: conversation.id,
        status: "BOT_HANDLED",
        assigned_admin_id: null,
        escalation_reason: null,
        admin_metadata: {
          ...metadata,
          unread_admin_count: 0,
          auto_returned_at: now.toISOString(),
          auto_return_reason: reason,
        },
      })

      const message = await chatModuleService.createChatMessages({
        conversation_id: conversation.id,
        sender_type: "bot",
        sender_id: "system",
        content: IN_PROGRESS_TIMEOUT_MESSAGE,
        metadata: {
          system: true,
          event: "auto_return_to_bot",
          reason,
        },
      })

      console.info("AUTO_RETURN_TO_BOT", {
        conversation_id: conversation.id,
        previous_status: previousStatus,
        reason,
      })

      await broadcastChatEvent(conversation.id, "conversation.status.updated", { conversation: updatedConversation })
      await broadcastChatEvent(conversation.id, "chat.message.created", { ...message, conversation_id: conversation.id })
    }
  }

  return candidates.length
}
