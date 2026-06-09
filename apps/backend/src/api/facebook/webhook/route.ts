import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"

export const AUTHENTICATE = false

const sanitizePsid = (value: string) =>
  value.replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 128)

const backendBaseUrl = (req: MedusaRequest) =>
  (process.env.MEDUSA_INTERNAL_URL || `http://${req.headers.host || "localhost:9000"}`).replace(/\/$/, "")

export const GET = async (req: MedusaRequest, res: MedusaResponse) => {
  const url = new URL(req.url, `http://${req.headers.host}`)
  const mode = url.searchParams.get("hub.mode")
  const token = url.searchParams.get("hub.verify_token")
  const challenge = url.searchParams.get("hub.challenge") || ""

  if (mode === "subscribe" && process.env.FB_VERIFY_TOKEN && token === process.env.FB_VERIFY_TOKEN) {
    return res.status(200).send(challenge)
  }

  return res.status(403).json({ error: "Facebook webhook verification failed" })
}

export const POST = async (req: MedusaRequest, res: MedusaResponse) => {
  const body = req.body as any
  if (body?.object !== "page") {
    return res.status(404).json({ error: "Unsupported webhook object" })
  }

  const handled: any[] = []
  for (const entry of body.entry || []) {
    for (const event of entry.messaging || []) {
      const psid = sanitizePsid(String(event.sender?.id || ""))
      const message = event.message || {}
      const text = String(message.text || "").trim()
      if (!psid || !text || message.is_echo) {
        continue
      }

      console.info("[MESSENGER_INCOMING]", {
        psid,
        message_id: message.mid,
        content_length: text.length,
      })

      const response = await fetch(`${backendBaseUrl(req)}/store/chats/process`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY
            ? { "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY }
            : {}),
        },
        body: JSON.stringify({
          message: text,
          guest_id: `fb_${psid}`,
          channel: "MESSENGER",
          external_user_id: psid,
          external_message_id: message.mid || null,
        }),
      })
      const result = await response.json().catch(() => null)
      if (!response.ok) {
        console.error("[MESSENGER_PROCESS_FAILED]", {
          psid,
          status: response.status,
          result,
        })
        continue
      }

      handled.push({
        psid,
        conversation_id: result?.conversationId,
        status: result?.conversationStatus,
        message_count: result?.messages?.length || 0,
      })
    }
  }

  return res.json({ success: true, handled })
}
