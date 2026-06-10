import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"

const aiServiceUrl = () =>
  (process.env.CHATBOT_SERVICE_URL || "http://chatbot-service:8080")
    .replace(/\/webhook$/, "")
    .replace(/\/$/, "")

export const POST = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const query = new URLSearchParams()
  if (req.query?.date) {
    query.set("date", String(req.query.date))
  }

  const response = await fetch(`${aiServiceUrl()}/admin/ai-usage/daily-snapshots/refresh?${query.toString()}`, {
    method: "POST",
  })
  const body = await response.json().catch(() => null)

  if (!response.ok) {
    return res.status(response.status).json({
      error: "AI usage snapshot refresh failed",
      detail: body,
    })
  }

  return res.json(body)
}
