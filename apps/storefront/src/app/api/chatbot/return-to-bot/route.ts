import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}))
  const conversationId = typeof body.conversationId === "string" ? body.conversationId : ""
  const guestId = typeof body.guestId === "string" ? body.guestId : null

  if (!conversationId) {
    return NextResponse.json({ error: "conversationId is required" }, { status: 400 })
  }

  const backendUrl = process.env.MEDUSA_BACKEND_URL || process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL || "http://localhost:9000"
  const cookieStore = await cookies()
  const customerToken = cookieStore.get("_medusa_jwt")?.value

  const response = await fetch(`${backendUrl}/store/chats/${conversationId}/return-to-bot`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
      ...(customerToken ? { "Authorization": `Bearer ${customerToken}` } : {}),
    },
    body: JSON.stringify({ guest_id: guestId }),
  })

  const data = await response.json().catch(() => null)
  return NextResponse.json(data || {}, { status: response.status })
}
