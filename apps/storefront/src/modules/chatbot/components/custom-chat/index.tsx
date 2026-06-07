"use client"

import { ChatBubbleLeftRight, PaperPlane, XMark } from "@medusajs/icons"
import clsx from "clsx"
import { FormEvent, useEffect, useMemo, useRef, useState } from "react"

type ProductCard = {
  title?: string
  url?: string
  image?: string | null
  price_from?: string
  discount?: string
}

type BotMessage = {
  id: string
  role: "bot" | "user"
  text: string
  payload?: {
    product?: ProductCard
    products?: ProductCard[]
  }
}

type ApiMessage = {
  text?: string
  payload?: BotMessage["payload"]
}

const initialMessages: BotMessage[] = [
  {
    id: "welcome",
    role: "bot",
    text: "Chào bạn, mình có thể hỗ trợ tìm sản phẩm, xem giá, gợi ý đồ mặc và kiểm tra đơn hàng khi bạn đã đăng nhập.",
  },
]

const suggestedQuestions = [
  "Áo hoodie giá bao nhiêu?",
  "Gợi ý đồ mặc mùa đông",
  "Top 5 sản phẩm giá cao nhất",
  "Tôi có đặt đơn nào không?",
]

const cleanBotText = (text: string) => {
  return text
    .split("\n")
    .filter((line) => !line.trim().startsWith("!["))
    .map((line) =>
      line
        .replace(/^#{1,6}\s*/, "")
        .replace(/\*\*(.*?)\*\*/g, "$1")
        .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
        .replace(/^\s*\*\s+/g, "- ")
    )
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

const getSessionId = () => {
  const key = "medusa_chatbot_session_id"
  const existing = window.localStorage.getItem(key)
  if (existing) {
    return existing
  }

  const next = crypto.randomUUID()
  window.localStorage.setItem(key, next)
  return next
}

const ProductCards = ({ payload }: { payload?: BotMessage["payload"] }) => {
  const products = payload?.products || (payload?.product ? [payload.product] : [])

  if (!products.length) {
    return null
  }

  return (
    <div className="mt-3 grid gap-2">
      {products.map((product, index) => (
        <a
          key={`${product.url || product.title || "product"}-${index}`}
          href={product.url || "#"}
          className="flex min-h-[84px] gap-3 rounded-md border border-gray-200 bg-white p-2 transition hover:border-gray-400"
        >
          {product.image ? (
            <img
              src={product.image}
              alt={product.title || "Product image"}
              className="h-20 w-16 flex-none rounded-sm object-cover"
            />
          ) : (
            <div className="h-20 w-16 flex-none rounded-sm bg-gray-100" />
          )}
          <div className="min-w-0 flex-1">
            <p className="line-clamp-2 text-sm font-semibold text-gray-900">
              {product.title || "Sản phẩm"}
            </p>
            <p className="mt-1 text-sm text-gray-700">
              {product.price_from || "Chưa cập nhật giá"}
            </p>
            {product.discount ? (
              <p className="mt-1 line-clamp-2 text-xs text-gray-500">
                {product.discount}
              </p>
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
        "flex",
        message.role === "user" ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={clsx(
          "max-w-[88%] whitespace-pre-line rounded-lg px-3 py-2 text-sm leading-5",
          message.role === "user"
            ? "bg-gray-900 text-white"
            : "border border-gray-200 bg-gray-50 text-gray-900"
        )}
      >
        {message.text}
        {message.role === "bot" ? <ProductCards payload={message.payload} /> : null}
      </div>
    </div>
  )
}

const CustomChat = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<BotMessage[]>(initialMessages)
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const sessionId = useMemo(
    () => (typeof window === "undefined" ? "" : getSessionId()),
    []
  )

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages, isOpen])

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) {
      return
    }

    setInput("")
    setIsLoading(true)
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: "user",
        text: trimmed,
      },
    ])

    try {
      const response = await fetch("/api/chatbot", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: trimmed,
          sessionId,
        }),
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data?.error || "Chatbot request failed")
      }

      const botMessages = (data.messages || []).map(
        (item: ApiMessage): BotMessage => ({
          id: crypto.randomUUID(),
          role: "bot",
          text: cleanBotText(item.text || "Mình chưa có phản hồi phù hợp."),
          payload: item.payload,
        })
      )

      setMessages((current) => [...current, ...botMessages])
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
        <section className="flex h-[min(640px,calc(100vh-48px))] w-[min(420px,calc(100vw-32px))] flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-2xl">
          <header className="flex h-14 items-center justify-between border-b border-gray-200 px-4">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-gray-900 text-white">
                <ChatBubbleLeftRight />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900">Bot Medusa</p>
                <p className="text-xs text-gray-500">AI customer support</p>
              </div>
            </div>
            <button
              aria-label="Đóng chat"
              className="flex h-9 w-9 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-900"
              type="button"
              onClick={() => setIsOpen(false)}
            >
              <XMark />
            </button>
          </header>

          <div className="flex-1 overflow-y-auto bg-white px-4 py-4">
            <div className="grid gap-3">
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              {isLoading ? (
                <div className="flex justify-start">
                  <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500">
                    Đang xử lý...
                  </div>
                </div>
              ) : null}
              <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="border-t border-gray-200 bg-white p-3">
            <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
              {suggestedQuestions.map((question) => (
                <button
                  key={question}
                  className="h-8 flex-none rounded-md border border-gray-200 px-3 text-xs text-gray-700 hover:border-gray-400"
                  type="button"
                  onClick={() => sendMessage(question)}
                >
                  {question}
                </button>
              ))}
            </div>
            <form className="flex gap-2" onSubmit={onSubmit}>
              <input
                className="h-10 min-w-0 flex-1 rounded-md border border-gray-300 px-3 text-sm outline-none focus:border-gray-900"
                placeholder="Nhập câu hỏi..."
                value={input}
                onChange={(event) => setInput(event.target.value)}
              />
              <button
                aria-label="Gửi tin nhắn"
                className="flex h-10 w-10 flex-none items-center justify-center rounded-md bg-gray-900 text-white disabled:cursor-not-allowed disabled:bg-gray-300"
                type="submit"
                disabled={!input.trim() || isLoading}
              >
                <PaperPlane />
              </button>
            </form>
          </div>
        </section>
      ) : (
        <button
          aria-label="Mở chat"
          className="flex h-14 w-14 items-center justify-center rounded-full bg-gray-900 text-white shadow-xl transition hover:bg-gray-700"
          type="button"
          onClick={() => setIsOpen(true)}
        >
          <ChatBubbleLeftRight />
        </button>
      )}
    </div>
  )
}

export default CustomChat
