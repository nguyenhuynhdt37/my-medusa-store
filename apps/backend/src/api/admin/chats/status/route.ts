import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { Modules } from "@medusajs/framework/utils"

export const GET = async (req: MedusaRequest, res: MedusaResponse) => {
  const cacheService = req.scope.resolve(Modules.CACHE)
  const isOffline = await cacheService.get("chat_offline_status")
  return res.json({ isOffline: isOffline === "true" })
}

export const POST = async (req: MedusaRequest, res: MedusaResponse) => {
  const cacheService = req.scope.resolve(Modules.CACHE)
  const { isOffline } = req.body as { isOffline: boolean }
  await cacheService.set("chat_offline_status", isOffline ? "true" : "false")
  return res.json({ isOffline })
}
