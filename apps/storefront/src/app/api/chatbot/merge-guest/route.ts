import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}))
  const { guest_id, customer_id } = body
  const backendUrl = process.env.MEDUSA_BACKEND_URL || process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL || "http://localhost:9000"
  const cookieStore = await cookies()
  const customerToken = cookieStore.get("_medusa_jwt")?.value

  console.log("[MERGE_GUEST_PROXY_REQUEST]", {
    guest_id,
    customer_id,
    has_customer_token: Boolean(customerToken),
  })

  try {
    const response = await fetch(`${backendUrl}/store/chats/merge-guest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
        ...(customerToken ? { Authorization: `Bearer ${customerToken}` } : {}),
      },
      body: JSON.stringify({ guest_id, customer_id }),
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
