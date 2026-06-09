const graphVersion = () => process.env.FB_GRAPH_VERSION || "v20.0"

export const sendMessengerMessage = async (psid: string, text: string) => {
  const token = process.env.FB_PAGE_ACCESS_TOKEN
  if (!token) {
    console.info("[MESSENGER_OUTGOING_SKIPPED]", {
      reason: "missing_FB_PAGE_ACCESS_TOKEN",
      psid,
    })
    return { ok: false, skipped: true, reason: "missing_FB_PAGE_ACCESS_TOKEN" }
  }

  const response = await fetch(`https://graph.facebook.com/${graphVersion()}/me/messages?access_token=${encodeURIComponent(token)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      recipient: { id: psid },
      message: { text },
    }),
  })

  const body = await response.json().catch(() => null)
  console.info("[MESSENGER_OUTGOING]", {
    psid,
    status: response.status,
    ok: response.ok,
  })
  return { ok: response.ok, status: response.status, response: body }
}
