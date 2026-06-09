import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../../modules/chat"

export const GET = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const url = new URL(req.url, `http://${req.headers.host}`)
  const guestId = url.searchParams.get("guest_id")
  const conversationId = url.searchParams.get("conversation_id")
  const customerId = (req as any).auth_context?.actor_type === "customer"
    ? (req as any).auth_context.actor_id
    : url.searchParams.get("customer_id")

  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  let conversation: any = null
  let conversations: any[] = []

  if (conversationId) {
    try {
      conversation = await chatModuleService.retrieveChatConversation(conversationId)
      conversations = [conversation]
    } catch (err) {
      console.warn("[CHAT_DEBUG_CURRENT_NOT_FOUND]", {
        guest_id: guestId,
        customer_id: customerId,
        conversation_id: conversationId,
        error: err instanceof Error ? err.message : err,
      })
    }
  }

  if (!conversation && guestId) {
    conversations = await chatModuleService.listChatConversations(
      { guest_id: guestId },
      { order: { last_message_at: "DESC", updated_at: "DESC" } }
    )
    conversation = conversations.find((item: any) => item.status !== "CLOSED") || conversations[0] || null
  }

  if (!conversation && customerId) {
    conversations = await chatModuleService.listChatConversations(
      { customer_id: customerId },
      { order: { last_message_at: "DESC", updated_at: "DESC" } }
    )
    conversation = conversations.find((item: any) => item.status !== "CLOSED") || conversations[0] || null
  }

  const merged = Boolean(
    guestId &&
    customerId &&
    conversation &&
    conversation.guest_id === guestId &&
    conversation.customer_id === customerId
  )

  console.info("[CHAT_DEBUG_CURRENT]", {
    guest_id: guestId,
    customer_id: customerId,
    conversation_id: conversation?.id || conversationId || null,
    merged,
    conversation_count: conversations.length,
  })

  return res.json({
    guest_id: guestId,
    customer_id: customerId,
    conversation_id: conversation?.id || conversationId || null,
    merged,
    conversation,
    conversation_count: conversations.length,
  })
}
