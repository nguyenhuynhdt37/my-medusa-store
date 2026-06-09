import { Container, Heading, Text, Button, Badge, Input, Avatar } from "@medusajs/ui"
import { toast } from "@medusajs/ui"
import { defineRouteConfig } from "@medusajs/admin-sdk"
import { Component, useEffect, useState, useRef, type ErrorInfo, type ReactNode } from "react"
import ReactMarkdown from "react-markdown"
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
  status: "BOT_HANDLED" | "WAITING_ADMIN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED"
  last_message_at?: string
  escalation_reason?: string
  admin_metadata?: {
    unread_admin_count?: number
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
      return (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 bg-ui-bg-subtle text-ui-fg-base p-6">
          <AlertCircleIcon className="w-10 h-10 text-ui-fg-error" />
          <Heading level="h2" className="text-lg">Không thể hiển thị khung chat</Heading>
          <Text size="small" className="text-ui-fg-muted text-center max-w-md">
            Có lỗi render trong Chat Panel. Xem console với log CHAT_PANEL_RENDER_ERROR để xử lý chi tiết.
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
  return ["BOT_HANDLED", "WAITING_ADMIN", "IN_PROGRESS", "CLOSED"].includes(conversation.status)
}

const getStatusMeta = (status: ChatStatus) => {
  switch (status) {
    case "BOT_HANDLED":
      return {
        label: "Bot đang hỗ trợ",
        description: "AI đang phụ trách cuộc hội thoại này.",
        badgeColor: "green" as const,
        dotClassName: "bg-green-500",
      }
    case "WAITING_ADMIN":
      return {
        label: "Chờ nhân viên tiếp nhận",
        description: "Khách đang chờ admin tiếp nhận hỗ trợ.",
        badgeColor: "orange" as const,
        dotClassName: "bg-yellow-500",
      }
    case "IN_PROGRESS":
      return {
        label: "Nhân viên đang hỗ trợ",
        description: "Admin đang hỗ trợ khách. Bot không trả lời trong phiên này.",
        badgeColor: "blue" as const,
        dotClassName: "bg-blue-500",
      }
    case "CLOSED":
      return {
        label: "Đã đóng",
        description: "Phiên hỗ trợ đã kết thúc.",
        badgeColor: "grey" as const,
        dotClassName: "bg-gray-500",
      }
    case "RESOLVED":
      return {
        label: "Đã đóng",
        description: "Phiên hỗ trợ đã kết thúc.",
        badgeColor: "grey" as const,
        dotClassName: "bg-gray-500",
      }
  }
}

const ChatAdminPage = () => {
  const [conversations, setConversations] = useState<ChatConversation[]>([])
  const [filteredConversations, setFilteredConversations] = useState<ChatConversation[]>([])
  const [activeConversation, setActiveConversation] = useState<ChatConversation | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [presenceMap, setPresenceMap] = useState<Record<string, { online: boolean; last_seen_at?: string | null }>>({})
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(true)
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected")
  const wsRef = useRef<WebSocket | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<"all" | "BOT_HANDLED" | "WAITING_ADMIN" | "IN_PROGRESS" | "CLOSED">("all")
  const [stats, setStats] = useState<ChatStats | null>(null)
  const {
    unreadCount,
    notify,
    markRead,
  } = useChatNotifications({
    baseTitle: "Medusan Chat",
    notificationTitle: "Medusan",
  })

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const activeConversationRef = useRef<ChatConversation | null>(null)
  const lastActiveConvIdRef = useRef<string | null>(null)

  const getSidebarConversations = (list: ChatConversation[]) => {
    let result = list

    if (searchQuery) {
      const normalizedSearch = searchQuery.toLowerCase()
      result = result.filter(c =>
        (c.customer_id && c.customer_id.toLowerCase().includes(normalizedSearch)) ||
        (c.guest_id && c.guest_id.toLowerCase().includes(normalizedSearch))
      )
    }

    if (statusFilter !== "all") {
      result = result.filter(c => c.status === statusFilter)
    }

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
      // fetch persisted presence for this conversation
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
        } catch (e) {
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
    console.table(
      sortMessagesByCreatedAt(messages).map((m) => ({
        id: m.id,
        sender: m.sender_type,
        created_at: m.created_at,
        content: m.content,
      }))
    )
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
            void notify(
              {
                id: msg.id,
                senderLabel: msg.sender_type === "bot" ? "Bot" : "Khách",
                content: msg.content || "",
              },
              msg.sender_type !== "admin" && (document.hidden || activeConversationRef.current?.id !== msg.conversation_id)
            )

            fetchConversations(false)
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
            } catch (e) {
              // ignore
            }
          }
        } catch (e) { }
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
    }
  }, []) // Mount once

  // Listen for custom event to update messages array safely with activeConversation context
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
    } catch (err) {
      toast.error("Lỗi", { description: "Không thể tải danh sách chat" })
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
    } catch (err) {
      toast.error("Lỗi", { description: "Không thể tải tin nhắn" })
    }
  }

  const sendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!input.trim() || !activeConversation || activeConversation.status !== "IN_PROGRESS") return

    const tempInput = input.trim()
    setInput("")
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }

    try {
      await fetch(`/admin/chats/${activeConversation.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: tempInput }),
      })
    } catch (err) {
      toast.error("Lỗi", { description: "Gửi tin nhắn thất bại" })
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

      toast.success("Thành công", { description: "Cập nhật trạng thái thành công" })
      void fetchConversations(false)
    } catch (err) {
      console.error("CHAT_ACTION_ERROR", err)
      toast.error("Lỗi", { description: "Không thể cập nhật" })
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`
  }

  const formatLastSeen = (iso: string | null | undefined) => {
    if (!iso) return ""
    const then = new Date(iso).getTime()
    const delta = Math.floor((Date.now() - then) / 1000)
    if (delta < 60) return "vừa xong"
    if (delta < 3600) return `cách ${Math.floor(delta / 60)} phút`
    if (delta < 86400) return `cách ${Math.floor(delta / 3600)} giờ`
    return `cách ${Math.floor(delta / 86400)} ngày`
  }

  const renderedMessages = sortMessagesByCreatedAt(messages)
  const activeStatusMeta = activeConversation ? getStatusMeta(activeConversation.status) : null

  return (
    <Container className="flex h-[calc(100vh-120px)] p-0 overflow-hidden divide-x border border-ui-border-base rounded-lg shadow-sm bg-ui-bg-base">
      {/* Sidebar */}
      <div className="w-[320px] flex flex-col bg-ui-bg-subtle shrink-0">
        <div className="p-4 border-b border-ui-border-base flex flex-col gap-4 bg-ui-bg-base">
          <div className="flex justify-between items-center">
            <Heading level="h2" className="text-lg">Trò chuyện</Heading>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && <Badge color="red" size="small">{unreadCount > 99 ? "99+" : unreadCount}</Badge>}
              {wsStatus === "connected" && <Badge color="green" size="small" className="animate-pulse">Connected</Badge>}
              {wsStatus === "connecting" && <Badge color="orange" size="small">Connecting...</Badge>}
              {wsStatus === "disconnected" && <Badge color="red" size="small">Disconnected</Badge>}
            </div>
          </div>

          <div className="flex flex-col gap-3">
            {stats && (
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                  <Text size="xsmall" className="text-ui-fg-muted">AI xử lý</Text>
                  <Text size="small" weight="plus">{stats.ai_handled_conversations}/{stats.total_conversations}</Text>
                </div>
                <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                  <Text size="xsmall" className="text-ui-fg-muted">AI rate</Text>
                  <Text size="small" weight="plus">{stats.ai_resolution_rate}%</Text>
                </div>
                <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                  <Text size="xsmall" className="text-ui-fg-muted">Escalated</Text>
                  <Text size="small" weight="plus">{stats.escalated_conversations}</Text>
                </div>
                <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-2">
                  <Text size="xsmall" className="text-ui-fg-muted">Esc. time</Text>
                  <Text size="small" weight="plus">{stats.average_escalation_time_minutes ?? "-"}m</Text>
                </div>
              </div>
            )}

            <div className="relative">
              <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-ui-fg-muted" />
              <Input
                placeholder="Tìm khách hàng..."
                className="pl-9 bg-ui-bg-field"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
              <Badge
                className={`cursor-pointer whitespace-nowrap transition-colors ${statusFilter === 'all' ? 'bg-ui-bg-interactive text-ui-fg-on-inverted hover:bg-ui-bg-interactive-hover' : ''}`}
                onClick={() => setStatusFilter('all')}
              >
                Tất cả
              </Badge>
              <Badge
                color="green"
                className={`cursor-pointer whitespace-nowrap transition-colors ${statusFilter === 'BOT_HANDLED' ? 'bg-green-600 text-white hover:bg-green-700' : ''}`}
                onClick={() => setStatusFilter('BOT_HANDLED')}
              >
                Bot hỗ trợ
              </Badge>
              <Badge
                color="orange"
                className={`cursor-pointer whitespace-nowrap transition-colors ${statusFilter === 'WAITING_ADMIN' ? 'bg-yellow-500 text-white hover:bg-yellow-600' : ''}`}
                onClick={() => setStatusFilter('WAITING_ADMIN')}
              >
                Chờ nhân viên
              </Badge>
              <Badge
                color="blue"
                className={`cursor-pointer whitespace-nowrap transition-colors ${statusFilter === 'IN_PROGRESS' ? 'bg-blue-600 text-white hover:bg-blue-700' : ''}`}
                onClick={() => setStatusFilter('IN_PROGRESS')}
              >
                Nhân viên hỗ trợ
              </Badge>
              <Badge
                color="grey"
                className={`cursor-pointer whitespace-nowrap transition-colors ${statusFilter === 'CLOSED' ? 'bg-gray-600 text-white hover:bg-gray-700' : ''}`}
                onClick={() => setStatusFilter('CLOSED')}
              >
                Đã đóng
              </Badge>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-6 text-center text-ui-fg-muted flex flex-col items-center gap-2">
              <div className="w-5 h-5 border-2 border-ui-fg-subtle border-t-transparent rounded-full animate-spin" />
              <Text size="small">Đang tải...</Text>
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="p-6 text-center text-ui-fg-muted flex flex-col items-center gap-2">
              <MessageSquareIcon className="w-8 h-8 text-ui-fg-disabled" />
              <Text size="small">Không tìm thấy cuộc trò chuyện nào.</Text>
            </div>
          ) : (
            filteredConversations.map(conv => {
              const statusMeta = getStatusMeta(conv.status)

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
                      fallback={conv.customer_id ? "C" : "G"}
                      variant="squared"
                      size="base"
                      className={conv.customer_id ? "bg-blue-100 text-blue-700 mt-1" : "bg-gray-200 text-gray-700 mt-1"}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start mb-1">
                        <Text size="small" weight="plus" className="truncate text-ui-fg-base max-w-[150px]">
                          {conv.customer_id ? `Khách (${conv.customer_id.substring(0, 8)})` : `Ẩn danh (${conv.guest_id?.substring(0, 8)})`}
                        </Text>
                        <div className="flex flex-col items-end">
                          <Text size="xsmall" className="text-ui-fg-muted shrink-0 mt-0.5">
                            {conv.last_message_at ? new Date(conv.last_message_at).toLocaleTimeString("vi-VN", { hour: '2-digit', minute: '2-digit' }) : ""}
                          </Text>
                          {/* Presence dot / last seen */}
                          <div className="text-[10px] text-ui-fg-muted mt-1">
                            {presenceMap[conv.id]?.online ? (
                              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-green-500" />Đang online</span>
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
                    </div>
                  </div>
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <ChatPanelErrorBoundary>
      <div className="flex-1 flex flex-col bg-ui-bg-subtle relative min-w-0">
        {activeConversation ? (
          <>
            <div className="h-[72px] px-6 border-b border-ui-border-base flex justify-between items-center bg-ui-bg-base shrink-0 z-10 shadow-sm">
              <div className="flex items-center gap-4">
                <Avatar
                  size="large"
                  fallback={activeConversation.customer_id ? "C" : "G"}
                  variant="squared"
                  className={activeConversation.customer_id ? "bg-blue-100 text-blue-700" : "bg-gray-200 text-gray-700"}
                />
                <div>
                  <div className="flex items-center gap-2">
                    <Heading level="h2" className="text-base m-0 leading-none">
                      {activeConversation.customer_id ? "Khách hàng đăng nhập" : "Khách hàng ẩn danh"}
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
                          <Text size="xsmall" className="text-ui-fg-muted">Đang online</Text>
                        </div>
                      ) : presenceMap[activeConversation.id]?.last_seen_at ? (
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-gray-400" />
                          <Text size="xsmall" className="text-ui-fg-muted">{formatLastSeen(presenceMap[activeConversation.id].last_seen_at)}</Text>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-gray-300" />
                          <Text size="xsmall" className="text-ui-fg-muted">Offline</Text>
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
                    Tiếp nhận hỗ trợ
                  </Button>
                )}
                {activeConversation.status === "IN_PROGRESS" && (
                  <>
                    <Button variant="secondary" size="small" onClick={() => updateStatus("BOT_HANDLED")}>
                      Giao lại cho Bot
                    </Button>
                    <Button variant="transparent" size="small" className="text-ui-fg-error hover:bg-ui-bg-error" onClick={() => updateStatus("CLOSED")}>
                      Đóng phiên
                    </Button>
                  </>
                )}
                {activeConversation.status === "BOT_HANDLED" && (
                  <Text size="small" className="text-ui-fg-muted self-center">Bot đang xử lý</Text>
                )}
                {activeConversation.status === "CLOSED" && (
                  <>
                    <Text size="small" className="text-ui-fg-muted self-center">Phiên đã đóng</Text>
                    <Button variant="secondary" size="small" onClick={() => updateStatus("IN_PROGRESS")}>
                      Nhận lại phiên
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
                    <Text>Chưa có tin nhắn nào</Text>
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
                                  <img src={img.url} alt={img.alt || "Chat image"} className="max-w-[320px] w-full h-auto max-h-[320px] object-cover" />
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
                              {isAdmin ? "Bạn" : isBot ? "Bot" : isCustomer ? "Khách hàng" : isGuest ? "Khách ẩn danh" : "Khách"}
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
                    placeholder="Gõ tin nhắn... (Shift + Enter để xuống dòng)"
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
                    {activeConversation.status === "BOT_HANDLED" && "Bot đang xử lý cuộc trò chuyện này."}
                    {activeConversation.status === "WAITING_ADMIN" && "Tiếp nhận hỗ trợ để bắt đầu trả lời khách."}
                    {activeConversation.status === "CLOSED" && "Phiên đã đóng."}
                    {activeConversation.status === "RESOLVED" && "Phiên đã đóng."}
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
            <Heading level="h1" className="text-xl mb-2 text-ui-fg-base">Chọn một cuộc trò chuyện</Heading>
            <Text className="max-w-xs text-center">Chọn một cuộc trò chuyện từ danh sách bên trái để bắt đầu chat với khách hàng.</Text>
          </div>
        )}
      </div>
      </ChatPanelErrorBoundary>
    </Container>
  )
}

const ChatIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
)

export const config = defineRouteConfig({
  label: "Live Chat",
  icon: ChatIcon,
})

export default ChatAdminPage
