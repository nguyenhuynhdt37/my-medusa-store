import http from "http"
import { WebSocket, WebSocketServer } from "ws"

type PresenceEntry = {
  client_key: string
  user_id?: string | null
  guest_id?: string | null
  user_type: string
  name?: string | null
  online: boolean
  last_seen_at: string
}

type BroadcastPayload = {
  conversation_id: string
  event: string
  data: any
  notify_admin?: boolean
}

const PORT = Number(process.env.CHAT_REALTIME_PORT || 9001)
const MEDUSA_BASE_URL = (process.env.MEDUSA_INTERNAL_URL || "http://localhost:9000").replace(/\/$/, "")
const PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || ""

const activeConnections = new Map<string, Set<WebSocket>>()
const adminConnections = new Set<WebSocket>()
const socketRooms = new Map<WebSocket, string>()
const socketKeys = new Map<WebSocket, string>()
const presence = new Map<string, Map<string, PresenceEntry>>()
const typing = new Map<string, Map<string, any>>()

const nowIso = () => new Date().toISOString()

const sendJson = (socket: WebSocket, payload: any) => {
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload))
    return true
  }
  return false
}

const broadcast = (conversationId: string, message: any, notifyAdmin = false) => {
  let delivered = 0
  for (const socket of activeConnections.get(conversationId) || []) {
    if (sendJson(socket, message)) delivered += 1
  }
  if (notifyAdmin) {
    for (const socket of adminConnections) {
      if (sendJson(socket, message)) delivered += 1
    }
  }
  return delivered
}

const persistPresence = async (conversationId: string, body: Record<string, any>) => {
  if (conversationId === "admin") return
  try {
    await fetch(`${MEDUSA_BASE_URL}/admin/chats/${conversationId}/presence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  } catch (err) {
    console.warn("[MEDUSA_REALTIME_PRESENCE_PERSIST_FAILED]", {
      conversation_id: conversationId,
      error: err instanceof Error ? err.message : err,
    })
  }
}

const shouldNotifyAdmin = async (conversationId: string) => {
  if (!conversationId.startsWith("01")) return false
  try {
    const url = new URL(`${MEDUSA_BASE_URL}/store/chats/debug/current`)
    url.searchParams.set("conversation_id", conversationId)
    const response = await fetch(url, {
      headers: PUBLISHABLE_KEY ? { "x-publishable-api-key": PUBLISHABLE_KEY } : {},
    })
    if (!response.ok) return false
    const data = await response.json()
    const status = data?.conversation?.status
    const notify = status === "WAITING_ADMIN" || status === "IN_PROGRESS"
    console.info("[TYPING_NOTIFY_ADMIN_CHECK]", { conversation_id: conversationId, status, notify_admin: notify })
    return notify
  } catch (err) {
    console.warn("[TYPING_NOTIFY_ADMIN_CHECK_ERROR]", {
      conversation_id: conversationId,
      error: err instanceof Error ? err.message : err,
    })
    return false
  }
}

const getPresenceList = (conversationId: string) => [
  ...Array.from(presence.get(conversationId)?.values() || []),
  ...Array.from(presence.get("admin")?.values() || []),
]

const broadcastPresenceUpdate = async (conversationId: string) => {
  const notifyAdmin = await shouldNotifyAdmin(conversationId)
  broadcast(
    conversationId,
    {
      event: "presence.updated",
      conversation_id: conversationId,
      data: getPresenceList(conversationId),
    },
    notifyAdmin
  )
}

const broadcastAdminPresenceToConversations = async () => {
  for (const conversationId of activeConnections.keys()) {
    await broadcastPresenceUpdate(conversationId)
  }
}

const setPresence = async (conversationId: string, clientKey: string, body: any) => {
  const entry: PresenceEntry = {
    client_key: clientKey,
    user_id: body.user_id || null,
    guest_id: body.guest_id || null,
    user_type: body.user_type || "guest",
    name: body.name || null,
    online: true,
    last_seen_at: nowIso(),
  }
  if (!presence.has(conversationId)) {
    presence.set(conversationId, new Map())
  }
  presence.get(conversationId)!.set(clientKey, entry)

  console.info("[PRESENCE_UPDATED]", {
    conversation_id: conversationId,
    client_key: clientKey,
    user_type: entry.user_type,
    online: entry.online,
  })

  await persistPresence(conversationId, entry)
  await broadcastPresenceUpdate(conversationId)
  if (conversationId === "admin") {
    console.info("[ADMIN_CONNECTED]", { client_key: clientKey, user_id: entry.user_id || null })
    await broadcastAdminPresenceToConversations()
  }
}

const heartbeatPresence = async (conversationId: string, clientKey: string) => {
  const entry = presence.get(conversationId)?.get(clientKey)
  if (!entry) return
  entry.online = true
  entry.last_seen_at = nowIso()
  if (entry.user_type === "admin") {
    console.info("[ADMIN_HEARTBEAT]", { client_key: clientKey })
  }
  await persistPresence(conversationId, {
    client_key: clientKey,
    online: true,
    last_seen_at: entry.last_seen_at,
  })
  await broadcastPresenceUpdate(conversationId)
  if (conversationId === "admin") {
    await broadcastAdminPresenceToConversations()
  }
}

const removePresence = async (conversationId: string, clientKey: string) => {
  const entry = presence.get(conversationId)?.get(clientKey)
  if (!entry) return
  entry.online = false
  entry.last_seen_at = nowIso()
  if (entry.user_type === "admin") {
    console.info("[ADMIN_DISCONNECTED]", { client_key: clientKey })
  }
  console.info("[PRESENCE_UPDATED]", {
    conversation_id: conversationId,
    client_key: clientKey,
    user_type: entry.user_type,
    online: false,
  })
  await persistPresence(conversationId, {
    client_key: clientKey,
    online: false,
    last_seen_at: entry.last_seen_at,
  })
  await broadcastPresenceUpdate(conversationId)
  if (conversationId === "admin") {
    await broadcastAdminPresenceToConversations()
  }
}

const setTyping = async (conversationId: string, clientKey: string, body: any, roomId: string) => {
  const senderType = body.sender_type || body.user_type || (roomId === "admin" ? "admin" : "customer")
  if (!typing.has(conversationId)) {
    typing.set(conversationId, new Map())
  }
  const payload = {
    sender_type: senderType,
    user_type: body.user_type || senderType,
    name: body.name || null,
    client_key: clientKey,
    updated_at: nowIso(),
  }
  typing.get(conversationId)!.set(clientKey, payload)
  const notifyAdmin = await shouldNotifyAdmin(conversationId)
  const delivered = broadcast(
    conversationId,
    { event: "typing.start", conversation_id: conversationId, data: payload },
    notifyAdmin
  )
  console.info("[TYPING_START]", { conversation_id: conversationId, client_key: clientKey, sender_type: senderType, delivered_to: delivered })
}

const clearTyping = async (conversationId: string, clientKey: string, body: any = {}, roomId = conversationId) => {
  const existing = typing.get(conversationId)?.get(clientKey) || {}
  typing.get(conversationId)?.delete(clientKey)
  const senderType = body.sender_type || existing.sender_type || body.user_type || existing.user_type || (roomId === "admin" ? "admin" : "customer")
  const payload = {
    ...existing,
    ...body,
    sender_type: senderType,
    user_type: body.user_type || existing.user_type || senderType,
    client_key: clientKey,
    updated_at: nowIso(),
  }
  const notifyAdmin = await shouldNotifyAdmin(conversationId)
  const delivered = broadcast(
    conversationId,
    { event: "typing.stop", conversation_id: conversationId, data: payload },
    notifyAdmin
  )
  console.info("[TYPING_STOP]", { conversation_id: conversationId, client_key: clientKey, sender_type: senderType, delivered_to: delivered })
}

const handleSocketMessage = async (socket: WebSocket, roomId: string, raw: string) => {
  if (raw === "ping") {
    socket.send("pong")
    return
  }

  let payload: any
  try {
    payload = JSON.parse(raw)
  } catch {
    return
  }

  const event = payload.event
  const data = payload.data || {}
  const clientKey = socketKeys.get(socket)!

  if (event === "presence.subscribe") {
    await setPresence(roomId, clientKey, data)
    return
  }
  if (event === "presence.heartbeat") {
    await heartbeatPresence(roomId, clientKey)
    return
  }
  if (event === "presence.unsubscribe") {
    await removePresence(roomId, clientKey)
    return
  }
  if (event === "typing.start") {
    const targetRoom = roomId === "admin" ? data.conversation_id : roomId
    if (targetRoom) await setTyping(targetRoom, clientKey, data, roomId)
    return
  }
  if (event === "typing.stop") {
    const targetRoom = roomId === "admin" ? data.conversation_id : roomId
    if (targetRoom) await clearTyping(targetRoom, clientKey, data, roomId)
  }
}

const server = http.createServer(async (req, res) => {
  if (req.method === "POST" && req.url === "/api/broadcast") {
    let body = ""
    req.on("data", (chunk) => {
      body += chunk
    })
    req.on("end", () => {
      try {
        const payload = JSON.parse(body) as BroadcastPayload
        const delivered = broadcast(
          payload.conversation_id,
          {
            event: payload.event,
            data: payload.data,
            conversation_id: payload.conversation_id,
          },
          Boolean(payload.notify_admin)
        )
        res.writeHead(200, { "Content-Type": "application/json" })
        res.end(JSON.stringify({ status: "ok", delivered_to: delivered }))
      } catch (err) {
        res.writeHead(400, { "Content-Type": "application/json" })
        res.end(JSON.stringify({ error: "Invalid broadcast payload" }))
      }
    })
    return
  }

  res.writeHead(404, { "Content-Type": "application/json" })
  res.end(JSON.stringify({ error: "Not found" }))
})

const wss = new WebSocketServer({ noServer: true })

server.on("upgrade", (request, socket, head) => {
  const url = new URL(request.url || "", `http://${request.headers.host}`)
  const match = url.pathname.match(/^\/ws\/chat\/([^/]+)$/)
  if (!match) {
    socket.destroy()
    return
  }

  const roomId = decodeURIComponent(match[1])
  wss.handleUpgrade(request, socket, head, (ws) => {
    wss.emit("connection", ws, request, roomId)
  })
})

wss.on("connection", (socket: WebSocket, _request, roomId: string) => {
  const clientKey = `ws_${Date.now()}_${Math.random().toString(36).slice(2)}`
  socketRooms.set(socket, roomId)
  socketKeys.set(socket, clientKey)
  if (roomId === "admin") {
    adminConnections.add(socket)
    console.info("[ADMIN_CONNECTED]", { websocket_id: clientKey })
  } else {
    if (!activeConnections.has(roomId)) {
      activeConnections.set(roomId, new Set())
    }
    activeConnections.get(roomId)!.add(socket)
  }

  socket.on("message", (raw) => {
    void handleSocketMessage(socket, roomId, raw.toString())
  })

  socket.on("close", () => {
    const key = socketKeys.get(socket)
    const room = socketRooms.get(socket)
    if (key && room) {
      void clearTyping(room, key, {}, room)
      void removePresence(room, key)
      activeConnections.get(room)?.delete(socket)
      adminConnections.delete(socket)
    }
    socketKeys.delete(socket)
    socketRooms.delete(socket)
  })
})

setInterval(() => {
  const cutoff = Date.now() - 30_000
  for (const [room, entries] of presence.entries()) {
    for (const [key, entry] of entries.entries()) {
      if (entry.online && new Date(entry.last_seen_at).getTime() < cutoff) {
        void removePresence(room, key)
      }
    }
  }
}, 5_000)

setInterval(() => {
  const cutoff = Date.now() - 5_000
  for (const [room, entries] of typing.entries()) {
    for (const [key, value] of entries.entries()) {
      if (new Date(value.updated_at).getTime() < cutoff) {
        void clearTyping(room, key, { timeout: true }, room)
      }
    }
  }
}, 2_000)

server.listen(PORT, "0.0.0.0", () => {
  console.info(`[MEDUSA_REALTIME] listening on ${PORT}`)
})
