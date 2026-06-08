import { execFileSync } from "node:child_process"

const backendUrl = process.env.MEDUSA_BACKEND_URL || "http://localhost:9000"
const publishableKey =
  process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY ||
  "pk_0e7b15b6af66ec0cc488b8c17cdf2b0020ad203653949c239d686790d670f819"

const log = (step, payload = {}) => {
  console.log(`[chat:test-ai-first] ${step}`, JSON.stringify(payload, null, 2))
}

const postStoreMessage = async (payload) => {
  const response = await fetch(`${backendUrl}/store/chats/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-publishable-api-key": publishableKey,
    },
    body: JSON.stringify(payload),
  })
  const body = await response.json().catch(() => null)
  log("store-message-response", { ok: response.ok, status: response.status, body })
  if (!response.ok) {
    throw new Error(`Store message failed with ${response.status}`)
  }
  return body
}

const getAdminToken = async () => {
  if (process.env.ADMIN_TOKEN) {
    return process.env.ADMIN_TOKEN
  }

  const response = await fetch(`${backendUrl}/auth/user/emailpass`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: process.env.CHAT_TEST_ADMIN_EMAIL || "admin@ecomoi.local",
      password: process.env.CHAT_TEST_ADMIN_PASSWORD || "admin123",
    }),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok || !body?.token) {
    throw new Error("Admin token is required for Admin Inbox assertion. Set ADMIN_TOKEN.")
  }
  return body.token
}

const queryDb = (sql) => {
  return execFileSync(
    "docker",
    ["compose", "exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "ecomoi", "-c", sql],
    { encoding: "utf8" }
  )
}

const assert = (condition, message) => {
  if (!condition) {
    throw new Error(message)
  }
}

const main = async () => {
  const suffix = Date.now()

  const botGuestId = `guest_ai_bot_${suffix}`
  const botUser = await postStoreMessage({
    guest_id: botGuestId,
    sender_type: "guest",
    content: "iPhone 17 Pro Max giá bao nhiêu?",
  })
  const botConversationId = botUser.conversation.id
  await postStoreMessage({
    conversation_id: botConversationId,
    guest_id: botGuestId,
    sender_type: "bot",
    content: "iPhone 17 Pro Max hiện có giá từ 30.990.000đ.",
    conversation_status: "BOT_HANDLED",
    failed_response_count: 0,
    ai_confidence: 1,
  })

  const escalatedGuestId = `guest_ai_admin_${suffix}`
  const escalatedUser = await postStoreMessage({
    guest_id: escalatedGuestId,
    sender_type: "guest",
    content: "Tôi muốn hoàn tiền vì bị trừ tiền nhưng thanh toán thất bại.",
  })
  const escalatedConversationId = escalatedUser.conversation.id
  await postStoreMessage({
    conversation_id: escalatedConversationId,
    guest_id: escalatedGuestId,
    sender_type: "bot",
    content: "Mình sẽ chuyển trường hợp này sang nhân viên hỗ trợ.",
    conversation_status: "WAITING_ADMIN",
    escalation_reason: "refund_request",
    failed_response_count: 0,
    ai_confidence: 1,
  })

  const sql = `
select id, guest_id, status, escalation_reason, admin_metadata, escalated_at, created_at
from chat_conversation
where id in ('${botConversationId}', '${escalatedConversationId}')
order by created_at asc;
`
  log("db-query", { sql })
  const dbOutput = queryDb(sql)
  console.log(dbOutput)
  assert(dbOutput.includes("BOT_HANDLED"), "Expected BOT_HANDLED conversation in DB")
  assert(dbOutput.includes("WAITING_ADMIN"), "Expected WAITING_ADMIN conversation in DB")
  assert(dbOutput.includes("refund_request"), "Expected escalation reason in DB")

  const adminToken = await getAdminToken()
  const adminResponse = await fetch(`${backendUrl}/admin/chats`, {
    headers: {
      Authorization: `Bearer ${adminToken}`,
    },
  })
  const adminBody = await adminResponse.json()
  assert(adminResponse.ok, `Admin Inbox request failed with ${adminResponse.status}`)
  const adminConversationIds = (adminBody.conversations || []).map((conversation) => conversation.id)
  log("admin-inbox-check", {
    botConversationId,
    escalatedConversationId,
    adminConversationIds,
    stats: adminBody.stats,
  })
  assert(!adminConversationIds.includes(botConversationId), "BOT_HANDLED conversation must not appear in Admin Inbox")
  assert(adminConversationIds.includes(escalatedConversationId), "WAITING_ADMIN conversation must appear in Admin Inbox")
}

main().catch((error) => {
  console.error("[chat:test-ai-first] failed", error)
  process.exit(1)
})
