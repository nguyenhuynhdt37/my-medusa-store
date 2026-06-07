"use client"

import Script from "next/script"
import { createElement } from "react"

const projectId = process.env.NEXT_PUBLIC_DIALOGFLOW_PROJECT_ID
const agentId = process.env.NEXT_PUBLIC_DIALOGFLOW_AGENT_ID
const location = process.env.NEXT_PUBLIC_DIALOGFLOW_LOCATION || "global"
const languageCode = process.env.NEXT_PUBLIC_DIALOGFLOW_LANGUAGE_CODE || "vi"
const chatTitle = process.env.NEXT_PUBLIC_DIALOGFLOW_CHAT_TITLE || "Bot Medusa"

const DialogflowMessenger = () => {
  if (!projectId || !agentId) {
    return null
  }

  return (
    <>
      <Script
        src="https://www.gstatic.com/dialogflow-console/fast/df-messenger/prod/v1/df-messenger.js"
        strategy="afterInteractive"
      />
      {createElement(
        "df-messenger",
        {
          "project-id": projectId,
          "agent-id": agentId,
          location,
          "language-code": languageCode,
          "max-query-length": "-1",
        },
        createElement("df-messenger-chat-bubble", {
          "chat-title": chatTitle,
        })
      )}
    </>
  )
}

export default DialogflowMessenger
