"use client"

import { ChatBubbleLeftRight, PaperPlane, XMark } from "@medusajs/icons"
import clsx from "clsx"
import React, { FormEvent, useEffect, useRef, useState } from "react"
import { useChatNotifications } from "../../lib/chat-notifications"

type ProductCard = {
  title?: string
  url?: string
  image?: string | null
  price_from?: string
  discount?: string
}

type BotMessage = {
  id: string
  role: "bot" | "user" | "admin"
  text: string
  created_at: string
  payload?: {
    product?: ProductCard
    products?: ProductCard[]
  }
}

type ApiMessage = {
  id?: string
  text?: string
  payload?: BotMessage["payload"]
}

const initialMessages: BotMessage[] = [
  {
    id: "welcome",
    role: "bot",
    text: "Chào bạn, mình có thể hỗ trợ tìm sản phẩm, xem giá điện thoại, so sánh và kiểm tra đơn hàng khi bạn đã đăng nhập.",
    created_at: new Date(0).toISOString(),
  },
]

const suggestedQuestions = [
  "iPhone 17 Pro Max giá bao nhiêu?",
  "So sánh iPhone 15 và Samsung S26 Plus",
  "Top 5 sản phẩm giá cao nhất",
  "Tôi có đặt đơn nào không?",
]

const cleanBotText = (text: string) => {
  return text.trim()
}

const sortMessagesByCreatedAt = (items: BotMessage[]) => {
  return [...items].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  )
}

const mergeMessagesById = (...groups: BotMessage[][]) => {
  const merged = new Map<string, BotMessage>()

  for (const group of groups) {
    for (const message of group) {
      merged.set(message.id, message)
    }
  }

  return sortMessagesByCreatedAt(Array.from(merged.values()))
}

const getGuestId = () => {
  if (typeof window === "undefined") return ""
  const key = "chat_guest_id"
  const existing = window.localStorage.getItem(key)
  if (existing) {
    return existing
  }

  const next = "guest_" + crypto.randomUUID()
  window.localStorage.setItem(key, next)
  return next
}

const getConversationId = () => {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem("chat_conversation_id")
}

const clearConversationId = () => {
  if (typeof window === "undefined") return
  window.localStorage.removeItem("chat_conversation_id")
}

const FormattedText = ({ text }: { text: string }) => {
  const lines = text.split("\n")
  const elements: React.ReactNode[] = []
  let currentTable: string[][] = []
  let inTable = false

  const parseInline = (inlineText: string) => {
    const parts: React.ReactNode[] = []
    let currentIndex = 0

    const regex = /\*\*(.*?)\*\*|\[(.*?)\]\((.*?)\)/g
    let match

    while ((match = regex.exec(inlineText)) !== null) {
      const matchIndex = match.index
      if (matchIndex > currentIndex) {
        parts.push(inlineText.substring(currentIndex, matchIndex))
      }

      if (match[1] !== undefined) {
        parts.push(
          <strong key={matchIndex} className="font-bold text-black">
            {match[1]}
          </strong>
        )
      } else if (match[2] !== undefined) {
        parts.push(
          <a
            key={matchIndex}
            href={match[3]}
            className="font-bold text-black underline transition hover:text-gray-600"
            target="_blank"
            rel="noopener noreferrer"
          >
            {match[2]}
          </a>
        )
      }

      currentIndex = regex.lastIndex
    }

    if (currentIndex < inlineText.length) {
      parts.push(inlineText.substring(currentIndex))
    }

    return parts.length > 0 ? parts : inlineText
  }

  const parseLine = (line: string, key: string | number) => {
    if (!line.trim()) {
      return <div key={key} className="h-1.5" />
    }

    // Image pattern: ![caption](url)
    const imgRegex = /!\[(.*?)\]\((.*?)\)/g
    let imgMatch
    if ((imgMatch = imgRegex.exec(line)) !== null) {
      return (
        <div key={key} className="my-2.5 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition duration-300 hover:shadow-md">
          <img
            src={imgMatch[2]}
            alt={imgMatch[1]}
            className="w-full max-h-48 object-cover transition duration-500 hover:scale-105"
          />
          {imgMatch[1] && (
            <p className="border-t border-gray-100 bg-gray-50 p-2 text-center text-xs italic text-gray-500">
              {imgMatch[1]}
            </p>
          )}
        </div>
      )
    }

    // Headings
    if (line.startsWith("### ")) {
      return (
        <h4 key={key} className="mt-3.5 mb-1 text-sm font-bold text-black border-l-2 border-black pl-2">
          {parseInline(line.slice(4))}
        </h4>
      )
    }
    if (line.startsWith("## ")) {
      return (
        <h3 key={key} className="mt-4 mb-2 text-base font-bold text-black border-l-2 border-black pl-2">
          {parseInline(line.slice(3))}
        </h3>
      )
    }
    if (line.startsWith("# ")) {
      return (
        <h2 key={key} className="mt-4 mb-2 text-lg font-bold text-black border-l-2 border-black pl-2">
          {parseInline(line.slice(2))}
        </h2>
      )
    }

    // List items
    if (line.startsWith("- ") || line.startsWith("* ")) {
      return (
        <li key={key} className="ml-3 list-disc text-xs text-gray-800 my-0.5">
          {parseInline(line.slice(2))}
        </li>
      )
    }

    return (
      <p key={key} className="text-xs text-gray-800 leading-relaxed my-0.5">
        {parseInline(line)}
      </p>
    )
  }

  const renderTable = (tableData: string[][], key: string | number) => {
    if (!tableData.length) return null
    return (
      <div key={key} className="my-3 overflow-hidden rounded-xl border border-gray-200 shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-[11px]">
            <thead>
              <tr className="bg-gray-100 border-b border-gray-200">
                {tableData[0].map((cell, idx) => (
                  <th key={idx} className="p-2 font-bold text-black whitespace-nowrap">
                    {parseInline(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {tableData.slice(1).map((row, rIdx) => (
                <tr key={rIdx} className={clsx(rIdx % 2 === 0 ? "bg-white" : "bg-gray-50/50", "hover:bg-gray-100/50")}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="p-2 text-gray-800">
                      {parseInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (line.trim().startsWith("|")) {
      inTable = true
      const cells = line
        .split("|")
        .map((c) => c.trim())
        .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)

      if (cells.every((cell) => /^:?-+:?$/.test(cell))) {
        continue
      }

      currentTable.push(cells)
    } else {
      if (inTable && currentTable.length > 0) {
        elements.push(renderTable(currentTable, `table-${i}`))
        currentTable = []
        inTable = false
      }
      elements.push(parseLine(line, i))
    }
  }

  if (inTable && currentTable.length > 0) {
    elements.push(renderTable(currentTable, "table-end"))
  }

  return <div className="space-y-0.5">{elements}</div>
}

const ProductCards = ({ payload }: { payload?: BotMessage["payload"] }) => {
  const products = payload?.products || (payload?.product ? [payload.product] : [])

  if (!products.length) {
    return null
  }

  return (
    <div className="mt-3 grid gap-2.5">
      {products.map((product, index) => (
        <a
          key={`${product.url || product.title || "product"}-${index}`}
          href={product.url || "#"}
          target="_blank"
          rel="noopener noreferrer"
          className="group flex gap-3 rounded-xl border border-gray-200 bg-gray-50/50 p-2.5 transition duration-200 hover:border-black hover:bg-white"
        >
          {product.image ? (
            <div className="h-16 w-16 flex-none overflow-hidden rounded-lg border border-gray-200 bg-white">
              <img
                src={product.image}
                alt={product.title || "Product image"}
                className="h-full w-full object-cover transition duration-300 group-hover:scale-110"
              />
            </div>
          ) : (
            <div className="h-16 w-16 flex-none rounded-lg bg-gray-100" />
          )}
          <div className="min-w-0 flex-1 flex flex-col justify-center">
            <p className="line-clamp-1 text-xs font-bold text-gray-900 group-hover:text-black transition">
              {product.title || "Sản phẩm"}
            </p>
            <p className="mt-0.5 text-xs font-bold text-black">
              {product.price_from || "Chưa cập nhật giá"}
            </p>
            {product.discount ? (
              <span className="mt-1 self-start rounded bg-black px-1.5 py-0.5 text-[9px] font-bold text-white uppercase tracking-wider">
                {product.discount}
              </span>
            ) : null}
          </div>
        </a>
      ))}
    </div>
  )
}

const ChatMessage = ({ message }: { message: BotMessage }) => {
  return (
    <div
      className={clsx(
        "flex w-full",
        message.role === "user" ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={clsx(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm transition-all duration-200 relative",
          message.role === "user"
            ? "bg-black text-white rounded-br-none"
            : message.role === "admin"
              ? "border border-blue-200 bg-blue-50 text-gray-800 rounded-bl-none shadow-sm"
              : "border border-gray-200 bg-white text-gray-800 rounded-bl-none shadow-sm"
        )}
      >
        {message.role === "admin" && (
          <div className="text-[10px] font-bold text-blue-600 mb-1">NV Hỗ trợ</div>
        )}
        {message.role === "user" ? (
          <p className="whitespace-pre-line text-xs">{message.text}</p>
        ) : (
          <FormattedText text={message.text} />
        )}
        {message.role === "bot" ? <ProductCards payload={message.payload} /> : null}
      </div>
    </div>
  )
}

const CustomChat = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<BotMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected")
  const [agentOnline, setAgentOnline] = useState(false)
  const [agentLastSeen, setAgentLastSeen] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const heartbeatRef = useRef<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const isOpenRef = useRef(false)

  const [guestId, setGuestId] = useState<string>("")
  const {
    unreadCount,
    notify,
    markRead,
  } = useChatNotifications({
    baseTitle: "Medusan Chat",
    notificationTitle: "Medusan",
  })

  useEffect(() => {
    isOpenRef.current = isOpen
    if (isOpen) {
      markRead()
    }
  }, [isOpen, markRead])

  useEffect(() => {
    // Run only on client side to avoid hydration mismatch
    const id = getGuestId()
    setGuestId(id)

    const convId = getConversationId()
    if (convId) setConversationId(convId)
  }, [])

  const handleSetConversationId = (id: string) => {
    setConversationId(id)
    if (typeof window !== "undefined") {
      window.localStorage.setItem("chat_conversation_id", id)
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages, isOpen])

  useEffect(() => {
    console.table(
      sortMessagesByCreatedAt(messages).map((m) => ({
        id: m.id,
        sender: m.role,
        created_at: m.created_at,
        content: m.text,
      }))
    )
  }, [messages])

  // Load history on mount
  useEffect(() => {
    if (!guestId) return

    const loadHistory = async () => {
      try {
        const storedConversationId = getConversationId()
        console.log("[CHAT_LOCAL_STORAGE]", {
          chat_guest_id: guestId,
          chat_conversation_id: storedConversationId,
        })

        const params = new URLSearchParams({ guest_id: guestId })
        if (storedConversationId) {
          params.set("conversation_id", storedConversationId)
        }

        const response = await fetch(`/api/chatbot/history?${params.toString()}`)
        const data = await response.json()

        if (data.conversation?.id) {
          handleSetConversationId(data.conversation.id)
        } else if (storedConversationId) {
          clearConversationId()
          setConversationId(null)
        }

        if (data.messages && data.messages.length > 0) {
          const historyMessages = data.messages.map((m: any) => ({
            id: m.id,
            role: m.sender_type === "customer" || m.sender_type === "guest" ? "user" : m.sender_type === "admin" ? "admin" : "bot",
            text: m.content,
            created_at: m.created_at || new Date().toISOString(),
            payload: m.metadata?.payload
          }))
          setMessages(mergeMessagesById(historyMessages))
        } else {
          setMessages(initialMessages)
        }
      } catch (e) {
        console.error("Failed to load history", e)
        setMessages(initialMessages)
      } finally {
        setIsInitializing(false)
      }
    }

    loadHistory()
  }, [guestId])

  useEffect(() => {
    if (!conversationId || isInitializing) return

    let reconnectTimer: NodeJS.Timeout

    const connect = () => {
      setWsStatus("connecting")
      // Use Python chatbot service port (8080) for WebSockets
      const wsUrl = `ws://localhost:8080/ws/chat/${conversationId}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setWsStatus("connected")
        // subscribe presence for this guest
        try {
          ws.send(JSON.stringify({ event: "presence.subscribe", data: { guest_id: guestId, user_type: "guest", name: "Guest" } }))
        } catch (e) { }
        // start heartbeat
        try {
          const id = window.setInterval(() => {
            try {
              ws.send(JSON.stringify({ event: "presence.heartbeat", data: {} }))
            } catch (e) { }
          }, 15000)
          heartbeatRef.current = id
        } catch (e) { }
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.event === "chat.message.created") {
            const msg = payload.data
            // Ensure we don't add messages we already have
            if (msg.sender_type === "admin" || msg.sender_type === "bot") {
              const role = msg.sender_type === "admin" ? "admin" : "bot"
              const text = msg.content || ""
              setMessages(current => {
                if (current.find(m => m.id === msg.id)) return current
                return mergeMessagesById(current, [{
                  id: msg.id,
                  role,
                  text,
                  created_at: msg.created_at || new Date().toISOString(),
                  payload: msg.metadata?.payload
                }])
              })
              void notify(
                {
                  id: msg.id,
                  senderLabel: role === "admin" ? "Admin" : "Bot",
                  content: text,
                },
                document.hidden || !isOpenRef.current
              )
            }
          }
          if (payload.event === "presence.updated") {
            const list = payload.data || []
            // find admin presence entries
            const admins = list.filter((p: any) => p.user_type === "admin")
            const anyOnline = admins.some((a: any) => a.online)
            setAgentOnline(anyOnline)
            if (!anyOnline && admins.length > 0) {
              const latest = admins.reduce((acc: any, cur: any) => {
                return (!acc || new Date(cur.last_seen_at) > new Date(acc.last_seen_at)) ? cur : acc
              }, null)
              setAgentLastSeen(latest ? latest.last_seen_at : null)
            } else if (anyOnline) {
              setAgentLastSeen(null)
            }
          }
        } catch (e) {
          console.error("Failed to parse WS message", e)
        }
      }

      ws.onclose = () => {
        setWsStatus("disconnected")
        // Try to reconnect after 3s
        reconnectTimer = setTimeout(connect, 3000)
      }

      ws.onerror = (err) => {
        console.error("WebSocket error", err)
        ws.close()
      }
    }

    connect()

    return () => {
      clearTimeout(reconnectTimer)
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect on unmount
        try {
          wsRef.current.send(JSON.stringify({ event: "presence.unsubscribe", data: {} }))
        } catch (e) { }
        wsRef.current.close()
      }
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current)
        heartbeatRef.current = null
      }
    }
  }, [conversationId, notify])

  const formatLastSeen = (iso: string | null) => {
    if (!iso) return ""
    const then = new Date(iso).getTime()
    const delta = Math.floor((Date.now() - then) / 1000)
    if (delta < 60) return "vừa xong"
    if (delta < 3600) return `cách ${Math.floor(delta / 60)} phút`
    if (delta < 86400) return `cách ${Math.floor(delta / 3600)} giờ`
    return `cách ${Math.floor(delta / 86400)} ngày`
  }

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) {
      return
    }

    const optimisticUserId = crypto.randomUUID()
    const optimisticCreatedAt = new Date().toISOString()

    setMessages((current) =>
      mergeMessagesById(current, [{
        id: optimisticUserId,
        role: "user",
        text: trimmed,
        created_at: optimisticCreatedAt,
      }])
    )

    setInput("")
    setIsLoading(true)

    try {
      const response = await fetch("/api/chatbot", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: trimmed,
          guestId,
          conversationId,
        }),
      })
      const data = await response.json()

      if (data.conversationId) {
        handleSetConversationId(data.conversationId)
      }

      if (data.userMessage?.id) {
        const serverUserMessage: BotMessage = {
          id: data.userMessage.id,
          role: data.userMessage.sender_type === "customer" ? "user" : "admin",
          text: data.userMessage.content || trimmed,
          created_at: data.userMessage.created_at || optimisticCreatedAt,
        }

        setMessages((current) => {
          const withoutOptimistic = current.filter((message) => message.id !== optimisticUserId)
          return mergeMessagesById(withoutOptimistic, [serverUserMessage])
        })
      }

      if (!response.ok) {
        throw new Error(data?.error || "Chatbot request failed")
      }

      if (data.intent === "HumanHandover") {
        // Wait for admin response via SSE
        setIsLoading(false)
        return
      }

      const botMessages = (data.messages || []).map(
        (item: ApiMessage): BotMessage => ({
          id: item.id || crypto.randomUUID(),
          role: "bot",
          text: cleanBotText(item.text || "Mình chưa có phản hồi phù hợp."),
          created_at: item.created_at || new Date().toISOString(),
          payload: item.payload,
        })
      )

      if (document.hidden || !isOpenRef.current) {
        for (const botMessage of botMessages) {
          void notify(
            {
              id: botMessage.id,
              senderLabel: "Bot",
              content: botMessage.text,
            },
            true
          )
        }
      }

      setMessages((current) => {
        return mergeMessagesById(current, botMessages)
      })
    } catch (error) {
      const text =
        error instanceof Error
          ? error.message
          : "Mình đang gặp lỗi kết nối. Bạn thử lại sau nhé."

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "bot",
          text,
          created_at: new Date().toISOString(),
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void sendMessage(input)
  }

  return (
    <div className="fixed bottom-6 right-6 z-[9999] font-sans">
      {isOpen ? (
        <section className="flex h-[min(660px,calc(100vh-48px))] w-[min(430px,calc(100vw-32px))] flex-col overflow-hidden rounded-2xl border border-gray-300 bg-white shadow-2xl transition-all duration-300">
          <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-black px-4 text-white">
            <div className="flex items-center gap-2.5">
              <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-white">
                <ChatBubbleLeftRight className="h-5 w-5" />
                <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border border-black bg-white animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-bold tracking-wide">Trợ lý Medusa</p>
                  {wsStatus === "connected" && <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" title="Đã kết nối"></span>}
                  {wsStatus === "connecting" && <span className="h-2 w-2 rounded-full bg-yellow-500" title="Đang kết nối..."></span>}
                  {wsStatus === "disconnected" && <span className="h-2 w-2 rounded-full bg-red-500" title="Mất kết nối"></span>}
                </div>
                <p className="text-[10px] text-gray-400">
                  {agentOnline ? (
                    "Agent online"
                  ) : agentLastSeen ? (
                    `Agent ${formatLastSeen(agentLastSeen)}`
                  ) : (
                    "Online | AI Support"
                  )}
                </p>
              </div>
            </div>
            <button
              aria-label="Đóng chat"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-white/10 hover:text-white transition duration-200"
              type="button"
              onClick={() => setIsOpen(false)}
            >
              <XMark className="h-5 w-5" />
            </button>
          </header>

          <div className="flex-1 overflow-y-auto bg-gray-50/50 px-4 py-4">
            <div className="grid gap-4">
              {isInitializing ? (
                <div className="flex justify-center text-xs text-gray-500 py-4">Đang tải lịch sử...</div>
              ) : (
                sortMessagesByCreatedAt(messages).map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))
              )}
              {isLoading ? (
                <div className="flex justify-start">
                  <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-[11px] text-gray-500 shadow-sm">
                    <span className="flex gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                    </span>
                    <span>Đang suy nghĩ...</span>
                  </div>
                </div>
              ) : null}
              <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="border-t border-gray-250 bg-white p-4">
            <div className="mb-3 flex gap-2 overflow-x-auto pb-2">
              {suggestedQuestions.map((question) => (
                <button
                  key={question}
                  className="h-8 flex-none rounded-full border border-gray-200 bg-gray-50 px-3.5 text-xs font-bold text-gray-700 transition duration-200 hover:border-black hover:bg-black hover:text-white active:scale-95"
                  type="button"
                  onClick={() => sendMessage(question)}
                >
                  {question}
                </button>
              ))}
            </div>
            <form className="flex gap-2.5" onSubmit={onSubmit}>
              <input
                className="h-10 min-w-0 flex-1 rounded-full border border-gray-200 bg-gray-50 px-4 text-xs text-gray-800 outline-none transition duration-200 focus:border-black focus:bg-white focus:ring-1 focus:ring-black"
                placeholder="Nhập câu hỏi cho trợ lý..."
                value={input}
                onChange={(event) => setInput(event.target.value)}
                disabled={isInitializing}
              />
              <button
                aria-label="Gửi tin nhắn"
                className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-black text-white transition duration-200 hover:bg-gray-850 active:scale-95 disabled:cursor-not-allowed disabled:bg-gray-200"
                type="submit"
                disabled={!input.trim() || isLoading || isInitializing}
              >
                <PaperPlane className="h-4 w-4" />
              </button>
            </form>
          </div>
        </section>
      ) : (
        <button
          aria-label="Mở chat"
          className="flex h-14 w-14 items-center justify-center rounded-full bg-black text-white shadow-xl transition-all duration-300 hover:scale-110 hover:bg-gray-900 active:scale-95 relative group"
          type="button"
          onClick={() => setIsOpen(true)}
        >
          <ChatBubbleLeftRight className="h-6 w-6 transition group-hover:rotate-6" />
          {unreadCount > 0 ? (
            <span className="absolute -top-1.5 -right-1.5 flex min-h-5 min-w-5 items-center justify-center rounded-full border border-white bg-red-600 px-1.5 text-[10px] font-bold leading-none text-white shadow-sm">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          ) : (
            <span className="absolute -top-1 -right-1 flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-gray-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-4 w-4 bg-black text-[9px] font-bold text-white items-center justify-center border border-white">1</span>
            </span>
          )}
        </button>
      )}
    </div>
  )
}

export default CustomChat
