import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

const LOG_PREFIX = "[chat:storefront:api]"

type ChatbotRequest = {
  message?: string
  guestId?: string
  conversationId?: string | null
}

const sanitize = (value?: string | null, max = 128) =>
  value?.replace(/[^a-zA-Z0-9_-]/g, "").slice(0, max) || null

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as ChatbotRequest
  const message = body.message?.trim()

  if (!message) {
    console.error(`${LOG_PREFIX} missing message`)
    return NextResponse.json({ error: "Message is required." }, { status: 400 })
  }

  const medusaBackendUrl =
    process.env.MEDUSA_BACKEND_URL ||
    process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL ||
    "http://localhost:9000"
  const publishableKey = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY
  const cookieStore = await cookies()
  const customerToken = cookieStore.get("_medusa_jwt")?.value
  const cartId = cookieStore.get("_medusa_cart_id")?.value
  const guestId =
    sanitize(body.guestId, 128) ||
    sanitize(cookieStore.get("chat_guest_id")?.value, 128) ||
    `guest_${crypto.randomUUID()}`
  const conversationId = sanitize(body.conversationId, 128)

  console.info(`${LOG_PREFIX} proxying to Medusa chat process`, {
    backend_url: medusaBackendUrl,
    guest_id: guestId,
    conversation_id: conversationId,
    has_customer_token: Boolean(customerToken),
    content_length: message.length,
  })

  try {
    const response = await fetch(`${medusaBackendUrl}/store/chats/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(publishableKey ? { "x-publishable-api-key": publishableKey } : {}),
        ...(customerToken ? { Authorization: `Bearer ${customerToken}` } : {}),
      },
      body: JSON.stringify({
        message,
        guest_id: guestId,
        conversation_id: conversationId,
        cart_id: cartId || null,
        channel: "WEB",
      }),
    })

    const data = await response.json().catch(() => null)

    const nextResponse = NextResponse.json(data, { status: response.status })
    if (response.ok && data?.cartId && data.cartId !== cartId) {
      nextResponse.cookies.set("_medusa_cart_id", data.cartId, {
        maxAge: 60 * 60 * 24 * 7,
        httpOnly: true,
        path: "/",
        sameSite: (process.env.COOKIE_SAME_SITE || "lax") as "lax" | "strict" | "none",
        secure: process.env.COOKIE_SECURE === "true",
      })
    }

    console.info(`${LOG_PREFIX} Medusa chat process response`, {
      ok: response.ok,
      status: response.status,
      guest_id: guestId,
      conversation_id: data?.conversationId || conversationId,
      conversation_status: data?.conversationStatus,
      intent: data?.intent,
    })

    return nextResponse
  } catch (err) {
    console.error(`${LOG_PREFIX} proxy failed`, {
      guest_id: guestId,
      conversation_id: conversationId,
      error: err instanceof Error ? err.message : err,
    })
    return NextResponse.json(
      {
        error: "Xin lỗi, hệ thống đang gặp sự cố tạm thời. Vui lòng thử lại sau.",
        detail: err instanceof Error ? err.message : String(err),
        guestId,
        conversationId,
      },
      { status: 502 }
    )
  }
}
