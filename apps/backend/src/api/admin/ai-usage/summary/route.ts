import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"

const aiServiceUrl = () =>
  (process.env.CHATBOT_SERVICE_URL || "http://chatbot-service:8080")
    .replace(/\/webhook$/, "")
    .replace(/\/$/, "")

export const GET = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(req.query || {})) {
    if (Array.isArray(value)) {
      for (const item of value) {
        query.append(key, String(item))
      }
    } else if (value != null) {
      query.set(key, String(value))
    }
  }

  const response = await fetch(`${aiServiceUrl()}/admin/ai-usage/summary?${query.toString()}`)
  const body = await response.json().catch(() => null)

  if (!response.ok) {
    return res.status(response.status).json({
      error: "AI usage service failed",
      detail: body,
    })
  }

  return res.json(body)
}
