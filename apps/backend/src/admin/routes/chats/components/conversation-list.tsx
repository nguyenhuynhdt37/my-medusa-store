import { Avatar, Badge, Heading, Input, Text } from "@medusajs/ui";
import type {
  ChatConversation,
  ChatPresenceMap,
  ChatStatusFilter,
  Translate,
} from "../types";
import { MessageIcon, SearchIcon } from "../icons";
import {
  formatLastSeen,
  formatTime,
  getCustomerLabel,
  getInitials,
  getStatusMeta,
} from "../utils";

type ConversationListProps = {
  activeConversation: ChatConversation | null;
  conversations: ChatConversation[];
  customerTypingMap: Record<string, boolean>;
  loading: boolean;
  presenceMap: ChatPresenceMap;
  searchQuery: string;
  setActiveConversation: (conversation: ChatConversation) => void;
  setSearchQuery: (value: string) => void;
  setStatusFilter: (value: ChatStatusFilter) => void;
  statusFilter: ChatStatusFilter;
  tt: Translate;
  unreadCount: number;
};

export const ConversationList = ({
  activeConversation,
  conversations,
  customerTypingMap,
  loading,
  presenceMap,
  searchQuery,
  setActiveConversation,
  setSearchQuery,
  setStatusFilter,
  statusFilter,
  tt,
  unreadCount,
}: ConversationListProps) => (
  <aside className="flex h-full min-h-0 min-w-0 flex-col border-r border-ui-border-base bg-ui-bg-subtle">
    <div className="shrink-0 border-b border-ui-border-base bg-ui-bg-base p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <Heading level="h2" className="text-base">
          {tt("chat.sidebar.title")}
        </Heading>
        {unreadCount > 0 && (
          <Badge color="red" size="small">
            {unreadCount > 99 ? "99+" : unreadCount}
          </Badge>
        )}
      </div>

      <div className="relative">
        <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-ui-fg-muted" />
        <Input
          placeholder={tt("chat.sidebar.searchPlaceholder")}
          className="bg-ui-bg-field pl-9"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
        />
      </div>

      <div className="mt-3 grid grid-cols-3 rounded-md border border-ui-border-base bg-ui-bg-field p-1">
        {[
          ["WAITING_ADMIN", "Chờ tiếp nhận"],
          ["IN_PROGRESS", "Đang hỗ trợ"],
          ["CLOSED", "Đã kết thúc"],
        ].map(([status, label]) => (
          <button
            key={status}
            type="button"
            onClick={() => setStatusFilter(status as ChatStatusFilter)}
            className={`rounded px-2 py-1.5 text-xs font-medium transition-colors ${
              statusFilter === status
                ? "bg-ui-bg-base text-ui-fg-base shadow-borders-base"
                : "text-ui-fg-muted hover:text-ui-fg-base"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>

    <div className="flex shrink-0 items-center justify-between border-b border-ui-border-base px-4 py-3">
      <Text size="small" weight="plus" className="text-ui-fg-base">
        {statusFilter === "WAITING_ADMIN" && `Chờ tiếp nhận (${conversations.length})`}
        {statusFilter === "IN_PROGRESS" && `Đang hỗ trợ (${conversations.length})`}
        {statusFilter === "CLOSED" && `Đã kết thúc (${conversations.length})`}
      </Text>
      <Text size="xsmall" className="text-ui-fg-muted">
        Mới nhất trước
      </Text>
    </div>

    <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
      {loading ? (
        <div className="flex flex-col items-center gap-2 p-6 text-center text-ui-fg-muted">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-ui-fg-subtle border-t-transparent" />
          <Text size="small">{tt("common.loading")}</Text>
        </div>
      ) : conversations.length === 0 ? (
        <div className="flex flex-col items-center gap-2 p-6 text-center text-ui-fg-muted">
          <MessageIcon className="h-8 w-8 text-ui-fg-disabled" />
          <Text size="small">{tt("chat.sidebar.noConversations")}</Text>
        </div>
      ) : (
        conversations.map((conversation) => {
          const statusMeta = getStatusMeta(conversation.status, tt);
          const customerLabel = getCustomerLabel(conversation);
          const unread = Number(
            conversation.admin_metadata?.unread_admin_count || 0,
          );
          const isActive = activeConversation?.id === conversation.id;
          const presence = presenceMap[conversation.id];
          const isTyping = customerTypingMap[conversation.id];

          return (
            <button
              key={conversation.id}
              type="button"
              onClick={() => setActiveConversation(conversation)}
              className={`relative w-full rounded-md border p-3 text-left shadow-borders-base transition-colors ${
                isActive
                  ? "border-ui-border-interactive bg-ui-bg-base shadow-borders-interactive-with-active"
                  : unread > 0
                    ? "border-ui-border-interactive bg-ui-bg-highlight hover:bg-ui-bg-base"
                    : "border-ui-border-base bg-ui-bg-base hover:bg-ui-bg-base-hover"
              }`}
            >
              {isActive && (
                <span className="absolute right-3 top-3 h-2.5 w-2.5 rounded-full bg-ui-fg-interactive" />
              )}
              <div className="flex items-start gap-3">
                <Avatar
                  src=""
                  fallback={getInitials(customerLabel)}
                  size="base"
                  variant="squared"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <Text
                      size="small"
                      weight="plus"
                      className="truncate text-ui-fg-base"
                    >
                      {customerLabel}
                    </Text>
                    <Text size="xsmall" className="shrink-0 text-ui-fg-muted">
                      {formatTime(conversation.last_message_at)}
                    </Text>
                  </div>
                  <Text size="small" className="mt-1 truncate text-ui-fg-muted">
                    {isTyping
                      ? "Khách đang nhập..."
                      : conversation.last_message_preview || "Chưa có tin nhắn"}
                  </Text>
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <Badge size="small" color={statusMeta.badgeColor}>
                        {statusMeta.shortLabel}
                      </Badge>
                      {conversation.last_message_sender === "bot" && (
                        <Badge size="small" color="green">
                          Bot
                        </Badge>
                      )}
                      {conversation.last_message_sender === "admin" && (
                        <Badge size="small" color="blue">
                          Nhân viên
                        </Badge>
                      )}
                    </div>
                    {unread > 0 && (
                      <Badge size="small" color="red">
                        {unread}
                      </Badge>
                    )}
                  </div>
                  <Text size="xsmall" className="mt-2 text-ui-fg-muted">
                    {presence?.online
                      ? tt("chat.presence.online")
                      : presence?.last_seen_at
                        ? formatLastSeen(presence.last_seen_at, tt)
                        : ""}
                  </Text>
                </div>
              </div>
            </button>
          );
        })
      )}
    </div>
  </aside>
);
