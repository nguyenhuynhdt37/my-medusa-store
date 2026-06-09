import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"

export const AUTHENTICATE = false

const LOG_PREFIX = "[chat:admin:presence]"

export const GET = async (req: MedusaRequest, res: MedusaResponse) => {
  const { id } = req.params
  console.info(`${LOG_PREFIX} volatile presence read`, { conversation_id: id })
  return res.json({ presences: [] })
}

export const POST = async (req: MedusaRequest, res: MedusaResponse) => {
  const { id } = req.params
  console.info(`${LOG_PREFIX} request received`, { conversation_id: id })
  return res.status(204).send()
}
