import { MedusaContainer } from "@medusajs/framework/types"
import { CHAT_MODULE } from "../modules/chat"
import { runChatAutoReturn } from "../api/utils/chat-auto-return"

export default async function chatAutoReturnJob(container: MedusaContainer) {
  const chatModuleService = container.resolve(CHAT_MODULE)
  await runChatAutoReturn(chatModuleService)
}

export const config = {
  name: "chat-auto-return-to-bot",
  schedule: "* * * * *",
}
