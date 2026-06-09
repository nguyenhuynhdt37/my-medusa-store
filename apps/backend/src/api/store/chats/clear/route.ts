import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../modules/chat"

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const customerId = (req as any).auth_context?.actor_type === "customer" ? (req as any).auth_context.actor_id : null
  const guestId = (req.body as any)?.guest_id || null

  console.log("[CLEAR_CHAT_REQUEST]", {
    guest_id: guestId || null,
    customer_id: customerId || null,
  })

  if (!customerId && !guestId) {
    return res.status(400).json({ error: "Missing customer_id or guest_id" })
  }

  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  const filters: any = {}
  if (customerId) {
    filters.customer_id = customerId
  } else if (guestId) {
    filters.guest_id = guestId
  }

  // List all conversations for the user
  const conversations = await chatModuleService.listChatConversations(filters, {
    order: { last_message_at: "DESC", updated_at: "DESC" },
  })

  // Close all active conversations
  const activeConversations = conversations.filter((c: any) => c.status !== "CLOSED")
  for (const conv of activeConversations) {
    await chatModuleService.updateChatConversations({
      id: conv.id,
      status: "CLOSED",
      closed_at: new Date(),
    })
    console.log("[CONVERSATION_CLOSED_ON_CLEAR]", { conversation_id: conv.id })
  }

  // Create a new conversation
  const newConversation = await chatModuleService.createChatConversations({
    customer_id: customerId,
    guest_id: customerId ? null : guestId,
  })

  console.log("[CONVERSATION_CREATED_ON_CLEAR]", {
    new_conversation_id: newConversation.id,
    customer_id: newConversation.customer_id,
    guest_id: newConversation.guest_id,
  })

  return res.json({ conversation: newConversation })
}
