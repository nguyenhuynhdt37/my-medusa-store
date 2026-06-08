import { LexRuntimeV2Client, RecognizeTextCommand } from "@aws-sdk/client-lex-runtime-v2"
import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

type ChatbotRequest = {
  message?: string
  sessionId?: string
}

type ChatbotPayload = {
  text: string
  payload?: Record<string, unknown>
}

const lexClient = new LexRuntimeV2Client({
  region: process.env.AWS_REGION || "us-east-1",
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || "",
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || "",
  },
})

const botId = process.env.LEX_BOT_ID
const botAliasId = process.env.LEX_BOT_ALIAS_ID
const localeId = process.env.LEX_LOCALE_ID || "vi_VN"

const normalizeResponseMessages = (messages: any[] = []): ChatbotPayload[] => {
  const normalized: ChatbotPayload[] = []
  let pendingText = ""

  for (const message of messages) {
    if (message.contentType === "PlainText") {
      pendingText = pendingText ? `${pendingText}\n${message.content}` : message.content
    } else if (message.contentType === "CustomPayload") {
      try {
        const payload = JSON.parse(message.content)
        normalized.push({
          text: pendingText,
          payload: payload,
        })
        pendingText = ""
      } catch (e) {
        console.error("Failed to parse custom payload", e)
      }
    }
  }

  if (pendingText || !normalized.length) {
    normalized.push({
      text: pendingText || "Mình chưa nhận được phản hồi phù hợp. Bạn thử hỏi lại giúp mình nhé.",
    })
  }

  return normalized
}

export async function POST(request: NextRequest) {
  if (!botId || !botAliasId) {
    return NextResponse.json(
      { error: "AWS Lex is not configured on the storefront server. Please check .env.local" },
      { status: 500 }
    )
  }

  const body = (await request.json().catch(() => ({}))) as ChatbotRequest
  const message = body.message?.trim()

  if (!message) {
    return NextResponse.json({ error: "Message is required." }, { status: 400 })
  }

  const sessionId = body.sessionId?.replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 64) || crypto.randomUUID()
  const cookieStore = await cookies()
  const customerToken = cookieStore.get("_medusa_jwt")?.value

  const backendUrl = process.env.MEDUSA_BACKEND_URL || process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL || "http://localhost:9000"
  
  try {
    await fetch(`${backendUrl}/store/chat`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
      },
      body: JSON.stringify({
        session_id: sessionId,
        sender: "user",
        text: message,
      })
    })
  } catch (err) {
    console.error("Failed to save user message", err)
  }

  try {
    const params = {
      botId,
      botAliasId,
      localeId,
      sessionId,
      text: message,
      requestAttributes: customerToken ? {
        Authorization: `Bearer ${customerToken}`,
      } : undefined,
    }

    const command = new RecognizeTextCommand(params)
    const response = await lexClient.send(command)

    const messages = normalizeResponseMessages(response.messages || [])

    try {
      for (const msg of messages) {
        await fetch(`${backendUrl}/store/chat`, {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
          },
          body: JSON.stringify({
            session_id: sessionId,
            sender: "bot",
            text: msg.text,
            payload: msg.payload || null,
          })
        })
      }
    } catch (err) {
      console.error("Failed to save bot messages", err)
    }

    return NextResponse.json({
      sessionId,
      intent: response.sessionState?.intent?.name || "Fallback",
      messages,
    })
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown error"

    return NextResponse.json(
      {
        error: "Không thể kết nối AWS Lex. Kiểm tra Access Key, Secret Key, và quyền IAM.",
        detail,
      },
      { status: 502 }
    )
  }
}
