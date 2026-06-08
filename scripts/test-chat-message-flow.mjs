import { execFileSync } from "node:child_process"

const backendUrl = process.env.MEDUSA_BACKEND_URL || "http://localhost:9000"
const publishableKey =
  process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY ||
  "pk_0e7b15b6af66ec0cc488b8c17cdf2b0020ad203653949c239d686790d670f819"
const guestId = process.env.CHAT_TEST_GUEST_ID || `guest_flow_test_${Date.now()}`
const content = process.env.CHAT_TEST_CONTENT || `chat flow test ${new Date().toISOString()}`

const log = (step, payload = {}) => {
  console.log(`[chat:test-flow] ${step}`, JSON.stringify(payload, null, 2))
}

const postJson = async (url, payload, headers = {}) => {
  log("request", { url, payload })
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-publishable-api-key": publishableKey,
      ...headers,
    },
    body: JSON.stringify(payload),
  })
  const body = await response.json().catch(() => null)
  log("response", { ok: response.ok, status: response.status, body })

  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`)
  }

  return body
}

const queryDb = (sql) => {
  return execFileSync(
    "docker",
    ["compose", "exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "ecomoi", "-c", sql],
    { encoding: "utf8" }
  )
}

const main = async () => {
  const first = await postJson(`${backendUrl}/store/chats/messages`, {
    guest_id: guestId,
    sender_type: "guest",
    content,
  })

  const messageId = first.message.id
  const conversationId = first.conversation.id
  log("insert-result", {
    message_id: messageId,
    conversation_id: conversationId,
    sender_type: first.message.sender_type,
    content: first.message.content,
    created_at: first.message.created_at,
  })

  const sql = `
select
  m.id,
  m.conversation_id,
  c.guest_id,
  c.customer_id,
  m.sender_type,
  m.content,
  m.created_at
from chat_message m
join chat_conversation c on c.id = m.conversation_id
where m.id = '${messageId}'
  and m.deleted_at is null;
`
  log("db-query", { sql })
  console.log(queryDb(sql))

  if (process.env.ADMIN_TOKEN) {
    const admin = await postJson(
      `${backendUrl}/admin/chats/${conversationId}/messages`,
      { content: `${content} admin reply` },
      { Authorization: `Bearer ${process.env.ADMIN_TOKEN}` }
    )
    log("admin-insert-result", {
      message_id: admin.message.id,
      conversation_id: conversationId,
      sender_type: admin.message.sender_type,
      content: admin.message.content,
      created_at: admin.message.created_at,
    })
    console.log(queryDb(`select id, conversation_id, sender_type, content, created_at from chat_message where id = '${admin.message.id}';`))
  } else {
    log("admin-skip", { reason: "Set ADMIN_TOKEN to test admin message persistence." })
  }

  if (process.env.CUSTOMER_TOKEN) {
    const customer = await postJson(
      `${backendUrl}/store/chats/messages`,
      {
        conversation_id: conversationId,
        guest_id: guestId,
        sender_type: "customer",
        content: `${content} customer auth`,
      },
      { Authorization: `Bearer ${process.env.CUSTOMER_TOKEN}` }
    )
    log("customer-insert-result", {
      message_id: customer.message.id,
      conversation_id: customer.conversation.id,
      sender_type: customer.message.sender_type,
      content: customer.message.content,
      created_at: customer.message.created_at,
    })
    console.log(queryDb(`select id, conversation_id, sender_type, content, created_at from chat_message where id = '${customer.message.id}';`))
  } else {
    log("customer-skip", { reason: "Set CUSTOMER_TOKEN to test authenticated customer persistence." })
  }
}

main().catch((error) => {
  console.error("[chat:test-flow] failed", error)
  process.exit(1)
})
