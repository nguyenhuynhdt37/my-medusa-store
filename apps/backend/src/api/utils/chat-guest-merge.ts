type ChatModuleService = {
  listChatConversations: (...args: any[]) => Promise<any[]>
  updateChatConversations: (...args: any[]) => Promise<any>
  listChatMessages: (...args: any[]) => Promise<any[]>
  updateChatMessages: (...args: any[]) => Promise<any>
  listChatPresences: (...args: any[]) => Promise<any[]>
  updateChatPresences: (...args: any[]) => Promise<any>
}

export type GuestCustomerMergeResult = {
  guest_id: string | null
  customer_id: string | null
  conversation_count: number
  message_count: number
  presence_count: number
  session_count: number
  handover_count: number
  merged: boolean
  conversation_ids: string[]
  skipped: string[]
}

export const syncGuestChatToCustomer = async (
  chatModuleService: ChatModuleService,
  {
    guestId,
    customerId,
  }: {
    guestId?: string | null
    customerId?: string | null
  }
): Promise<GuestCustomerMergeResult> => {
  const result: GuestCustomerMergeResult = {
    guest_id: guestId || null,
    customer_id: customerId || null,
    conversation_count: 0,
    message_count: 0,
    presence_count: 0,
    session_count: 0,
    handover_count: 0,
    merged: false,
    conversation_ids: [],
    skipped: [],
  }

  if (!guestId || !customerId) {
    result.skipped.push("missing_identity")
    return result
  }

  const conversations = await chatModuleService.listChatConversations(
    { guest_id: guestId },
    { order: { last_message_at: "DESC", updated_at: "DESC" } }
  )

  result.conversation_ids = conversations.map((conversation: any) => conversation.id)

  for (const conversation of conversations) {
    if (conversation.customer_id !== customerId) {
      await chatModuleService.updateChatConversations({
        id: conversation.id,
        customer_id: customerId,
        guest_id: guestId,
      })
      result.conversation_count += 1
    }
  }

  for (const conversationId of result.conversation_ids) {
    const messages = await chatModuleService.listChatMessages({
      conversation_id: conversationId,
    })

    for (const message of messages) {
      if (message.customer_id !== customerId || message.guest_id !== guestId) {
        await chatModuleService.updateChatMessages({
          id: message.id,
          customer_id: customerId,
          guest_id: guestId,
        })
        result.message_count += 1
      }
    }
  }

  const presences = await chatModuleService.listChatPresences({
    guest_id: guestId,
  })

  for (const presence of presences) {
    if (presence.user_id !== customerId || presence.guest_id !== guestId) {
      await chatModuleService.updateChatPresences({
        id: presence.id,
        user_id: customerId,
        guest_id: guestId,
      })
      result.presence_count += 1
    }
  }

  result.skipped.push("chat_session_missing_model")
  result.skipped.push("handover_missing_model")
  result.merged =
    result.conversation_count > 0 ||
    result.message_count > 0 ||
    result.presence_count > 0

  console.info("[GUEST_TO_CUSTOMER_MERGE]", {
    guest_id: guestId,
    customer_id: customerId,
    conversation_count: result.conversation_count,
    message_count: result.message_count,
    presence_count: result.presence_count,
    session_count: result.session_count,
    handover_count: result.handover_count,
    merged: result.merged,
    conversation_ids: result.conversation_ids,
    skipped: result.skipped,
  })

  return result
}
