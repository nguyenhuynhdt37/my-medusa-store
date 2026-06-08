import { Container, Heading, Text, Button, Badge, Input, Avatar, DropdownMenu } from "@medusajs/ui"
import { toast } from "@medusajs/ui"
import { defineRouteConfig } from "@medusajs/admin-sdk"
import { useEffect, useState, useRef } from "react"
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

const createIcon = (content: JSX.Element | JSX.Element[]) => ({ className }: IconProps) => (
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

const sortMessagesByCreatedAt = (items: ChatMessage[]) => {
  return [...items].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  )
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
  const [statusFilter, setStatusFilter] = useState<"all" | "WAITING_ADMIN" | "IN_PROGRESS" | "RESOLVED">("all")
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
    let result = conversations
    if (searchQuery) {
      result = result.filter(c =>
        (c.customer_id && c.customer_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (c.guest_id && c.guest_id.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    }
    if (statusFilter !== "all") {
      result = result.filter(c => c.status === statusFilter)
    }
    setFilteredConversations(result)
  }, [conversations, searchQuery, statusFilter])

  useEffect(() => {
    if (activeConversation) {
      setMessages([])
      fetchMessages(activeConversation.id)
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
      setConversations(data.conversations || [])
      setStats(data.stats || null)
    } catch (err) {
      toast({ title: "Lỗi", description: "Không thể tải danh sách chat", variant: "error" })
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
      toast({ title: "Lỗi", description: "Không thể tải tin nhắn", variant: "error" })
    }
  }

  const sendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!input.trim() || !activeConversation) return

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
      toast({ title: "Lỗi", description: "Gửi tin nhắn thất bại", variant: "error" })
    }
  }

  const updateStatus = async (status: "WAITING_ADMIN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED" | "BOT_HANDLED") => {
    if (!activeConversation) return
    const endpoint =
      status === "WAITING_ADMIN"
        ? "handover"
        : status === "IN_PROGRESS"
          ? "assign"
          : status === "RESOLVED"
            ? "resolve"
            : status === "BOT_HANDLED"
              ? "bot"
              : "close"

    try {
      await fetch(`/admin/chats/${activeConversation.id}/${endpoint}`, { method: "POST" })
      setActiveConversation({ ...activeConversation, status })
      toast({ title: "Thành công", description: "Cập nhật trạng thái thành công" })
      fetchConversations(false)
    } catch (err) {
      toast({ title: "Lỗi", description: "Không thể cập nhật", variant: "error" })
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
                color="blue"
                className={`cursor-pointer whitespace-nowrap transition-colors ${statusFilter === 'WAITING_ADMIN' ? 'bg-blue-600 text-white hover:bg-blue-700' : ''}`}
                onClick={() => setStatusFilter('WAITING_ADMIN')}
              >
                Chờ admin
              </Badge>
              <Badge
                color="orange"
                className={`cursor-pointer whitespace-nowrap transition-colors ${statusFilter === 'IN_PROGRESS' ? 'bg-orange-600 text-white hover:bg-orange-700' : ''}`}
                onClick={() => setStatusFilter('IN_PROGRESS')}
              >
                Đang xử lý
              </Badge>
              <Badge
                color="grey"
                className={`cursor-pointer whitespace-nowrap transition-colors ${statusFilter === 'RESOLVED' ? 'bg-gray-600 text-white hover:bg-gray-700' : ''}`}
                onClick={() => setStatusFilter('RESOLVED')}
              >
                Đã xử lý
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
            filteredConversations.map(conv => (
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
                      <Badge size="small" color={conv.status === "WAITING_ADMIN" ? "blue" : conv.status === "IN_PROGRESS" ? "orange" : "grey"}>
                        {conv.status === "WAITING_ADMIN" ? "Chờ admin" : conv.status === "IN_PROGRESS" ? "Đang xử lý" : "Đã xử lý"}
                      </Badge>
                      {Number(conv.admin_metadata?.unread_admin_count || 0) > 0 && (
                        <Badge size="small" color="red">{conv.admin_metadata?.unread_admin_count}</Badge>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Area */}
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
                  <Button variant="secondary" size="small" onClick={() => updateStatus("IN_PROGRESS")}>
                    Nhận hỗ trợ
                  </Button>
                )}
                {activeConversation.status === "IN_PROGRESS" && (
                  <Button variant="secondary" size="small" onClick={() => updateStatus("BOT_HANDLED")}>
                    Giao cho Bot
                  </Button>
                )}
                {activeConversation.status !== "RESOLVED" && activeConversation.status !== "CLOSED" && (
                  <Button variant="secondary" size="small" onClick={() => updateStatus("RESOLVED")}>
                    Đã xử lý
                  </Button>
                )}
                {activeConversation.status !== "CLOSED" && (
                  <Button variant="transparent" size="small" className="text-ui-fg-error hover:bg-ui-bg-error" onClick={() => updateStatus("CLOSED")}>
                    Đóng phiên
                  </Button>
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
                    let cleanText = msg.content.replace(markdownImgRegex, (match, alt, url) => {
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
                                  h1: ({ node, ...props }) => <h1 className="text-lg font-bold mt-3 mb-2" {...props} />,
                                  h2: ({ node, ...props }) => <h2 className="text-base font-bold mt-2 mb-1" {...props} />,
                                  h3: ({ node, ...props }) => <h3 className="text-sm font-bold mt-2 mb-1" {...props} />,
                                  p: ({ node, ...props }) => <p className="mb-2 last:mb-0 leading-relaxed" {...props} />,
                                  ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />,
                                  ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />,
                                  li: ({ node, ...props }) => <li className="mb-1" {...props} />,
                                  a: ({ node, ...props }) => <a className="text-blue-500 hover:underline break-all" target="_blank" rel="noopener noreferrer" {...props} />,
                                  strong: ({ node, ...props }) => <strong className="font-semibold" {...props} />,
                                  code: ({ node, ...props }) => <code className="bg-black/10 dark:bg-white/10 rounded px-1 py-0.5 text-[13px]" {...props} />,
                                  pre: ({ node, ...props }) => <pre className="bg-black/10 dark:bg-white/10 rounded-lg p-3 overflow-x-auto my-2 text-[13px]" {...props} />
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
              {activeConversation.status !== "CLOSED" && activeConversation.status !== "RESOLVED" ? (
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
                    Phiên hội thoại này đã bị đóng.
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
            <Heading level="h1" className="text-xl mb-2 text-ui-fg-base">Trung tâm hỗ trợ</Heading>
            <Text className="max-w-xs text-center">Chọn một cuộc hội thoại từ danh sách bên trái để bắt đầu chat với khách hàng.</Text>
          </div>
        )}
      </div>
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
