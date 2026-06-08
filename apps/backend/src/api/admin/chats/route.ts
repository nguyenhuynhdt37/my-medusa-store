import { MedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { CHAT_MODULE } from "../../../modules/chat"
import { ADMIN_VISIBLE_CHAT_STATUSES } from "../../../modules/chat/status"

export const GET = async (
  req: MedusaRequest,
  res: MedusaResponse
) => {
  const chatModuleService = req.scope.resolve(CHAT_MODULE)
  
  // Basic filtering / pagination can be added here
  const limit = parseInt((req.query.limit as string) || "50", 10)
  const offset = parseInt((req.query.offset as string) || "0", 10)
  const status = req.query.status as string

  const allConversations = await chatModuleService.listChatConversations(
    {},
    {
      order: { updated_at: "DESC" },
    }
  )

  const visibleConversations = allConversations.filter((conversation) => {
    if (status) {
      return conversation.status === status
    }

    return ADMIN_VISIBLE_CHAT_STATUSES.includes(conversation.status)
  })
  const conversations = visibleConversations.slice(offset, offset + limit)
  const stats = buildChatStats(allConversations)

  return res.json({
    conversations,
    count: visibleConversations.length,
    limit,
    offset,
    stats,
  })
}

const minutesBetween = (start?: string | Date | null, end?: string | Date | null) => {
  if (!start || !end) {
    return null
  }

  const startMs = new Date(start).getTime()
  const endMs = new Date(end).getTime()

  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs < startMs) {
    return null
  }

  return Math.round((endMs - startMs) / 60000)
}

const average = (values: Array<number | null>) => {
  const validValues = values.filter((value): value is number => typeof value === "number")
  if (!validValues.length) {
    return null
  }

  return Math.round(validValues.reduce((sum, value) => sum + value, 0) / validValues.length)
}

const buildChatStats = (conversations: any[]) => {
  const totalConversations = conversations.length
  const aiHandledConversations = conversations.filter((conversation) => conversation.status === "BOT_HANDLED").length
  const escalatedConversations = conversations.filter((conversation) =>
    ["WAITING_ADMIN", "IN_PROGRESS", "RESOLVED", "CLOSED"].includes(conversation.status)
  ).length

  return {
    total_conversations: totalConversations,
    ai_handled_conversations: aiHandledConversations,
    escalated_conversations: escalatedConversations,
    ai_resolution_rate: totalConversations ? Math.round((aiHandledConversations / totalConversations) * 100) : 0,
    average_escalation_time_minutes: average(
      conversations.map((conversation) => minutesBetween(conversation.created_at, conversation.escalated_at))
    ),
    human_resolution_time_minutes: average(
      conversations.map((conversation) => minutesBetween(conversation.admin_started_at || conversation.escalated_at, conversation.resolved_at || conversation.closed_at))
    ),
  }
}
