"use client"

import { ChatBubbleLeftRight, PaperPlane, XMark } from "@medusajs/icons"
import clsx from "clsx"
import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react"

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
    text: "Chào bạn, mình có thể hỗ trợ tìm sản phẩm, xem giá điện thoại, so sánh và kiểm tra đơn hàng khi bạn đã đăng nhập.",
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
          <strong key={matchIndex} className="font-bold text-gray-900">
            {match[1]}
          </strong>
        )
      } else if (match[2] !== undefined) {
        parts.push(
          <a
            key={matchIndex}
            href={match[3]}
            className="font-semibold text-indigo-600 transition hover:text-indigo-800 hover:underline"
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
        <div key={key} className="my-2.5 overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm transition duration-300 hover:shadow-md">
          <img
            src={imgMatch[2]}
            alt={imgMatch[1]}
            className="w-full max-h-48 object-cover transition duration-500 hover:scale-105"
          />
          {imgMatch[1] && (
            <p className="border-t border-gray-50 bg-gray-50/50 p-2 text-center text-xs italic text-gray-500">
              {imgMatch[1]}
            </p>
          )}
        </div>
      )
    }

    // Headings
    if (line.startsWith("### ")) {
      return (
        <h4 key={key} className="mt-3.5 mb-1 text-sm font-bold text-gray-900 border-l-2 border-indigo-500 pl-2">
          {parseInline(line.slice(4))}
        </h4>
      )
    }
    if (line.startsWith("## ")) {
      return (
        <h3 key={key} className="mt-4 mb-2 text-base font-bold text-gray-900 border-l-2 border-indigo-500 pl-2">
          {parseInline(line.slice(3))}
        </h3>
      )
    }
    if (line.startsWith("# ")) {
      return (
        <h2 key={key} className="mt-4 mb-2 text-lg font-bold text-gray-950 border-l-2 border-indigo-500 pl-2">
          {parseInline(line.slice(2))}
        </h2>
      )
    }

    // List items
    if (line.startsWith("- ") || line.startsWith("* ")) {
      return (
        <li key={key} className="ml-3 list-disc text-xs text-gray-700 my-0.5">
          {parseInline(line.slice(2))}
        </li>
      )
    }

    return (
      <p key={key} className="text-xs text-gray-700 leading-relaxed my-0.5">
        {parseInline(line)}
      </p>
    )
  }

  const renderTable = (tableData: string[][], key: string | number) => {
    if (!tableData.length) return null
    return (
      <div key={key} className="my-3 overflow-hidden rounded-xl border border-gray-150 shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-[11px]">
            <thead>
              <tr className="bg-gray-100 border-b border-gray-200">
                {tableData[0].map((cell, idx) => (
                  <th key={idx} className="p-2 font-semibold text-gray-900 whitespace-nowrap">
                    {parseInline(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-150">
              {tableData.slice(1).map((row, rIdx) => (
                <tr key={rIdx} className={clsx(rIdx % 2 === 0 ? "bg-white" : "bg-gray-50/30", "hover:bg-gray-50")}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="p-2 text-gray-700">
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
          className="group flex gap-3 rounded-xl border border-gray-100 bg-gray-50/50 p-2.5 transition duration-200 hover:border-indigo-400 hover:bg-indigo-50/20"
        >
          {product.image ? (
            <div className="h-16 w-16 flex-none overflow-hidden rounded-lg border border-gray-100 bg-white">
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
            <p className="line-clamp-1 text-xs font-semibold text-gray-900 group-hover:text-indigo-600 transition">
              {product.title || "Sản phẩm"}
            </p>
            <p className="mt-0.5 text-xs font-bold text-indigo-600">
              {product.price_from || "Chưa cập nhật giá"}
            </p>
            {product.discount ? (
              <span className="mt-1 self-start rounded bg-rose-50 px-1.5 py-0.5 text-[9px] font-medium text-rose-600">
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
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm transition-all duration-200",
          message.role === "user"
            ? "bg-gradient-to-br from-indigo-600 to-violet-750 text-white rounded-br-none shadow-indigo-100"
            : "border border-gray-150 bg-white text-gray-800 rounded-bl-none shadow-slate-100"
        )}
      >
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
        <section className="flex h-[min(660px,calc(100vh-48px))] w-[min(430px,calc(100vw-32px))] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white/95 backdrop-blur-sm shadow-[0_20px_50px_rgba(0,0,0,0.15)] transition-all duration-300">
          <header className="flex h-16 items-center justify-between border-b border-gray-100 bg-gradient-to-r from-gray-900 via-slate-800 to-gray-900 px-4 text-white">
            <div className="flex items-center gap-2.5">
              <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-white backdrop-blur-sm">
                <ChatBubbleLeftRight className="h-5 w-5 animate-pulse" />
                <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-gray-900 bg-emerald-500" />
              </div>
              <div>
                <p className="text-sm font-semibold tracking-wide">Trợ lý Medusa</p>
                <p className="text-[10px] text-gray-300">Online | AI Support</p>
              </div>
            </div>
            <button
              aria-label="Đóng chat"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-300 hover:bg-white/10 hover:text-white transition duration-200"
              type="button"
              onClick={() => setIsOpen(false)}
            >
              <XMark className="h-5 w-5" />
            </button>
          </header>

          <div className="flex-1 overflow-y-auto bg-gray-50/50 px-4 py-4">
            <div className="grid gap-4">
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              {isLoading ? (
                <div className="flex justify-start">
                  <div className="flex items-center gap-2 rounded-xl border border-gray-100 bg-white px-4 py-2.5 text-[11px] text-gray-500 shadow-sm">
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

          <div className="border-t border-gray-150 bg-white p-4">
            <div className="mb-3 flex gap-2 overflow-x-auto pb-2">
              {suggestedQuestions.map((question) => (
                <button
                  key={question}
                  className="h-8 flex-none rounded-full border border-gray-200 bg-gray-50 px-3.5 text-xs font-medium text-gray-600 transition duration-200 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-600 active:scale-95"
                  type="button"
                  onClick={() => sendMessage(question)}
                >
                  {question}
                </button>
              ))}
            </div>
            <form className="flex gap-2.5" onSubmit={onSubmit}>
              <input
                className="h-10 min-w-0 flex-1 rounded-full border border-gray-200 bg-gray-50 px-4 text-xs text-gray-800 outline-none transition duration-200 focus:border-indigo-500 focus:bg-white focus:ring-2 focus:ring-indigo-100"
                placeholder="Nhập câu hỏi cho trợ lý..."
                value={input}
                onChange={(event) => setInput(event.target.value)}
              />
              <button
                aria-label="Gửi tin nhắn"
                className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-650 text-white shadow-md shadow-indigo-100 transition duration-200 hover:shadow-lg hover:shadow-indigo-200 hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:bg-gray-250 disabled:from-gray-300 disabled:to-gray-300 disabled:shadow-none"
                type="submit"
                disabled={!input.trim() || isLoading}
              >
                <PaperPlane className="h-4 w-4" />
              </button>
            </form>
          </div>
        </section>
      ) : (
        <button
          aria-label="Mở chat"
          className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-gray-900 via-slate-800 to-gray-900 text-white shadow-xl transition-all duration-300 hover:scale-110 hover:shadow-2xl hover:shadow-slate-350 active:scale-95 relative group"
          type="button"
          onClick={() => setIsOpen(true)}
        >
          <ChatBubbleLeftRight className="h-6 w-6 transition group-hover:rotate-6" />
          <span className="absolute -top-1 -right-1 flex h-4 w-4">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-4 w-4 bg-indigo-500 text-[9px] font-bold text-white items-center justify-center">1</span>
          </span>
        </button>
      )}
    </div>
  )
}

export default CustomChat
