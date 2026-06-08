import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { Modules } from "@medusajs/framework/utils"

export const GET = async (req: MedusaRequest, res: MedusaResponse) => {
  const cacheService = req.scope.resolve(Modules.CACHE)
  const isOffline = await cacheService.get("chat_offline_status")
  return res.json({ isOffline: isOffline === "true" })
}
