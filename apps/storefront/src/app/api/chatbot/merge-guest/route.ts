import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}))
  const guestIdFromBody = body.guest_id
  const customerIdFromBody = body.customer_id
  const backendUrl = process.env.MEDUSA_BACKEND_URL || process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL || "http://localhost:9000"
  const cookieStore = await cookies()
  const requestAuthHeader = request.headers.get("authorization")
  const customerToken = cookieStore.get("_medusa_jwt")?.value || requestAuthHeader?.replace(/^Bearer\s+/i, "")
  const guestIdFromCookie = cookieStore.get("chat_guest_id")?.value
  const guest_id = guestIdFromBody || guestIdFromCookie

  console.log("[MERGE_GUEST_PROXY_REQUEST]", {
    guest_id: guest_id || null,
    customer_id: customerIdFromBody || null,
    has_customer_token: Boolean(customerToken),
  })

  if (!guest_id) {
    return NextResponse.json({ success: true, count: 0, skipped: "missing_guest_id" })
  }

  try {
    const response = await fetch(`${backendUrl}/store/chats/merge-guest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
        ...(customerToken ? { Authorization: `Bearer ${customerToken}` } : {}),
      },
      body: JSON.stringify({ guest_id, customer_id: customerIdFromBody }),
    })

    const data = await response.json().catch(() => null)

    console.log("[MERGE_GUEST_PROXY_RESPONSE]", {
      ok: response.ok,
      status: response.status,
      data,
    })

    return NextResponse.json(data, { status: response.status })
  } catch (err) {
    console.error("[MERGE_GUEST_PROXY_ERROR]", err)
    return NextResponse.json(
      { error: "Internal Server Error", detail: err instanceof Error ? err.message : String(err) },
      { status: 500 }
    )
  }
}
