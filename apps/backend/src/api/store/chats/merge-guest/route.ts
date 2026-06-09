import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../../modules/chat"
import { syncGuestChatToCustomer } from "../../../utils/chat-guest-merge"

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
  const merge = await syncGuestChatToCustomer(chatModuleService, {
    guestId,
    customerId,
  })

  console.log("[MERGE_GUEST_COMPLETED]", {
    guest_id: guestId,
    customer_id: customerId,
    conversations_updated: merge.conversation_count,
    messages_updated: merge.message_count,
    presences_updated: merge.presence_count,
  })

  return res.json({
    success: true,
    count: merge.conversation_count,
    merge,
  })
}
