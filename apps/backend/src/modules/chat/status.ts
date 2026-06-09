export const CHAT_STATUSES = [
  "BOT_HANDLED",
  "WAITING_ADMIN",
  "IN_PROGRESS",
  "RESOLVED",
  "CLOSED",
] as const

export type ChatStatus = typeof CHAT_STATUSES[number]

export const ADMIN_VISIBLE_CHAT_STATUSES: ChatStatus[] = [
  "WAITING_ADMIN",
  "IN_PROGRESS",
]

export const ADMIN_INBOX_CHAT_STATUSES: ChatStatus[] = [
  "WAITING_ADMIN",
  "IN_PROGRESS",
  "CLOSED",
  "RESOLVED",
]

export const isAdminVisibleChatStatus = (status?: string | null) => {
  return ADMIN_VISIBLE_CHAT_STATUSES.includes(status as ChatStatus)
}

export const isAdminInboxChatStatus = (status?: string | null) => {
  return ADMIN_INBOX_CHAT_STATUSES.includes(status as ChatStatus)
}
