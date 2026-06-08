import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const guestId = searchParams.get("guest_id") || ""
  const conversationId = searchParams.get("conversation_id") || ""
  const backendUrl = process.env.MEDUSA_BACKEND_URL || process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL || "http://localhost:9000"
  const cookieStore = await cookies()
  const customerToken = cookieStore.get("_medusa_jwt")?.value

  console.log("[HISTORY_PROXY_REQUEST]", {
    guest_id: guestId || null,
    conversation_id: conversationId || null,
    has_customer_token: Boolean(customerToken),
  })

  const params = new URLSearchParams()
  if (guestId) {
    params.set("guest_id", guestId)
  }
  if (conversationId) {
    params.set("conversation_id", conversationId)
  }

  const response = await fetch(`${backendUrl}/store/chats/history?${params.toString()}`, {
    headers: {
      "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
      ...(customerToken ? { Authorization: `Bearer ${customerToken}` } : {}),
    },
  })

  const data = await response.json().catch(() => null)

  console.log("[HISTORY_PROXY_RESPONSE]", {
    ok: response.ok,
    status: response.status,
    conversation_id: data?.conversation?.id || null,
    message_count: data?.messages?.length || 0,
  })

  return NextResponse.json(data, { status: response.status })
}
