import { SessionsClient } from "@google-cloud/dialogflow-cx"
import { existsSync } from "fs"
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

const projectId = process.env.DIALOGFLOW_PROJECT_ID
const agentId = process.env.DIALOGFLOW_AGENT_ID
const location = process.env.DIALOGFLOW_LOCATION || "global"
const languageCode = process.env.DIALOGFLOW_LANGUAGE_CODE || "vi"

const getClient = () => {
  const options =
    location && location !== "global"
      ? { apiEndpoint: `${location}-dialogflow.googleapis.com` }
      : undefined

  return new SessionsClient(options)
}

const getTextFromResponseMessage = (message: any): string | null => {
  const text = message?.text?.text
  if (Array.isArray(text)) {
    return text.filter(Boolean).join("\n")
  }
  return null
}

const normalizeResponseMessages = (messages: any[] = []): ChatbotPayload[] => {
  const normalized: ChatbotPayload[] = []
  let pendingText = ""

  for (const message of messages) {
    const text = getTextFromResponseMessage(message)
    if (text) {
      pendingText = pendingText ? `${pendingText}\n${text}` : text
      continue
    }

    if (message?.payload) {
      normalized.push({
        text: pendingText,
        payload: message.payload,
      })
      pendingText = ""
    }
  }

  if (pendingText || !normalized.length) {
    normalized.push({
      text:
        pendingText ||
        "Mình chưa nhận được phản hồi phù hợp. Bạn thử hỏi lại giúp mình nhé.",
    })
  }

  return normalized
}

export async function POST(request: NextRequest) {
  if (!projectId || !agentId) {
    return NextResponse.json(
      { error: "Dialogflow CX is not configured on the storefront server." },
      { status: 500 }
    )
  }

  const body = (await request.json().catch(() => ({}))) as ChatbotRequest
  const message = body.message?.trim()

  if (!message) {
    return NextResponse.json({ error: "Message is required." }, { status: 400 })
  }

  const sessionId =
    body.sessionId?.replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 64) ||
    crypto.randomUUID()
  const cookieStore = await cookies()
  const customerToken = cookieStore.get("_medusa_jwt")?.value

  const credentialsPath = process.env.GOOGLE_APPLICATION_CREDENTIALS
  if (credentialsPath && !existsSync(credentialsPath)) {
    return NextResponse.json(
      {
        error:
          "Thiếu file service account Dialogflow CX trên server. Route này không dùng fallback.",
        detail: `Missing credentials file: ${credentialsPath}`,
      },
      { status: 500 }
    )
  }

  try {
    const client = getClient()
    const session = client.projectLocationAgentSessionPath(
      projectId,
      location,
      agentId,
      sessionId
    )

    const [response] = await client.detectIntent({
      session,
      queryInput: {
        text: {
          text: message,
        },
        languageCode,
      },
      queryParams: {
        webhookHeaders: customerToken
          ? {
              Authorization: `Bearer ${customerToken}`,
            }
          : undefined,
      },
    })

    const queryResult = response.queryResult
    const messages = normalizeResponseMessages(
      queryResult?.responseMessages || []
    )

    return NextResponse.json({
      sessionId,
      intent: queryResult?.intent?.displayName || "Fallback",
      messages,
    })
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown error"

    return NextResponse.json(
      {
        error:
          "Không thể kết nối Dialogflow CX. Kiểm tra service account, IAM role và biến môi trường.",
        detail,
      },
      { status: 502 }
    )
  }
}
