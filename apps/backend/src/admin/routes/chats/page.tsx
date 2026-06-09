import { Container, Heading, Text, Button, Badge, Input, Avatar } from "@medusajs/ui"
import { toast } from "@medusajs/ui"
import { defineRouteConfig } from "@medusajs/admin-sdk"
import { Component, useEffect, useState, useRef, type ErrorInfo, type ReactNode } from "react"
import ReactMarkdown from "react-markdown"
import { useTranslation } from "react-i18next"
import { useChatNotifications } from "../../lib/chat-notifications"

type ChatMessage = {
  id: string
  content: string
  sender_type: "customer" | "guest" | "bot" | "admin"
  created_at: string
  conversation_id?: string
}

type ChatConversation = {
  id: string
  customer_id?: string
  guest_id?: string
  customer_name?: string
  customer_email?: string
  status: "BOT_HANDLED" | "WAITING_ADMIN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED"
  last_message_at?: string
  last_message_preview?: string
  last_message_sender?: ChatMessage["sender_type"] | null
  escalation_reason?: string
  admin_metadata?: {
    unread_admin_count?: number
    last_customer_message_at?: string
    last_admin_message_at?: string
    auto_returned_at?: string
    auto_return_reason?: string
  }
}

type ChatStatus = ChatConversation["status"]

type ChatStats = {
  total_conversations: number
  ai_handled_conversations: number
  escalated_conversations: number
  ai_resolution_rate: number
  average_escalation_time_minutes: number | null
  human_resolution_time_minutes: number | null
}

type IconProps = {
  className?: string
}

type StatusMeta = {
  label: string
  description: string
  badgeColor: "green" | "orange" | "blue" | "grey"
  dotClassName: string
}

type ErrorBoundaryStrings = {
  panelTitle: string
  panelDescription: string
}

type TranslateOptions = Record<string, unknown>
type Translate = (key: string, fallbackOrOptions?: string | TranslateOptions) => string

const CHAT_FALLBACKS: Record<string, string> = {
  "chat.sidebar.title": "Hỗ trợ trực tuyến",
  "chat.sidebar.connected": "Đã kết nối",
  "chat.sidebar.connecting": "Đang kết nối...",
  "chat.sidebar.disconnected": "Mất kết nối",
  "chat.sidebar.searchPlaceholder": "Tìm kiếm cuộc trò chuyện...",
  "chat.sidebar.noConversations": "Chưa có cuộc trò chuyện nào",
  "chat.stats.aiHandled": "Bot xử lý",
  "chat.stats.aiRate": "Tỷ lệ AI xử lý",
  "chat.stats.escalated": "Chuyển nhân viên",
  "chat.stats.escTime": "Thời gian tiếp nhận",
  "chat.empty.title": "Chọn một cuộc trò chuyện",
  "chat.empty.description": "Chọn cuộc trò chuyện từ danh sách bên trái để bắt đầu hỗ trợ",
  "chat.notifications.baseTitle": "Medusan Chat",
  "chat.notifications.notificationTitle": "Medusan",
  "chat.sender.bot": "Bot",
  "chat.sender.guest": "Khách",
  "chat.sender.you": "Bạn",
  "chat.sender.customer": "Khách hàng",
  "chat.sender.unknown": "Khách",
  "chat.error.panelTitle": "Không thể hiển thị khung chat",
  "chat.error.panelDescription": "Có lỗi render trong Chat Panel. Xem console với log CHAT_PANEL_RENDER_ERROR để xử lý chi tiết.",
  "chat.error.loadConversations": "Không thể tải danh sách chat",
  "chat.error.loadMessages": "Không thể tải tin nhắn",
  "chat.error.sendMessage": "Gửi tin nhắn thất bại",
  "chat.error.updateStatus": "Không thể cập nhật",
  "chat.success.updateStatus": "Cập nhật trạng thái thành công",
  "chat.presence.online": "Đang online",
  "chat.presence.offline": "Offline",
  "chat.presence.justNow": "vừa xong",
  "chat.presence.minutesAgo": "cách {{count}} phút",
  "chat.presence.hoursAgo": "cách {{count}} giờ",
  "chat.presence.daysAgo": "cách {{count}} ngày",
  "chat.customer.customer": "Khách",
  "chat.customer.guest": "Ẩn danh",
  "chat.header.loggedInCustomer": "Khách hàng đăng nhập",
  "chat.header.anonymousCustomer": "Khách hàng ẩn danh",
  "chat.header.botProcessing": "Bot đang xử lý",
  "chat.header.sessionClosed": "Phiên đã đóng",
  "chat.actions.takeOver": "Tiếp nhận hỗ trợ",
  "chat.actions.returnToBot": "Giao lại cho Bot",
  "chat.actions.closeSession": "Đóng phiên",
  "chat.actions.reopenSession": "Nhận lại phiên",
  "chat.messages.noMessages": "Chưa có tin nhắn nào",
  "chat.messages.placeholder": "Gõ tin nhắn... (Shift + Enter để xuống dòng)",
  "chat.messages.botProcessing": "Bot đang xử lý cuộc trò chuyện này.",
  "chat.messages.waitingForAdmin": "Tiếp nhận hỗ trợ để bắt đầu trả lời khách.",
  "chat.messages.sessionClosed": "Phiên đã đóng.",
  "chat.messages.imageAlt": "Hình ảnh trong chat",
  "chat.status.botHandled.label": "Bot đang hỗ trợ",
  "chat.status.botHandled.description": "AI đang phụ trách cuộc hội thoại này.",
  "chat.status.waitingAdmin.label": "Chờ nhân viên tiếp nhận",
  "chat.status.waitingAdmin.description": "Khách đang chờ admin tiếp nhận hỗ trợ.",
  "chat.status.inProgress.label": "Nhân viên đang hỗ trợ",
  "chat.status.inProgress.description": "Admin đang hỗ trợ khách. Bot không trả lời trong phiên này.",
  "chat.status.closed.label": "Đã đóng",
  "chat.status.closed.description": "Phiên hỗ trợ đã kết thúc.",
  "chat.status.resolved.label": "Đã đóng",
  "chat.status.resolved.description": "Phiên hỗ trợ đã kết thúc.",
  "common.loading": "Đang tải...",
  "common.error": "Lỗi",
  "common.success": "Thành công",
}

const makeTranslate = (translate: ReturnType<typeof useTranslation>["t"]): Translate => {
  return (key, fallbackOrOptions) => {
    const fallback = typeof fallbackOrOptions === "string"
      ? fallbackOrOptions
      : CHAT_FALLBACKS[key] || key
    const options = typeof fallbackOrOptions === "object"
      ? { ...fallbackOrOptions, defaultValue: fallback }
      : fallback
    const translated = (translate as any)(key, options)
    if (translated === key) {
      return fallback
    }

    return translated
  }
}

const createIcon = (content: ReactNode) => ({ className }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    {content}
  </svg>
)

const SearchIcon = createIcon(<><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>)
const SendIcon = createIcon(<><path d="m22 2-7 20-4-9-9-4 20-7Z" /><path d="M11 13 22 2" /></>)
const UserIcon = createIcon(<><path d="M20 21a8 8 0 0 0-16 0" /><circle cx="12" cy="8" r="4" /></>)
const AlertCircleIcon = createIcon(<><circle cx="12" cy="12" r="10" /><path d="M12 8v4" /><path d="M12 16h.01" /></>)
const MessageSquareIcon = createIcon(<><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></>)

type ChatPanelErrorBoundaryProps = {
  children: ReactNode
  strings: ErrorBoundaryStrings
}

type ChatPanelErrorBoundaryState = {
  error: Error | null
}

class ChatPanelErrorBoundary extends Component<ChatPanelErrorBoundaryProps, ChatPanelErrorBoundaryState> {
  state: ChatPanelErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("CHAT_PANEL_RENDER_ERROR", error, errorInfo)
  }

  componentDidUpdate(prevProps: ChatPanelErrorBoundaryProps) {
    if (this.state.error && prevProps.children !== this.props.children) {
      this.setState({ error: null })
    }
  }

  render() {
    if (this.state.error) {
      const { panelTitle, panelDescription } = this.props.strings
      return (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 bg-ui-bg-subtle text-ui-fg-base p-6">
          <AlertCircleIcon className="w-10 h-10 text-ui-fg-error" />
          <Heading level="h2" className="text-lg">{panelTitle}</Heading>
          <Text size="small" className="text-ui-fg-muted text-center max-w-md">
            {panelDescription}
          </Text>
        </div>
      )
    }

    return this.props.children
  }
}

const sortMessagesByCreatedAt = (items: ChatMessage[]) => {
  return [...items].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  )
}

const isAdminVisibleConversation = (conversation: ChatConversation) => {
  return ["WAITING_ADMIN", "IN_PROGRESS", "CLOSED", "RESOLVED"].includes(conversation.status)
}

const getStatusMeta = (
  status: ChatStatus,
  tt: Translate
): StatusMeta => {
  switch (status) {
    case "BOT_HANDLED":
      return {
        label: tt("chat.status.botHandled.label"),
        description: tt("chat.status.botHandled.description"),
        badgeColor: "green",
        dotClassName: "bg-green-500",
      }
    case "WAITING_ADMIN":
      return {
        label: tt("chat.status.waitingAdmin.label"),
        description: tt("chat.status.waitingAdmin.description"),
        badgeColor: "orange",
        dotClassName: "bg-yellow-500",
      }
    case "IN_PROGRESS":
      return {
        label: tt("chat.status.inProgress.label"),
        description: tt("chat.status.inProgress.description"),
        badgeColor: "blue",
        dotClassName: "bg-blue-500",
      }
    case "CLOSED":
      return {
        label: tt("chat.status.closed.label"),
        description: tt("chat.status.closed.description"),
        badgeColor: "grey",
        dotClassName: "bg-gray-500",
      }
    case "RESOLVED":
      return {
        label: tt("chat.status.resolved.label"),
        description: tt("chat.status.resolved.description"),
        badgeColor: "grey",
        dotClassName: "bg-gray-500",
      }
  }
}

const ChatAdminPage = () => {
  const { t, i18n } = useTranslation()
  const tt = makeTranslate(t)
  const [conversations, setConversations] = useState<ChatConversation[]>([])
  const [filteredConversations, setFilteredConversations] = useState<ChatConversation[]>([])
  const [activeConversation, setActiveConversation] = useState<ChatConversation | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [presenceMap, setPresenceMap] = useState<Record<string, { online: boolean; last_seen_at?: string | null }>>({})
  const [customerTypingMap, setCustomerTypingMap] = useState<Record<string, boolean>>({})
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(true)
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected")
  const wsRef = useRef<WebSocket | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<"WAITING_ADMIN" | "IN_PROGRESS" | "CLOSED">("WAITING_ADMIN")
  const [stats, setStats] = useState<ChatStats | null>(null)
  const {
    permission,
    support: notificationSupport,
    serviceWorkerStatus,
    unreadCount,
    notify,
    markRead,
    testNotification,
  } = useChatNotifications({
    baseTitle: tt("chat.notifications.baseTitle"),
    notificationTitle: tt("chat.notifications.notificationTitle"),
  })

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const activeConversationRef = useRef<ChatConversation | null>(null)
  const lastActiveConvIdRef = useRef<string | null>(null)
  const adminTypingStopRef = useRef<number | null>(null)
  const customerTypingTimeoutsRef = useRef<Record<string, number>>({})
  const notifyRef = useRef(notify)
  const translateRef = useRef(tt)

  const errorBoundaryStrings: ErrorBoundaryStrings = {
    panelTitle: tt("chat.error.panelTitle"),
    panelDescription: tt("chat.error.panelDescription"),
  }

  useEffect(() => {
    console.log("[ADMIN_CHAT_I18N_LANGUAGE]", i18n.language)
    console.log("[ADMIN_CHAT_I18N_STORE]", i18n.store?.data)
    console.log("[ADMIN_CHAT_I18N_SAMPLE]", tt("chat.sidebar.title"))
  }, [i18n.language])

  const getSidebarConversations = (list: ChatConversation[]) => {
    let result = list

    if (searchQuery) {
      const normalizedSearch = searchQuery.toLowerCase()
      result = result.filter(c =>
        (c.customer_id && c.customer_id.toLowerCase().includes(normalizedSearch)) ||
        (c.guest_id && c.guest_id.toLowerCase().includes(normalizedSearch))
      )
    }

    result = result.filter(c =>
      statusFilter === "CLOSED"
        ? c.status === "CLOSED" || c.status === "RESOLVED"
        : c.status === statusFilter
    )

    return result
  }

  const syncActiveConversationFromList = (list: ChatConversation[]) => {
    const current = activeConversationRef.current
    if (!current) {
      return
    }

    const updated = list.find((c) => c.id === current.id)
    const sidebarList = getSidebarConversations(list)

    if (updated && sidebarList.some((c) => c.id === updated.id)) {
      if (
        updated.status !== current.status ||
        JSON.stringify(updated.admin_metadata) !== JSON.stringify(current.admin_metadata)
      ) {
        setActiveConversation(updated)
      }
      return
    }

    setActiveConversation(sidebarList[0] || null)
  }

  useEffect(() => {
    activeConversationRef.current = activeConversation
    if (activeConversation) {
      markRead()
    }
  }, [activeConversation, markRead])

  useEffect(() => {
    notifyRef.current = notify
    translateRef.current = tt
  }, [notify, tt])

  useEffect(() => {
    fetchConversations()
  }, [])

  useEffect(() => {
    const result = getSidebarConversations(conversations)
    setFilteredConversations(result)

    if (
      activeConversationRef.current &&
      !result.some((conversation) => conversation.id === activeConversationRef.current?.id)
    ) {
      setActiveConversation(result[0] || null)
    }
  }, [conversations, searchQuery, statusFilter])

  useEffect(() => {
    if (activeConversation) {
      if (activeConversation.id !== lastActiveConvIdRef.current) {
        lastActiveConvIdRef.current = activeConversation.id
        setMessages([])
        fetchMessages(activeConversation.id)
      }
      const fetchPresence = async () => {
        try {
          const res = await fetch(`/admin/chats/${activeConversation.id}/presence`)
          const data = await res.json()
          const list = data.presences || []
          const anyOnline = list.some((p: any) => p.online)
          let latest: string | null = null
          if (list.length > 0) {
            latest = list.reduce((acc: string | null, cur: any) => {
              if (!cur.last_seen_at) return acc
              if (!acc) return cur.last_seen_at
              return new Date(cur.last_seen_at) > new Date(acc) ? cur.last_seen_at : acc
            }, null)
          }
          setPresenceMap(prev => ({ ...prev, [activeConversation.id]: { online: anyOnline, last_seen_at: latest } }))
        } catch {
          // ignore
        }
      }
      void fetchPresence()
    } else {
      lastActiveConvIdRef.current = null
    }
  }, [activeConversation])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    let reconnectTimer: NodeJS.Timeout

    const connect = () => {
      setWsStatus("connecting")
      const wsUrl = `ws://localhost:8080/ws/chat/admin`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setWsStatus("connected")
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.event === "chat.message.created") {
            const msg = payload.data
            const customEvent = new CustomEvent("new_chat_message", { detail: payload })
            window.dispatchEvent(customEvent)
            void notifyRef.current(
              {
                id: msg.id,
                conversationId: msg.conversation_id,
                senderLabel: msg.sender_type === "bot" ? translateRef.current("chat.sender.bot") : translateRef.current("chat.sender.guest"),
                content: msg.content || "",
              },
              msg.sender_type !== "admin" && (document.hidden || activeConversationRef.current?.id !== msg.conversation_id)
            )

            fetchConversations(false)
          }
          if (payload.event === "conversation.status.updated") {
            const updated = payload.data?.conversation as ChatConversation | undefined
            if (updated) {
              setConversations((current) => {
                const exists = current.some((conversation) => conversation.id === updated.id)
                return exists
                  ? current.map((conversation) => conversation.id === updated.id ? updated : conversation)
                  : [...current, updated]
              })
              if (activeConversationRef.current?.id === updated.id) {
                setActiveConversation(updated)
              }
            }
          }
          if (payload.event === "typing.start" && payload.data?.user_type !== "admin") {
            const convId = payload.conversation_id
            if (convId) {
              setCustomerTypingMap(prev => ({ ...prev, [convId]: true }))
              const existing = customerTypingTimeoutsRef.current[convId]
              if (existing) {
                window.clearTimeout(existing)
              }
              customerTypingTimeoutsRef.current[convId] = window.setTimeout(() => {
                setCustomerTypingMap(prev => ({ ...prev, [convId]: false }))
              }, 5000)
            }
          }
          if (payload.event === "typing.stop" && payload.data?.user_type !== "admin") {
            const convId = payload.conversation_id
            if (convId) {
              setCustomerTypingMap(prev => ({ ...prev, [convId]: false }))
            }
          }
          if (payload.event === "presence.updated") {
            try {
              const convId = payload.conversation_id
              const list = payload.data || []
              const anyOnline = list.some((p: any) => p.online)
              let latest: string | null = null
              if (list.length > 0) {
                latest = list.reduce((acc: string | null, cur: any) => {
                  if (!cur.last_seen_at) return acc
                  if (!acc) return cur.last_seen_at
                  return new Date(cur.last_seen_at) > new Date(acc) ? cur.last_seen_at : acc
                }, null)
              }
              setPresenceMap(prev => ({ ...prev, [convId]: { online: anyOnline, last_seen_at: latest } }))
            } catch {
              // ignore
            }
          }
        } catch {
          // ignore
        }
      }

      ws.onclose = () => {
        setWsStatus("disconnected")
        reconnectTimer = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      clearTimeout(reconnectTimer)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
      if (adminTypingStopRef.current) {
        window.clearTimeout(adminTypingStopRef.current)
        adminTypingStopRef.current = null
      }
      Object.values(customerTypingTimeoutsRef.current).forEach((timeoutId) => window.clearTimeout(timeoutId))
      customerTypingTimeoutsRef.current = {}
    }
  }, [])

  useEffect(() => {
    const handleNewMessage = (e: Event) => {
      const customEvent = e as CustomEvent
      const payload = customEvent.detail
      const msg = payload.data

      if (activeConversation && msg.conversation_id === activeConversation.id) {
        setMessages(prev => {
          if (prev.some(m => m.id === msg.id)) return prev
          return sortMessagesByCreatedAt([...prev, msg])
        })
      }
    }

    window.addEventListener("new_chat_message", handleNewMessage)
    return () => window.removeEventListener("new_chat_message", handleNewMessage)
  }, [activeConversation])

  const fetchConversations = async (showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      const res = await fetch("/admin/chats")
      const data = await res.json()
      const list = data.conversations || []
      setConversations(list)
      setStats(data.stats || null)
      syncActiveConversationFromList(list)
    } catch {
      toast.error(tt("common.error"), { description: tt("chat.error.loadConversations") })
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  const fetchMessages = async (id: string) => {
    try {
      const res = await fetch(`/admin/chats/${id}/messages`)
      const data = await res.json()
      const history = Array.isArray(data.messages) ? data.messages : []

      if (activeConversationRef.current?.id !== id) {
        return
      }

      setMessages(prev => {
        const mergedById = new Map<string, ChatMessage>()

        for (const message of prev) {
          mergedById.set(message.id, message)
        }

        for (const message of history) {
          mergedById.set(message.id, message)
        }

        return sortMessagesByCreatedAt(Array.from(mergedById.values()))
      })
    } catch {
      toast.error(tt("common.error"), { description: tt("chat.error.loadMessages") })
    }
  }

  const sendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!input.trim() || !activeConversation || activeConversation.status !== "IN_PROGRESS") return

    const tempInput = input.trim()
    setInput("")
    emitAdminTyping("typing.stop")
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }

    try {
      await fetch(`/admin/chats/${activeConversation.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: tempInput }),
      })
    } catch {
      toast.error(tt("common.error"), { description: tt("chat.error.sendMessage") })
    }
  }

  const updateStatus = async (status: "WAITING_ADMIN" | "IN_PROGRESS" | "CLOSED" | "BOT_HANDLED") => {
    if (!activeConversation) return
    const endpoint =
      status === "WAITING_ADMIN"
        ? "handover"
        : status === "IN_PROGRESS"
          ? "assign"
          : status === "BOT_HANDLED"
            ? "return-to-bot"
            : "close"

    try {
      const res = await fetch(`/admin/chats/${activeConversation.id}/${endpoint}`, { method: "POST" })
      const data = await res.json().catch(() => null)
      console.log("ACTION_RESPONSE", data)
      console.log("SELECTED_CONVERSATION", activeConversationRef.current)

      if (!res.ok) {
        throw new Error(data?.error || `Admin chat action failed with status ${res.status}`)
      }

      const updatedConversation = data?.conversation as ChatConversation | undefined
      if (!updatedConversation) {
        throw new Error("Admin chat action response is missing conversation")
      }

      const nextConversations = isAdminVisibleConversation(updatedConversation)
        ? conversations.map((conversation) =>
          conversation.id === updatedConversation.id ? updatedConversation : conversation
        )
        : conversations.filter((conversation) => conversation.id !== updatedConversation.id)

      setConversations(nextConversations)

      const sidebarList = getSidebarConversations(nextConversations)
      if (sidebarList.some((conversation) => conversation.id === updatedConversation.id)) {
        setActiveConversation(updatedConversation)
      } else {
        setActiveConversation(sidebarList[0] || null)
      }

      toast.success(tt("common.success"), { description: tt("chat.success.updateStatus") })
      void fetchConversations(false)
    } catch (err) {
      console.error("CHAT_ACTION_ERROR", err)
      toast.error(tt("common.error"), { description: tt("chat.error.updateStatus") })
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const emitAdminTyping = (event: "typing.start" | "typing.stop") => {
    const ws = wsRef.current
    if (!activeConversation || !ws || ws.readyState !== WebSocket.OPEN) {
      return
    }

    ws.send(JSON.stringify({
      event,
      data: {
        conversation_id: activeConversation.id,
        user_type: "admin",
        name: "NV Hỗ trợ",
      },
    }))
  }

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    emitAdminTyping("typing.start")
    if (adminTypingStopRef.current) {
      window.clearTimeout(adminTypingStopRef.current)
    }
    adminTypingStopRef.current = window.setTimeout(() => {
      emitAdminTyping("typing.stop")
    }, 1200)
    e.target.style.height = 'auto'
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`
  }

  const formatLastSeen = (iso: string | null | undefined) => {
    if (!iso) return ""
    const then = new Date(iso).getTime()
    const delta = Math.floor((Date.now() - then) / 1000)
    if (delta < 60) return tt("chat.presence.justNow")
    if (delta < 3600) return tt("chat.presence.minutesAgo", { count: Math.floor(delta / 60) })
    if (delta < 86400) return tt("chat.presence.hoursAgo", { count: Math.floor(delta / 3600) })
    return tt("chat.presence.daysAgo", { count: Math.floor(delta / 86400) })
  }

  const renderedMessages = sortMessagesByCreatedAt(messages)
  const activeStatusMeta = activeConversation ? getStatusMeta(activeConversation.status, tt) : null

  return (
    <Container className="flex h-[calc(100vh-120px)] p-0 overflow-hidden divide-x border border-ui-border-base rounded-lg shadow-sm bg-ui-bg-base">
      {/* Sidebar */}
      <div className="w-[320px] flex flex-col bg-ui-bg-subtle shrink-0">
        <div className="p-4 border-b border-ui-border-base flex flex-col gap-4 bg-ui-bg-base">
          <div className="flex justify-between items-center">
            <Heading level="h2" className="text-lg">{tt("chat.sidebar.title")}</Heading>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && <Badge color="red" size="small">{unreadCount > 99 ? "99+" : unreadCount}</Badge>}
              {wsStatus === "connected" && <Badge color="green" size="small" className="animate-pulse">{tt("chat.sidebar.connected")}</Badge>}
              {wsStatus === "connecting" && <Badge color="orange" size="small">{tt("chat.sidebar.connecting")}</Badge>}
              {wsStatus === "disconnected" && <Badge color="red" size="small">{tt("chat.sidebar.disconnected")}</Badge>}
              <Button
                variant="secondary"
                size="small"
                onClick={async () => {
                  const ok = await testNotification()
                  if (!ok) {
                    if (permission === "denied") {
                      toast.error("Không thể gửi thông báo", {
                        description: "Quyền thông báo đang bị từ chối. Vui lòng bật thông báo trong cài đặt trình duyệt."
                      })
                    } else if (notificationSupport === "unsupported") {
                      toast.error("Không thể gửi thông báo", {
                        description: "Trình duyệt không hỗ trợ Web Notification."
                      })
                    } else {
                      toast.error("Không thể gửi thông báo", {
                        description: "Vui lòng cấp quyền thông báo khi được yêu cầu."
                      })
                    }
                  } else {
                    toast.success("Thông báo thử đã được gửi", {
                      description: "Kiểm tra thông báo hệ thống trên thiết bị của bạn."
                    })
                  }
                }}
              >
                Gửi thông báo thử
              </Button>
            </div>
          </div>

          <div className="flex flex-col gap-3">
            {notificationSupport === "unsupported" ? (
              <div className="rounded-md border border-ui-border-error bg-ui-bg-error p-2">
                <Text size="xsmall" className="text-ui-fg-error">Trình duyệt không hỗ trợ Web Notification.</Text>
              </div>
            ) : permission === "denied" ? (
              <div className="rounded-md border border-ui-border-error bg-ui-bg-error p-2 flex flex-col gap-1">
                <Text size="xsmall" className="text-ui-fg-error font-medium">Thông báo đang bị chặn</Text>
                <Text size="xsmall" className="text-ui-fg-muted">
                  Vui lòng bật quyền thông báo trong cài đặt trình duyệt (click vào biểu tượng ổ khóa ở thanh địa chỉ) để nhận thông báo tin nhắn mới.
                </Text>
              </div>
            ) : (
              <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                <Text size="xsmall" className="text-ui-fg-muted">
                  Notification: {permission}. Service worker: {serviceWorkerStatus?.supported ? `${serviceWorkerStatus.registrations} registration, push ${serviceWorkerStatus.pushSubscription ? "on" : "off"}` : "unsupported"}.
                </Text>
              </div>
            )}
            {stats && (
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                  <Text size="xsmall" className="text-ui-fg-muted">Tổng chat</Text>
                  <Text size="small" weight="plus">{stats.total_conversations}</Text>
                </div>
                <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                  <Text size="xsmall" className="text-ui-fg-muted">{tt("chat.stats.aiHandled")}</Text>
                  <Text size="small" weight="plus">{stats.ai_handled_conversations}/{stats.total_conversations}</Text>
                </div>
                <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                  <Text size="xsmall" className="text-ui-fg-muted">{tt("chat.stats.aiRate")}</Text>
                  <Text size="small" weight="plus">{stats.ai_resolution_rate}%</Text>
                </div>
                <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                  <Text size="xsmall" className="text-ui-fg-muted">{tt("chat.stats.escalated")}</Text>
                  <Text size="small" weight="plus">{stats.escalated_conversations}</Text>
                </div>
                <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                  <Text size="xsmall" className="text-ui-fg-muted">{tt("chat.stats.escTime")}</Text>
                  <Text size="small" weight="plus">{stats.average_escalation_time_minutes ?? "-"}m</Text>
                </div>
              </div>
            )}

            <div className="relative">
              <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-ui-fg-muted" />
              <Input
                placeholder={tt("chat.sidebar.searchPlaceholder")}
                className="pl-9 bg-ui-bg-field"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-3 gap-2">
              <Badge
                color="orange"
                className={`cursor-pointer justify-center whitespace-nowrap transition-colors ${statusFilter === 'WAITING_ADMIN' ? 'bg-yellow-500 text-white hover:bg-yellow-600' : ''}`}
                onClick={() => setStatusFilter('WAITING_ADMIN')}
              >
                🟡 Chờ
              </Badge>
              <Badge
                color="blue"
                className={`cursor-pointer justify-center whitespace-nowrap transition-colors ${statusFilter === 'IN_PROGRESS' ? 'bg-blue-600 text-white hover:bg-blue-700' : ''}`}
                onClick={() => setStatusFilter('IN_PROGRESS')}
              >
                🔵 Đang hỗ trợ
              </Badge>
              <Badge
                color="grey"
                className={`cursor-pointer justify-center whitespace-nowrap transition-colors ${statusFilter === 'CLOSED' ? 'bg-gray-700 text-white hover:bg-gray-800' : ''}`}
                onClick={() => setStatusFilter('CLOSED')}
              >
                ⚫ Đã đóng
              </Badge>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-6 text-center text-ui-fg-muted flex flex-col items-center gap-2">
              <div className="w-5 h-5 border-2 border-ui-fg-subtle border-t-transparent rounded-full animate-spin" />
              <Text size="small">{tt("common.loading")}</Text>
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="p-6 text-center text-ui-fg-muted flex flex-col items-center gap-2">
              <MessageSquareIcon className="w-8 h-8 text-ui-fg-disabled" />
              <Text size="small">{tt("chat.sidebar.noConversations")}</Text>
            </div>
          ) : (
            filteredConversations.map(conv => {
              const statusMeta = getStatusMeta(conv.status, tt)

              return (
                <button
                  key={conv.id}
                  onClick={() => setActiveConversation(conv)}
                  className={`w-full text-left p-4 border-b border-ui-border-base transition-colors relative ${activeConversation?.id === conv.id
                    ? "bg-ui-bg-base before:absolute before:left-0 before:top-0 before:bottom-0 before:w-1 before:bg-blue-500"
                    : "hover:bg-ui-bg-base-hover"
                    }`}
                >
                  <div className="flex items-start gap-3">
                    <Avatar
                      src=""
                      fallback={conv.customer_id ? tt("chat.customer.customer") : tt("chat.customer.guest")}
                      variant="squared"
                      size="base"
                      className={conv.customer_id ? "bg-blue-100 text-blue-700 mt-1" : "bg-gray-200 text-gray-700 mt-1"}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start mb-1">
                        <Text size="small" weight="plus" className="truncate text-ui-fg-base max-w-[150px]">
                          {conv.customer_id
                            ? `${tt("chat.customer.customer")} (${conv.customer_id.substring(0, 8)})`
                            : `${tt("chat.customer.guest")} (${conv.guest_id?.substring(0, 8)})`}
                        </Text>
                        <div className="flex flex-col items-end">
                          <Text size="xsmall" className="text-ui-fg-muted shrink-0 mt-0.5">
                            {conv.last_message_at ? new Date(conv.last_message_at).toLocaleTimeString("vi-VN", { hour: '2-digit', minute: '2-digit' }) : ""}
                          </Text>
                          <div className="text-[10px] text-ui-fg-muted mt-1">
                          {presenceMap[conv.id]?.online ? (
                            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-green-500" />{tt("chat.presence.online")}</span>
                          ) : customerTypingMap[conv.id] ? (
                            <span className="flex items-center gap-1 text-blue-600">✍️ Khách đang nhập...</span>
                          ) : presenceMap[conv.id]?.last_seen_at ? (
                            <span className="flex items-center gap-1">{formatLastSeen(presenceMap[conv.id].last_seen_at)}</span>
                          ) : null}
                          </div>
                        </div>
                      </div>
	                      <div className="flex items-center justify-between mt-2">
	                        <Badge size="small" color={statusMeta.badgeColor}>
                          <span className="flex items-center gap-1">
                            <span className={`h-2 w-2 rounded-full ${statusMeta.dotClassName}`} />
                            {statusMeta.label}
                          </span>
                        </Badge>
	                        {Number(conv.admin_metadata?.unread_admin_count || 0) > 0 && (
	                          <Badge size="small" color="red">{conv.admin_metadata?.unread_admin_count}</Badge>
	                        )}
	                      </div>
                        <Text size="xsmall" className="mt-2 line-clamp-2 text-ui-fg-muted">
                          {conv.last_message_sender === "bot" && "🤖 "}
                          {conv.last_message_sender === "admin" && "👨‍💼 "}
                          {(conv.last_message_sender === "customer" || conv.last_message_sender === "guest") && "👤 "}
                          {conv.last_message_preview || "Chưa có tin nhắn"}
                        </Text>
	                    </div>
	                  </div>
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <ChatPanelErrorBoundary strings={errorBoundaryStrings}>
      <div className="flex-1 flex flex-col bg-ui-bg-subtle relative min-w-0">
        {activeConversation ? (
          <>
            <div className="h-[72px] px-6 border-b border-ui-border-base flex justify-between items-center bg-ui-bg-base shrink-0 z-10 shadow-sm">
              <div className="flex items-center gap-4">
                <Avatar
                  size="large"
                  fallback={activeConversation.customer_id ? tt("chat.customer.customer") : tt("chat.customer.guest")}
                  variant="squared"
                  className={activeConversation.customer_id ? "bg-blue-100 text-blue-700" : "bg-gray-200 text-gray-700"}
                />
                <div>
                  <div className="flex items-center gap-2">
                    <Heading level="h2" className="text-base m-0 leading-none">
                      {activeConversation.customer_id ? tt("chat.header.loggedInCustomer") : tt("chat.header.anonymousCustomer")}
                    </Heading>
                    <Badge size="small" color={activeStatusMeta?.badgeColor || "grey"}>
                      <span className="flex items-center gap-1">
                        <span className={`h-2 w-2 rounded-full ${activeStatusMeta?.dotClassName || "bg-gray-500"}`} />
                        {activeStatusMeta?.label}
                      </span>
                    </Badge>
                    <div>
                      {presenceMap[activeConversation.id]?.online ? (
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-green-500" />
                          <Text size="xsmall" className="text-ui-fg-muted">{tt("chat.presence.online")}</Text>
                        </div>
                      ) : presenceMap[activeConversation.id]?.last_seen_at ? (
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-gray-400" />
                          <Text size="xsmall" className="text-ui-fg-muted">{formatLastSeen(presenceMap[activeConversation.id].last_seen_at)}</Text>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-gray-300" />
                          <Text size="xsmall" className="text-ui-fg-muted">{tt("chat.presence.offline")}</Text>
                        </div>
                      )}
                    </div>
                  </div>
                  <Text size="xsmall" className="text-ui-fg-muted mt-1.5 flex items-center gap-1">
                    <UserIcon className="w-3 h-3" />
                    ID: {activeConversation.id.substring(0, 12)}
                  </Text>
                </div>
              </div>
              <div className="flex gap-2">
                {activeConversation.status === "WAITING_ADMIN" && (
                  <Button variant="primary" size="small" onClick={() => updateStatus("IN_PROGRESS")}>
                    {tt("chat.actions.takeOver")}
                  </Button>
                )}
                {activeConversation.status === "IN_PROGRESS" && (
                  <>
                    <Button variant="secondary" size="small" onClick={() => updateStatus("BOT_HANDLED")}>
                      {tt("chat.actions.returnToBot")}
                    </Button>
                    <Button variant="transparent" size="small" className="text-ui-fg-error hover:bg-ui-bg-error" onClick={() => updateStatus("CLOSED")}>
                      {tt("chat.actions.closeSession")}
                    </Button>
                  </>
                )}
                {activeConversation.status === "BOT_HANDLED" && (
                  <Text size="small" className="text-ui-fg-muted self-center">{tt("chat.header.botProcessing")}</Text>
                )}
                {activeConversation.status === "CLOSED" && (
                  <>
                    <Text size="small" className="text-ui-fg-muted self-center">{tt("chat.header.sessionClosed")}</Text>
                    <Button variant="secondary" size="small" onClick={() => updateStatus("IN_PROGRESS")}>
                      {tt("chat.actions.reopenSession")}
                    </Button>
                  </>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 bg-ui-bg-subtle/30 scroll-smooth">
              <div className="flex flex-col justify-end min-h-full space-y-6">
                {renderedMessages.length === 0 ? (
                  <div className="text-center text-ui-fg-muted my-auto flex flex-col items-center gap-2">
                    <MessageSquareIcon className="w-12 h-12 text-ui-fg-disabled mb-2" />
                    <Text>{tt("chat.messages.noMessages")}</Text>
                  </div>
                ) : (
                  renderedMessages.map((msg, index) => {
                    const isAdmin = msg.sender_type === "admin"
                    const isBot = msg.sender_type === "bot"
                    const isCustomer = msg.sender_type === "customer"
                    const isGuest = msg.sender_type === "guest"

                    const showAvatar = index === renderedMessages.length - 1 || renderedMessages[index + 1].sender_type !== msg.sender_type

                    const extractedImages: { alt: string, url: string }[] = [];
                    const markdownImgRegex = /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g;
                    let cleanText = msg.content.replace(markdownImgRegex, (_match, alt, url) => {
                      extractedImages.push({ alt, url });
                      return '';
                    });

                    const rawImgRegex = /(?<!\()(https?:\/\/[^\s]+?\.(?:png|jpe?g|gif|webp|svg))(?!\))/ig;
                    cleanText = cleanText.replace(rawImgRegex, (url) => {
                      extractedImages.push({ alt: "Image", url });
                      return '';
                    });

                    cleanText = cleanText.trim();

                    const senderLabel = isAdmin
                      ? tt("chat.sender.you")
                      : isBot
                        ? tt("chat.sender.bot")
                        : isCustomer
                          ? tt("chat.sender.customer")
                          : isGuest
                            ? tt("chat.sender.guest")
                            : tt("chat.sender.unknown")

                    return (
                      <div key={msg.id} className={`flex gap-3 ${isAdmin ? "flex-row-reverse" : "flex-row"}`}>
                        <div className="w-8 shrink-0 flex flex-col justify-end">
                          {showAvatar && (
                            <Avatar
                              size="small"
                              fallback={isAdmin ? "A" : isBot ? "B" : "C"}
                              className={isAdmin ? "bg-blue-600 text-white" : isBot ? "bg-green-600 text-white" : "bg-gray-800 text-white"}
                            />
                          )}
                        </div>

                        <div className={`flex flex-col max-w-[70%] ${isAdmin ? "items-end" : "items-start"} space-y-2`}>
                          {extractedImages.length > 0 && (
                            <div className="flex flex-col gap-2">
                              {extractedImages.map((img, i) => (
                                <a key={i} href={img.url} target="_blank" rel="noopener noreferrer" className="block w-fit rounded-xl overflow-hidden border border-ui-border-base shadow-sm hover:opacity-90 transition-opacity bg-ui-bg-subtle">
                                  <img src={img.url} alt={img.alt || tt("chat.messages.imageAlt")} className="max-w-[320px] w-full h-auto max-h-[320px] object-cover" />
                                </a>
                              ))}
                            </div>
                          )}

                          {cleanText && (
                            <div className={`px-4 py-3 text-sm shadow-sm break-words overflow-wrap-break-word ${isAdmin
                              ? "bg-blue-600 text-white rounded-2xl rounded-br-sm"
                              : isBot
                                ? "bg-ui-bg-base text-ui-fg-base border border-ui-border-base rounded-2xl rounded-bl-sm"
                                : "bg-ui-bg-subtle text-ui-fg-base border border-ui-border-base rounded-2xl rounded-bl-sm"
                              }`}>
                              <ReactMarkdown
                                components={{
                                  h1: ({ node: _node, ...props }) => <h1 className="text-lg font-bold mt-3 mb-2" {...props} />,
                                  h2: ({ node: _node, ...props }) => <h2 className="text-base font-bold mt-2 mb-1" {...props} />,
                                  h3: ({ node: _node, ...props }) => <h3 className="text-sm font-bold mt-2 mb-1" {...props} />,
                                  p: ({ node: _node, ...props }) => <p className="mb-2 last:mb-0 leading-relaxed" {...props} />,
                                  ul: ({ node: _node, ...props }) => <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />,
                                  ol: ({ node: _node, ...props }) => <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />,
                                  li: ({ node: _node, ...props }) => <li className="mb-1" {...props} />,
                                  a: ({ node: _node, ...props }) => <a className="text-blue-500 hover:underline break-all" target="_blank" rel="noopener noreferrer" {...props} />,
                                  strong: ({ node: _node, ...props }) => <strong className="font-semibold" {...props} />,
                                  code: ({ node: _node, ...props }) => <code className="bg-black/10 dark:bg-white/10 rounded px-1 py-0.5 text-[13px]" {...props} />,
                                  pre: ({ node: _node, ...props }) => <pre className="bg-black/10 dark:bg-white/10 rounded-lg p-3 overflow-x-auto my-2 text-[13px]" {...props} />
                                }}
                              >
                                {cleanText}
                              </ReactMarkdown>
                            </div>
                          )}

                          <div className={`flex items-center gap-1 mt-1 px-1 ${isAdmin ? "flex-row-reverse" : "flex-row"}`}>
                            <Text size="xsmall" weight="plus" className="text-ui-fg-subtle">
                              {senderLabel}
                            </Text>
                            <span className="text-ui-fg-muted text-[10px]">•</span>
                            <Text size="xsmall" className="text-ui-fg-muted">
                              {new Date(msg.created_at).toLocaleTimeString("vi-VN", { hour: '2-digit', minute: '2-digit' })}
                            </Text>
                          </div>
                        </div>
                      </div>
                    )
                  })
                )}
                {activeConversation && customerTypingMap[activeConversation.id] ? (
                  <div className="flex justify-start">
                    <div className="flex items-center gap-2 rounded-2xl border border-ui-border-base bg-ui-bg-base px-4 py-3 text-sm text-ui-fg-muted shadow-sm">
                      <span className="flex gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                      </span>
                      <span>✍️ Khách đang nhập...</span>
                    </div>
                  </div>
                ) : null}
                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="p-4 border-t border-ui-border-base bg-ui-bg-base shrink-0">
              {activeConversation.status === "IN_PROGRESS" ? (
                <div className="relative flex items-end border border-ui-border-base rounded-xl bg-ui-bg-field focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500 transition-all shadow-sm overflow-hidden">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={handleTextareaInput}
                    onKeyDown={handleKeyDown}
                    placeholder={tt("chat.messages.placeholder")}
                    className="flex-1 max-h-[200px] min-h-[52px] resize-none px-4 py-3.5 bg-transparent text-sm focus:outline-none scrollbar-hide text-ui-fg-base placeholder:text-ui-fg-muted"
                    rows={1}
                  />
                  <div className="pr-2 pb-2 pl-2 flex shrink-0">
                    <Button
                      onClick={() => sendMessage()}
                      variant="primary"
                      className="w-10 h-10 p-0 rounded-lg flex items-center justify-center transition-transform active:scale-95"
                      disabled={!input.trim()}
                    >
                      <SendIcon className="w-4 h-4 text-white" />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="h-[52px] flex items-center justify-center bg-ui-bg-subtle rounded-xl border border-ui-border-base">
                  <Text size="small" className="text-ui-fg-muted flex items-center gap-2">
                    <AlertCircleIcon className="w-4 h-4" />
                    {activeConversation.status === "BOT_HANDLED" && tt("chat.messages.botProcessing")}
                    {activeConversation.status === "WAITING_ADMIN" && tt("chat.messages.waitingForAdmin")}
                    {activeConversation.status === "CLOSED" && tt("chat.messages.sessionClosed")}
                    {activeConversation.status === "RESOLVED" && tt("chat.messages.sessionClosed")}
                  </Text>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-ui-fg-subtle bg-ui-bg-subtle">
            <div className="w-20 h-20 bg-ui-bg-base rounded-3xl flex items-center justify-center shadow-sm border border-ui-border-base mb-6">
              <MessageSquareIcon className="w-10 h-10 text-blue-500" />
            </div>
            <Heading level="h1" className="text-xl mb-2 text-ui-fg-base">{tt("chat.empty.title")}</Heading>
            <Text className="max-w-xs text-center">{tt("chat.empty.description")}</Text>
          </div>
        )}
      </div>
	      </ChatPanelErrorBoundary>
        <aside className="w-[300px] shrink-0 bg-ui-bg-base p-4 overflow-y-auto">
          <div className="flex flex-col gap-4">
            <div>
              <Heading level="h2" className="text-base">Thông tin khách hàng</Heading>
              <Text size="small" className="text-ui-fg-muted mt-1">
                Hồ sơ hội thoại và SLA hỗ trợ
              </Text>
            </div>

            {activeConversation ? (
              <>
                <div className="rounded-lg border border-ui-border-base bg-ui-bg-subtle p-3">
                  <Text size="xsmall" className="text-ui-fg-muted">Loại khách</Text>
                  <Text size="small" weight="plus">
                    {activeConversation.customer_id ? "Khách đã đăng nhập" : "Khách ẩn danh"}
                  </Text>
                  <div className="mt-3 space-y-2">
                    {activeConversation.customer_id ? (
                      <>
                        <div>
                          <Text size="xsmall" className="text-ui-fg-muted">Customer ID</Text>
                          <Text size="small" className="break-all">{activeConversation.customer_id}</Text>
                        </div>
                        <div>
                          <Text size="xsmall" className="text-ui-fg-muted">Họ tên</Text>
                          <Text size="small">{activeConversation.customer_name || "Chưa có dữ liệu"}</Text>
                        </div>
                        <div>
                          <Text size="xsmall" className="text-ui-fg-muted">Email</Text>
                          <Text size="small">{activeConversation.customer_email || "Chưa có dữ liệu"}</Text>
                        </div>
                        <div>
                          <Text size="xsmall" className="text-ui-fg-muted">Tổng đơn hàng / chi tiêu</Text>
                          <Text size="small">Chưa đồng bộ vào chat profile</Text>
                        </div>
                      </>
                    ) : (
                      <>
                        <div>
                          <Text size="xsmall" className="text-ui-fg-muted">Guest ID</Text>
                          <Text size="small" className="break-all">{activeConversation.guest_id || "-"}</Text>
                        </div>
                        <div>
                          <Text size="xsmall" className="text-ui-fg-muted">Thiết bị / trình duyệt</Text>
                          <Text size="small">Chưa thu thập user-agent</Text>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                <div className="rounded-lg border border-ui-border-base bg-ui-bg-subtle p-3">
                  <Text size="xsmall" className="text-ui-fg-muted">Trạng thái hiện tại</Text>
                  <Badge size="small" color={activeStatusMeta?.badgeColor || "grey"} className="mt-2">
                    {activeStatusMeta?.label}
                  </Badge>
                  <Text size="small" className="mt-3 text-ui-fg-muted">
                    {activeStatusMeta?.description}
                  </Text>
                  {activeConversation.escalation_reason && (
                    <div className="mt-3">
                      <Text size="xsmall" className="text-ui-fg-muted">Lý do chuyển admin</Text>
                      <Text size="small">{activeConversation.escalation_reason}</Text>
                    </div>
                  )}
                  {activeConversation.admin_metadata?.auto_returned_at && (
                    <div className="mt-3 rounded-md border border-ui-border-base bg-ui-bg-base p-2">
                      <Text size="xsmall" className="text-ui-fg-muted">Auto return</Text>
                      <Text size="small">
                        {formatLastSeen(activeConversation.admin_metadata.auto_returned_at)}
                      </Text>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-ui-border-base bg-ui-bg-subtle p-4 text-center">
                <Text size="small" className="text-ui-fg-muted">Chọn một cuộc trò chuyện</Text>
              </div>
            )}
          </div>
        </aside>
	    </Container>
  )
}

const ChatIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
)

export const config = defineRouteConfig({
  label: "chat.routeLabel",
  icon: ChatIcon,
  translationNs: "chat",
})

export default ChatAdminPage
