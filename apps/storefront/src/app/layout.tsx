import { getBaseURL } from "@lib/util/env"
import CustomChat from "@modules/chatbot/components/custom-chat"
import { Metadata } from "next"
import I18nProvider from "./providers"
import "styles/globals.css"

export const metadata: Metadata = {
  metadataBase: new URL(getBaseURL()),
}

export default function RootLayout(props: { children: React.ReactNode }) {
  return (
    <html lang="vi" data-mode="light">
      <body suppressHydrationWarning>
        <I18nProvider locale="vi">
          <main className="relative">{props.children}</main>
          <CustomChat />
        </I18nProvider>
      </body>
    </html>
  )
}
