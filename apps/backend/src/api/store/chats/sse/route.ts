import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"

export const GET = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const guestId = req.query.guest_id as string
  const customerId = (req as any).auth_context?.actor_type === "customer" ? (req as any).auth_context.actor_id : null

  if (!customerId && !guestId) {
    return res.status(400).json({ error: "Missing customer_id or guest_id" })
  }

  const eventBus = req.scope.resolve("event_bus_module")
  if (!eventBus) {
    return res.status(500).json({ error: "Event bus not available" })
  }

  // Set headers for SSE
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
  })

  // Send initial connected event
  res.write("data: connected\n\n")

  // Function to handle new messages
  const messageHandler = async (data: any) => {
    // Only send the message if it belongs to this guest or customer
    // We would need to verify conversation ownership. For simplicity, we just send conversation_id
    // But since the frontend listens, let's fetch the message to ensure ownership
    try {
      const chatModuleService = req.scope.resolve("chat")
      const message = await chatModuleService.retrieveChatMessage(data.message_id, {
        relations: ["conversation"]
      })
      
      const conv = message.conversation
      if ((customerId && conv.customer_id === customerId) || (guestId && conv.guest_id === guestId)) {
        res.write(`data: ${JSON.stringify(message)}\n\n`)
      }
    } catch (e) {
      console.error(e)
    }
  }

  // Subscribe to event
  (eventBus as any).subscribe("chat.message.created", messageHandler)

  // Handle client disconnect
  req.on("close", () => {
    (eventBus as any).unsubscribe("chat.message.created", messageHandler)
    res.end()
  })
}
