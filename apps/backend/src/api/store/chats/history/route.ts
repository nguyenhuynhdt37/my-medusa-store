import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../modules/chat"


export const GET = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const guestId = req.query.guest_id as string
  const conversationId = req.query.conversation_id as string
  const customerId = (req as any).auth_context?.actor_type === "customer" ? (req as any).auth_context.actor_id : null

  console.log("[HISTORY_REQUEST]", {
    guest_id: guestId || null,
    conversation_id: conversationId || null,
    customer_id: customerId || null,
  })

  if (!customerId && !guestId && !conversationId) {
    return res.status(400).json({ error: "Missing customer_id, guest_id, or conversation_id" })
  }

  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  let conversation: any = null

  if (conversationId) {
    try {
      const candidate = await chatModuleService.retrieveChatConversation(conversationId)
      const ownsConversation =
        (customerId && candidate.customer_id === customerId) ||
        (guestId && candidate.guest_id === guestId)

      if (ownsConversation && candidate.status !== "CLOSED") {
        conversation = candidate
      } else {
        console.log("[CONVERSATION_FOUND]", {
          conversation: null,
          rejected_conversation_id: conversationId,
          reason: ownsConversation ? "conversation_closed" : "ownership_mismatch",
          candidate_customer_id: candidate.customer_id,
          candidate_guest_id: candidate.guest_id,
          status: candidate.status,
        })
      }
    } catch (err) {
      console.log("[CONVERSATION_FOUND]", {
        conversation: null,
        rejected_conversation_id: conversationId,
        reason: "not_found",
      })
    }
  }

  if (!conversation) {
    const filters: any = {}
    if (customerId) {
      filters.customer_id = customerId
    } else if (guestId) {
      filters.guest_id = guestId
    }

    const conversations = await chatModuleService.listChatConversations(filters, {
      order: { last_message_at: "DESC", updated_at: "DESC" },
    })
    conversation = conversations.find((c: any) => c.status !== "CLOSED")

    console.log("[CONVERSATION_FOUND]", {
      conversation: conversation ? {
        id: conversation.id,
        customer_id: conversation.customer_id,
        guest_id: conversation.guest_id,
        status: conversation.status,
      } : null,
      count: conversations.length,
      filters,
    })
  } else {
    console.log("[CONVERSATION_FOUND]", {
      conversation: {
        id: conversation.id,
        customer_id: conversation.customer_id,
        guest_id: conversation.guest_id,
        status: conversation.status,
      },
      count: 1,
      source: "conversation_id",
    })
  }

  if (!conversation) {
    console.log("[MESSAGES_FOUND]", {
      count: 0,
      conversation_id: null,
    })
    return res.json({ conversation: null, messages: [] })
  }

  const messages = await chatModuleService.listChatMessages(
    { conversation_id: conversation.id },
    { order: { created_at: "ASC" } }
  )

  console.log("[MESSAGES_FOUND]", {
    count: messages.length,
    conversation_id: conversation.id,
  })

  return res.json({ conversation, messages })
}
