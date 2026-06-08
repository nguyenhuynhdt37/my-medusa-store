import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"

export const GET = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const eventBus = req.scope.resolve("event_bus_module")
  if (!eventBus) {
    return res.status(500).json({ error: "Event bus not available" })
  }

  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
  })

  res.write("data: connected\n\n")

  const messageHandler = async (data: any) => {
    try {
      const chatModuleService = req.scope.resolve("chat")
      const message = await chatModuleService.retrieveChatMessage(data.message_id, {
        relations: ["conversation"]
      })
      res.write(`data: ${JSON.stringify(message)}\n\n`)
    } catch (e) {
      console.error(e)
    }
  }

  (eventBus as any).subscribe("chat.message.created", messageHandler)

  req.on("close", () => {
    (eventBus as any).unsubscribe("chat.message.created", messageHandler)
    res.end()
  })
}
