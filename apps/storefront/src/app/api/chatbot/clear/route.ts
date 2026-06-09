import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}))
  const guestId = body.guest_id || null
  const backendUrl = process.env.MEDUSA_BACKEND_URL || process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL || "http://localhost:9000"
  const cookieStore = await cookies()
  const customerToken = cookieStore.get("_medusa_jwt")?.value

  console.log("[CLEAR_CHAT_PROXY_REQUEST]", {
    guest_id: guestId,
    has_customer_token: Boolean(customerToken),
  })

  try {
    const response = await fetch(`${backendUrl}/store/chats/clear`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
        ...(customerToken ? { Authorization: `Bearer ${customerToken}` } : {}),
      },
      body: JSON.stringify({ guest_id: guestId }),
    })

    const data = await response.json().catch(() => null)

    console.log("[CLEAR_CHAT_PROXY_RESPONSE]", {
      ok: response.ok,
      status: response.status,
      data,
    })

    return NextResponse.json(data, { status: response.status })
  } catch (err) {
    console.error("[CLEAR_CHAT_PROXY_ERROR]", err)
    return NextResponse.json(
      { error: "Internal Server Error", detail: err instanceof Error ? err.message : String(err) },
      { status: 500 }
    )
  }
}
