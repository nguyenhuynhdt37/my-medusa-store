const realtimeBaseUrl = () =>
  (process.env.CHAT_REALTIME_URL || "http://localhost:9001").replace(/\/$/, "")

export const broadcastChatEvent = async (
  conversationId: string,
  event: string,
  data: any,
  notifyAdmin = false
) => {
  try {
    const response = await fetch(`${realtimeBaseUrl()}/api/broadcast`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        event,
        data,
        notify_admin: notifyAdmin,
      }),
    })

    return {
      ok: response.ok,
      status: response.status,
      body: await response.json().catch(() => null),
    }
  } catch (err) {
    console.error("[CHAT_REALTIME_BROADCAST_FAILED]", {
      conversation_id: conversationId,
      event,
      error: err instanceof Error ? err.message : err,
    })
    return {
      ok: false,
      status: 0,
      body: null,
    }
  }
}
