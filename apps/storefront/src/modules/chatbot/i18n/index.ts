const translations = {
  chat: {
    welcome: "Chào bạn, mình có thể hỗ trợ tìm sản phẩm, xem giá điện thoại, so sánh và kiểm tra đơn hàng khi bạn đã đăng nhập.",
    suggestedQuestions: [
      "iPhone 17 Pro Max giá bao nhiêu?",
      "So sánh iPhone 15 và Samsung S26 Plus",
      "Top 5 sản phẩm giá cao nhất",
      "Tôi có đặt đơn nào không?",
    ],
    header: {
      title: "Trợ lý Medusa",
      connected: "Đã kết nối",
      connecting: "Đang kết nối...",
      disconnected: "Mất kết nối",
      agentOnline: "Agent online",
      aiSupport: "Online | AI Support",
      agentLastSeen: "Agent {{time}}",
    },
    aria: {
      clearHistory: "Xóa lịch sử chat",
      closeChat: "Đóng chat",
      openChat: "Mở chat",
      sendMessage: "Gửi tin nhắn",
    },
    loading: {
      history: "Đang tải lịch sử...",
      thinking: "Đang suy nghĩ...",
    },
    input: {
      placeholder: "Nhập câu hỏi cho trợ lý...",
    },
    confirm: {
      clearHistory: "Bạn có chắc chắn muốn xóa toàn bộ lịch sử trò chuyện này không?",
    },
    errors: {
      clearFailed: "Failed to clear chat",
      loadHistoryFailed: "Failed to load history",
      wsParseFailed: "Failed to parse WS message",
      connectionError: "Mình đang gặp lỗi kết nối. Bạn thử lại sau nhé.",
      noResponse: "Mình chưa có phản hồi phù hợp.",
    },
    notifications: {
      baseTitle: "Medusan Chat",
      notificationTitle: "Medusan",
      senderAdmin: "Admin",
      senderBot: "Bot",
    },
    product: {
      imageAlt: "Hình ảnh sản phẩm",
      defaultTitle: "Sản phẩm",
      noPrice: "Chưa cập nhật giá",
    },
    adminLabel: "NV Hỗ trợ",
    presence: {
      justNow: "vừa xong",
      minutesAgo: "cách {{count}} phút",
      hoursAgo: "cách {{count}} giờ",
      daysAgo: "cách {{count}} ngày",
    },
  },
}

export const storefrontTranslations = translations

export function t(key: string, params?: Record<string, string | number>): string {
  const keys = key.split(".")
  let value: unknown = storefrontTranslations

  for (const k of keys) {
    if (value && typeof value === "object" && k in value) {
      value = (value as Record<string, unknown>)[k]
    } else {
      return key
    }
  }

  if (typeof value !== "string") {
    return key
  }

  if (params) {
    return value.replace(/\{\{(\w+)\}\}/g, (_, k) => String(params[k] ?? `{{${k}}}`))
  }

  return value
}

export function formatPresence(iso: string | null | undefined): string {
  if (!iso) return ""
  const then = new Date(iso).getTime()
  const delta = Math.floor((Date.now() - then) / 1000)
  if (delta < 60) return t("chat.presence.justNow")
  if (delta < 3600) return t("chat.presence.minutesAgo", { count: Math.floor(delta / 60) })
  if (delta < 86400) return t("chat.presence.hoursAgo", { count: Math.floor(delta / 3600) })
  return t("chat.presence.daysAgo", { count: Math.floor(delta / 86400) })
}
