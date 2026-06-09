import { Container } from "@medusajs/ui";
import { defineRouteConfig } from "@medusajs/admin-sdk";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChatPanel } from "./components/chat-panel";
import { ChatReports } from "./components/chat-reports";
import { ConversationList } from "./components/conversation-list";
import { CustomerProfile } from "./components/customer-profile";
import { OverviewStrip } from "./components/overview-strip";
import { ChatIcon } from "./icons";
import type { ChatView } from "./types";
import { getStatusMeta, makeTranslate } from "./utils";
import { useAdminChat } from "./use-admin-chat";

const ChatAdminPage = () => {
  const { t } = useTranslation();
  const tt = makeTranslate(t);
  const [view, setView] = useState<ChatView>("inbox");
  const chat = useAdminChat(tt);
  const activeStatusMeta = chat.activeConversation
    ? getStatusMeta(chat.activeConversation.status, tt)
    : null;

  return (
    <div className="flex h-[calc(100vh-120px)] min-h-0 flex-col gap-4">
      <div className="shrink-0">
        <div className="flex rounded-md border border-ui-border-base bg-ui-bg-field p-1">
          <button
            type="button"
            onClick={() => setView("inbox")}
            className={`rounded px-3 py-1.5 text-sm font-medium ${
              view === "inbox"
                ? "bg-ui-bg-base text-ui-fg-base shadow-borders-base"
                : "text-ui-fg-muted"
            }`}
          >
            {tt("chat.tabs.inbox")}
          </button>
          <button
            type="button"
            onClick={() => setView("reports")}
            className={`rounded px-3 py-1.5 text-sm font-medium ${
              view === "reports"
                ? "bg-ui-bg-base text-ui-fg-base shadow-borders-base"
                : "text-ui-fg-muted"
            }`}
          >
            {tt("chat.tabs.reports")}
          </button>
        </div>
      </div>

      {view === "reports" ? (
        <ChatReports
          conversations={chat.conversations}
          stats={chat.stats}
          tt={tt}
        />
      ) : (
        <>
          <OverviewStrip
            conversations={chat.conversations}
            stats={chat.stats}
            tt={tt}
          />
          <Container className="grid min-h-0 flex-1 grid-cols-[25%_55%_20%] overflow-hidden border border-ui-border-base bg-ui-bg-base p-0">
            <ConversationList
              activeConversation={chat.activeConversation}
              conversations={chat.filteredConversations}
              customerTypingMap={chat.customerTypingMap}
              loading={chat.loading}
              presenceMap={chat.presenceMap}
              searchQuery={chat.searchQuery}
              setActiveConversation={chat.setActiveConversation}
              setSearchQuery={chat.setSearchQuery}
              setStatusFilter={chat.setStatusFilter}
              statusFilter={chat.statusFilter}
              tt={tt}
              unreadCount={chat.unreadCount}
            />
            <ChatPanel
              activeConversation={chat.activeConversation}
              activeStatusMeta={activeStatusMeta}
              customerTypingMap={chat.customerTypingMap}
              handleKeyDown={chat.handleKeyDown}
              handleMessagesScroll={chat.handleMessagesScroll}
              handleTextareaInput={chat.handleTextareaInput}
              input={chat.input}
              messages={chat.messages}
              messagesEndRef={chat.messagesEndRef}
              messagesScrollRef={chat.messagesScrollRef}
              presenceMap={chat.presenceMap}
              sendMessage={chat.sendMessage}
              textareaRef={chat.textareaRef}
              tt={tt}
              updateStatus={chat.updateStatus}
            />
            <CustomerProfile
              activeConversation={chat.activeConversation}
              activeStatusMeta={activeStatusMeta}
              updateStatus={chat.updateStatus}
            />
          </Container>
        </>
      )}
    </div>
  );
};

export const config = defineRouteConfig({
  label: "chat.routeLabel",
  icon: ChatIcon,
  translationNs: "chat",
});

export default ChatAdminPage;
