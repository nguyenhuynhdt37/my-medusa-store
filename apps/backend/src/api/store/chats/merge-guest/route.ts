import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../modules/chat"

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const guestId = (req.body as any)?.guest_id
  const customerId = (req as any).auth_context?.actor_type === "customer" 
    ? (req as any).auth_context.actor_id 
    : (req.body as any)?.customer_id

  console.log("[MERGE_GUEST_REQUEST]", {
    guest_id: guestId || null,
    customer_id: customerId || null,
  })

  if (!guestId || !customerId) {
    return res.status(400).json({ error: "Missing guest_id or customer_id" })
  }

  const chatModuleService = req.scope.resolve(CHAT_MODULE)

  // Find all conversations belonging to this guest
  const conversations = await chatModuleService.listChatConversations(
    { guest_id: guestId },
    { order: { last_message_at: "DESC", updated_at: "DESC" } }
  )

  const updatedConversations: any[] = []
  for (const conv of conversations) {
    // Only update if not already belonging to this customer
    if (conv.customer_id !== customerId) {
      const updated = await chatModuleService.updateChatConversations({
        id: conv.id,
        customer_id: customerId,
        // Ensure we preserve guest_id as per requirement:
        // Trước login: guest_id: "guest_123", customer_id: null
        // Sau login: guest_id: "guest_123", customer_id: "cus_456"
      })
      updatedConversations.push(updated)
    }
  }

  console.log("[MERGE_GUEST_COMPLETED]", {
    guest_id: guestId,
    customer_id: customerId,
    count_updated: updatedConversations.length,
  })

  return res.json({
    success: true,
    count: updatedConversations.length,
  })
}
