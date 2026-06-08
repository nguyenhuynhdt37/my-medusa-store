import { LexRuntimeV2Client, RecognizeTextCommand } from "@aws-sdk/client-lex-runtime-v2"
import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"
import { shouldEscalateToAdmin } from "./escalation"

export const runtime = "nodejs"

const LOG_PREFIX = "[chat:storefront:api]"

type ChatbotRequest = {
  message?: string
  guestId?: string
  conversationId?: string | null
}

type ChatbotPayload = {
  id?: string
  text: string
  created_at?: string
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
  const body = (await request.json().catch(() => ({}))) as ChatbotRequest
  const message = body.message?.trim()

  console.info(`${LOG_PREFIX} request received`, {
    has_message: Boolean(message),
    guest_id: body.guestId,
    conversation_id: body.conversationId,
  })

  if (!message) {
    console.error(`${LOG_PREFIX} missing message`)
    return NextResponse.json({ error: "Message is required." }, { status: 400 })
  }

  const guestId = body.guestId?.replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 64) || crypto.randomUUID()
  const clientConversationId =
    body.conversationId?.replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 128) || null
  const cookieStore = await cookies()
  const customerToken = cookieStore.get("_medusa_jwt")?.value

  const backendUrl = process.env.MEDUSA_BACKEND_URL || process.env.NEXT_PUBLIC_MEDUSA_BACKEND_URL || "http://localhost:9000"

  let conversationStatus = "BOT_HANDLED"
  let conversationId = ""
  let userMessage: any = null
  let failedResponseCount = 0

  try {
    // Save user message to backend
    console.info(`${LOG_PREFIX} saving user message`, {
      backend_url: backendUrl,
      guest_id: guestId,
      conversation_id: clientConversationId,
      sender_type: customerToken ? "customer" : "guest",
      content_length: message.length,
    })

    const res = await fetch(`${backendUrl}/store/chats/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
        ...(customerToken ? { "Authorization": `Bearer ${customerToken}` } : {})
      },
      body: JSON.stringify({
        conversation_id: clientConversationId,
        guest_id: guestId,
        sender_type: customerToken ? "customer" : "guest",
        content: message,
      })
    })

    const data = await res.json().catch(() => null)

    if (!res.ok || !data?.message?.id || !data?.conversation?.id) {
      console.error(`${LOG_PREFIX} user message save failed`, {
        ok: res.ok,
        status: res.status,
        response: data,
      })
      return NextResponse.json(
        { error: "Không thể lưu tin nhắn vào database.", detail: data },
        { status: 502 }
      )
    }

    if (data.conversation?.status) {
      conversationStatus = data.conversation.status
      conversationId = data.conversation.id
    }
    failedResponseCount = Number(data.conversation?.admin_metadata?.failed_response_count || 0)

    userMessage = data.message
    console.info(`${LOG_PREFIX} user message saved`, {
      message_id: userMessage.id,
      conversation_id: conversationId,
      sender_type: userMessage.sender_type,
      created_at: userMessage.created_at,
    })
  } catch (err) {
    console.error(`${LOG_PREFIX} user message save threw`, {
      error: err instanceof Error ? err.message : err,
    })
    return NextResponse.json(
      { error: "Không thể lưu tin nhắn vào database." },
      { status: 502 }
    )
  }

  // If admin is already handling the conversation, keep routing messages to Admin.
  if (conversationStatus === "WAITING_ADMIN" || conversationStatus === "IN_PROGRESS" || conversationStatus === "RESOLVED" || conversationStatus === "CLOSED") {
    return NextResponse.json({
      guestId,
      conversationId,
      userMessage,
      intent: "HumanHandover",
      messages: [], // Storefront will wait for SSE messages from Admin
    })
  }

  if (!botId || !botAliasId) {
    console.error(`${LOG_PREFIX} lex configuration missing`, {
      conversation_id: conversationId,
      user_message_id: userMessage?.id,
    })
    return NextResponse.json(
      {
        error: "AWS Lex is not configured on the storefront server.",
        guestId,
        conversationId,
        userMessage,
      },
      { status: 500 }
    )
  }

  const lexSessionId = conversationId || clientConversationId || guestId

  try {
    console.info(`${LOG_PREFIX} calling lex`, {
      session_id: lexSessionId,
      conversation_id: conversationId,
      user_message_id: userMessage?.id,
    })

    const params = {
      botId,
      botAliasId,
      localeId,
      sessionId: lexSessionId,
      text: message,
      requestAttributes: customerToken ? {
        Authorization: `Bearer ${customerToken}`,
      } : undefined,
    }

    const command = new RecognizeTextCommand(params)
    const response = await lexClient.send(command)

    const messages = normalizeResponseMessages(response.messages || [])
    const savedBotMessages: ChatbotPayload[] = []
    const sessionAttributes = response.sessionState?.sessionAttributes || {}
    const resolvedIntent = typeof sessionAttributes.resolved_intent === "string" ? sessionAttributes.resolved_intent : null
    const lexIntentName = resolvedIntent || response.sessionState?.intent?.name || "FallbackIntent"
    const sessionConfidence = Number(sessionAttributes.ai_confidence)
    const confidence = Number.isFinite(sessionConfidence)
      ? sessionConfidence
      : response.interpretations?.[0]?.nluConfidence?.score
    const isFallback = lexIntentName.toLowerCase().includes("fallback")
    const nextFailedResponseCount = isFallback ? failedResponseCount + 1 : 0
    const escalation = shouldEscalateToAdmin({
      message,
      intent: lexIntentName,
      confidence,
      failedResponseCount: nextFailedResponseCount,
    })
    const nextConversationStatus = escalation.escalate ? "WAITING_ADMIN" : "BOT_HANDLED"

    console.info(`${LOG_PREFIX} escalation decision`, {
      conversation_id: conversationId,
      intent: lexIntentName,
      confidence,
      failed_response_count: nextFailedResponseCount,
      escalation,
    })

    try {
      for (const msg of messages) {
        console.info(`${LOG_PREFIX} saving bot message`, {
          conversation_id: conversationId || clientConversationId,
          guest_id: guestId,
          content_length: msg.text.length,
        })

        const botSaveRes = await fetch(`${backendUrl}/store/chats/messages`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
            ...(customerToken ? { "Authorization": `Bearer ${customerToken}` } : {})
          },
          body: JSON.stringify({
            conversation_id: conversationId || clientConversationId,
            guest_id: guestId,
            sender_type: "bot",
            content: msg.text,
            metadata: {
              ...(msg.payload ? { payload: msg.payload } : {}),
              ai: {
                intent: lexIntentName,
                confidence,
                escalation,
              },
            },
            conversation_status: nextConversationStatus,
            escalation_reason: escalation.escalate ? escalation.reason : null,
            ai_confidence: confidence,
            failed_response_count: nextFailedResponseCount,
          })
        })

        const botSaveData = await botSaveRes.json().catch(() => null)
        if (!botSaveRes.ok || !botSaveData?.message?.id) {
          console.error(`${LOG_PREFIX} bot message save failed`, {
            ok: botSaveRes.ok,
            status: botSaveRes.status,
            response: botSaveData,
          })
          return NextResponse.json(
            {
              error: "Bot trả lời nhưng không lưu được tin nhắn vào database.",
              guestId,
              conversationId,
              userMessage,
            },
            { status: 502 }
          )
        }

        savedBotMessages.push({
          id: botSaveData.message.id,
          text: botSaveData.message.content,
          created_at: botSaveData.message.created_at,
          payload: botSaveData.message.metadata?.payload,
        })
        console.info(`${LOG_PREFIX} bot message saved`, {
          message_id: botSaveData.message.id,
          conversation_id: botSaveData.conversation?.id,
          sender_type: botSaveData.message.sender_type,
          created_at: botSaveData.message.created_at,
        })
      }
    } catch (err) {
      console.error(`${LOG_PREFIX} bot message save threw`, {
        error: err instanceof Error ? err.message : err,
      })
      return NextResponse.json(
        {
          error: "Bot trả lời nhưng không lưu được tin nhắn vào database.",
          guestId,
          conversationId,
          userMessage,
        },
        { status: 502 }
      )
    }

    console.info(`${LOG_PREFIX} response sent`, {
      conversation_id: conversationId,
      user_message_id: userMessage?.id,
      bot_message_count: savedBotMessages.length,
      conversation_status: nextConversationStatus,
      escalation,
    })

    return NextResponse.json({
      guestId,
      conversationId,
      userMessage,
      conversationStatus: nextConversationStatus,
      escalation,
      intent: lexIntentName,
      messages: savedBotMessages,
    })
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown error"
    console.error(`${LOG_PREFIX} lex call failed`, {
      conversation_id: conversationId,
      user_message_id: userMessage?.id,
      error: detail,
    })

    return NextResponse.json(
      {
        error: "Không thể kết nối AWS Lex. Kiểm tra Access Key, Secret Key, và quyền IAM.",
        detail,
        guestId,
        conversationId,
        userMessage,
      },
      { status: 502 }
    )
  }
}
