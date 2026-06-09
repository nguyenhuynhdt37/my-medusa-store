import { Avatar, Badge, Button, Heading, Text } from "@medusajs/ui";
import type { RefObject } from "react";
import ReactMarkdown from "react-markdown";
import type {
  ChatConversation,
  ChatMessage,
  ChatPresenceMap,
  StatusMeta,
  Translate,
} from "../types";
import { MessageIcon, SendIcon } from "../icons";
import { ChatPanelErrorBoundary } from "./error-boundary";
import { formatLastSeen, formatTime, getCustomerLabel } from "../utils";

type ChatPanelProps = {
  activeConversation: ChatConversation | null;
  activeStatusMeta: StatusMeta | null;
  customerTypingMap: Record<string, boolean>;
  handleKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  handleMessagesScroll: () => void;
  handleTextareaInput: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  input: string;
  messages: ChatMessage[];
  messagesEndRef: RefObject<HTMLDivElement>;
  messagesScrollRef: RefObject<HTMLDivElement>;
  presenceMap: ChatPresenceMap;
  sendMessage: (event?: React.FormEvent) => void;
  textareaRef: RefObject<HTMLTextAreaElement>;
  tt: Translate;
  updateStatus: (
    status: "WAITING_ADMIN" | "IN_PROGRESS" | "CLOSED" | "BOT_HANDLED",
  ) => void;
};

export const ChatPanel = ({
  activeConversation,
  activeStatusMeta,
  customerTypingMap,
  handleKeyDown,
  handleMessagesScroll,
  handleTextareaInput,
  input,
  messages,
  messagesEndRef,
  messagesScrollRef,
  presenceMap,
  sendMessage,
  textareaRef,
  tt,
  updateStatus,
}: ChatPanelProps) => (
  <ChatPanelErrorBoundary
    strings={{
      panelTitle: tt("chat.error.panelTitle"),
      panelDescription: tt("chat.error.panelDescription"),
    }}
  >
    <main className="flex h-full min-h-0 min-w-0 flex-col bg-ui-bg-subtle">
      {activeConversation ? (
        <>
          <ChatHeader
            activeConversation={activeConversation}
            activeStatusMeta={activeStatusMeta}
            presenceMap={presenceMap}
            tt={tt}
            updateStatus={updateStatus}
          />

          <MessageList
            activeConversation={activeConversation}
            activeStatusMeta={activeStatusMeta}
            customerTypingMap={customerTypingMap}
            handleMessagesScroll={handleMessagesScroll}
            messages={messages}
            messagesEndRef={messagesEndRef}
            messagesScrollRef={messagesScrollRef}
            tt={tt}
          />

          <Composer
            activeConversation={activeConversation}
            handleKeyDown={handleKeyDown}
            handleTextareaInput={handleTextareaInput}
            input={input}
            sendMessage={sendMessage}
            textareaRef={textareaRef}
            tt={tt}
          />
        </>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center bg-ui-bg-subtle text-ui-fg-subtle">
          <MessageIcon className="mb-4 h-10 w-10 text-ui-fg-disabled" />
          <Heading level="h1" className="mb-2 text-xl text-ui-fg-base">
            {tt("chat.empty.title")}
          </Heading>
          <Text className="max-w-xs text-center">
            {tt("chat.empty.description")}
          </Text>
        </div>
      )}
    </main>
  </ChatPanelErrorBoundary>
);

const ChatHeader = ({
  activeConversation,
  activeStatusMeta,
  presenceMap,
  tt,
  updateStatus,
}: {
  activeConversation: ChatConversation;
  activeStatusMeta: StatusMeta | null;
  presenceMap: ChatPresenceMap;
  tt: Translate;
  updateStatus: ChatPanelProps["updateStatus"];
}) => (
  <div className="flex h-[76px] shrink-0 items-center justify-between gap-4 border-b border-ui-border-base bg-ui-bg-base px-5">
    <div className="min-w-0">
      <div className="flex items-center gap-3">
        <Heading level="h2" className="truncate text-base">
          {getCustomerLabel(activeConversation)}
        </Heading>
        <Badge size="small" color={activeStatusMeta?.badgeColor || "grey"}>
          <span className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${activeStatusMeta?.dotClassName || "bg-ui-fg-muted"}`}
            />
            {activeStatusMeta?.label}
          </span>
        </Badge>
      </div>
      <Text size="xsmall" className="mt-1 text-ui-fg-muted">
        {presenceMap[activeConversation.id]?.online
          ? tt("chat.presence.online")
          : presenceMap[activeConversation.id]?.last_seen_at
            ? `Hoạt động ${formatLastSeen(
                presenceMap[activeConversation.id].last_seen_at,
                tt,
              )}`
            : tt("chat.presence.offline")}
      </Text>
    </div>

    <div className="flex shrink-0 items-center gap-2">
      {activeConversation.status === "WAITING_ADMIN" && (
        <Button
          variant="primary"
          size="small"
          onClick={() => updateStatus("IN_PROGRESS")}
        >
          {tt("chat.actions.takeOver")}
        </Button>
      )}
      {activeConversation.status === "IN_PROGRESS" && (
        <>
          <Button
            variant="secondary"
            size="small"
            onClick={() => updateStatus("BOT_HANDLED")}
          >
            {tt("chat.actions.returnToBot")}
          </Button>
          <Button
            variant="transparent"
            size="small"
            onClick={() => updateStatus("CLOSED")}
          >
            {tt("chat.actions.closeSession")}
          </Button>
        </>
      )}
      {(activeConversation.status === "CLOSED" ||
        activeConversation.status === "RESOLVED") && (
        <Button
          variant="secondary"
          size="small"
          onClick={() => updateStatus("IN_PROGRESS")}
        >
          {tt("chat.actions.reopenSession")}
        </Button>
      )}
    </div>
  </div>
);

const MessageList = ({
  activeConversation,
  activeStatusMeta,
  customerTypingMap,
  handleMessagesScroll,
  messages,
  messagesEndRef,
  messagesScrollRef,
  tt,
}: {
  activeConversation: ChatConversation;
  activeStatusMeta: StatusMeta | null;
  customerTypingMap: Record<string, boolean>;
  handleMessagesScroll: () => void;
  messages: ChatMessage[];
  messagesEndRef: RefObject<HTMLDivElement>;
  messagesScrollRef: RefObject<HTMLDivElement>;
  tt: Translate;
}) => (
  <div
    ref={messagesScrollRef}
    onScroll={handleMessagesScroll}
    className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6 py-5"
  >
    <div className="flex flex-col gap-5 pb-2">
      {activeConversation.status === "WAITING_ADMIN" && (
        <div className="mx-auto w-full max-w-md rounded-md border border-ui-border-base bg-ui-bg-base px-4 py-3 text-center shadow-borders-base">
          <Text size="small" weight="plus" className="text-ui-fg-base">
            Yêu cầu hỗ trợ đã được gửi
          </Text>
          <Text size="small" className="mt-1 text-ui-fg-muted">
            Khách đang chờ nhân viên tiếp nhận. Ưu tiên phản hồi trong vài phút.
          </Text>
        </div>
      )}
      {activeConversation.status === "IN_PROGRESS" && activeStatusMeta && (
        <div className="mx-auto w-full max-w-md rounded-md border border-ui-border-base bg-ui-bg-base px-4 py-3 text-center shadow-borders-base">
          <Text size="small" weight="plus" className="text-ui-fg-base">
            {activeStatusMeta.label}
          </Text>
          <Text size="small" className="mt-1 text-ui-fg-muted">
            {activeStatusMeta.description}
          </Text>
        </div>
      )}
      {messages.length === 0 ? (
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-2 text-center text-ui-fg-muted">
          <MessageIcon className="h-10 w-10 text-ui-fg-disabled" />
          <Text>{tt("chat.messages.noMessages")}</Text>
        </div>
      ) : (
        messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            nextMessage={messages[index + 1]}
            tt={tt}
          />
        ))
      )}

      {customerTypingMap[activeConversation.id] && (
        <div className="flex justify-start">
          <div className="rounded-md border border-ui-border-base bg-ui-bg-base px-4 py-3 text-sm text-ui-fg-muted">
            Khách đang nhập...
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  </div>
);

const MessageBubble = ({
  message,
  nextMessage,
  tt,
}: {
  message: ChatMessage;
  nextMessage?: ChatMessage;
  tt: Translate;
}) => {
  const isAdmin = message.sender_type === "admin";
  const isBot = message.sender_type === "bot";
  const showAvatar = !nextMessage || nextMessage.sender_type !== message.sender_type;
  const senderLabel = isAdmin
    ? tt("chat.sender.you")
    : isBot
      ? tt("chat.sender.bot")
      : message.sender_type === "customer"
        ? tt("chat.sender.customer")
        : tt("chat.sender.guest");

  const extractedImages: { alt: string; url: string }[] = [];
  const markdownImgRegex = /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g;
  let cleanText = message.content.replace(markdownImgRegex, (_match, alt, url) => {
    extractedImages.push({ alt, url });
    return "";
  });

  const rawImgRegex =
    /(?<!\()(https?:\/\/[^\s]+?\.(?:png|jpe?g|gif|webp|svg))(?!\))/gi;
  cleanText = cleanText
    .replace(rawImgRegex, (url) => {
      extractedImages.push({ alt: "Image", url });
      return "";
    })
    .trim();

  return (
    <div className={`flex gap-3 ${isAdmin ? "flex-row-reverse" : "flex-row"}`}>
      <div className="flex w-8 shrink-0 flex-col justify-end">
        {showAvatar && (
          <Avatar
            size="small"
            fallback={isAdmin ? "NV" : isBot ? "AI" : "KH"}
            variant="squared"
          />
        )}
      </div>

      <div
        className={`flex max-w-[76%] flex-col gap-2 ${isAdmin ? "items-end" : "items-start"}`}
      >
        {extractedImages.length > 0 && (
          <div className="flex flex-col gap-2">
            {extractedImages.map((image, imageIndex) => (
              <a
                key={`${image.url}-${imageIndex}`}
                href={image.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-fit overflow-hidden rounded-md border border-ui-border-base bg-ui-bg-base"
              >
                <img
                  src={image.url}
                  alt={image.alt || tt("chat.messages.imageAlt")}
                  className="max-h-[320px] w-full max-w-[320px] object-cover"
                />
              </a>
            ))}
          </div>
        )}

        {cleanText && (
          <div
            className={`rounded-md px-4 py-3 text-sm shadow-borders-base ${
              isAdmin
                ? "bg-ui-bg-interactive text-ui-fg-on-color"
                : isBot
                  ? "bg-ui-bg-base text-ui-fg-base"
                  : "bg-ui-bg-field text-ui-fg-base"
            }`}
          >
            <ReactMarkdown
              components={{
                h1: ({ node: _node, ...props }) => (
                  <h1 className="mb-2 mt-3 text-lg font-bold" {...props} />
                ),
                h2: ({ node: _node, ...props }) => (
                  <h2 className="mb-1 mt-2 text-base font-bold" {...props} />
                ),
                h3: ({ node: _node, ...props }) => (
                  <h3 className="mb-1 mt-2 text-sm font-bold" {...props} />
                ),
                p: ({ node: _node, ...props }) => (
                  <p className="mb-2 last:mb-0" {...props} />
                ),
                ul: ({ node: _node, ...props }) => (
                  <ul className="mb-2 list-disc space-y-1 pl-5" {...props} />
                ),
                ol: ({ node: _node, ...props }) => (
                  <ol className="mb-2 list-decimal space-y-1 pl-5" {...props} />
                ),
                a: ({ node: _node, ...props }) => (
                  <a
                    className="break-all underline"
                    target="_blank"
                    rel="noopener noreferrer"
                    {...props}
                  />
                ),
                code: ({ node: _node, ...props }) => (
                  <code
                    className="rounded bg-black/10 px-1 py-0.5 text-[13px] dark:bg-white/10"
                    {...props}
                  />
                ),
                pre: ({ node: _node, ...props }) => (
                  <pre
                    className="my-2 overflow-x-auto rounded-md bg-black/10 p-3 text-[13px] dark:bg-white/10"
                    {...props}
                  />
                ),
              }}
            >
              {cleanText}
            </ReactMarkdown>
          </div>
        )}

        <div
          className={`flex items-center gap-1 px-1 ${isAdmin ? "flex-row-reverse" : "flex-row"}`}
        >
          <Text size="xsmall" weight="plus" className="text-ui-fg-subtle">
            {senderLabel}
          </Text>
          <span className="text-[10px] text-ui-fg-muted">.</span>
          <Text size="xsmall" className="text-ui-fg-muted">
            {formatTime(message.created_at)}
          </Text>
        </div>
      </div>
    </div>
  );
};

const Composer = ({
  activeConversation,
  handleKeyDown,
  handleTextareaInput,
  input,
  sendMessage,
  textareaRef,
  tt,
}: {
  activeConversation: ChatConversation;
  handleKeyDown: ChatPanelProps["handleKeyDown"];
  handleTextareaInput: ChatPanelProps["handleTextareaInput"];
  input: string;
  sendMessage: ChatPanelProps["sendMessage"];
  textareaRef: RefObject<HTMLTextAreaElement>;
  tt: Translate;
}) => (
  <div className="shrink-0 border-t border-ui-border-base bg-ui-bg-base p-4">
    {activeConversation.status === "IN_PROGRESS" ? (
      <form
        onSubmit={sendMessage}
        className="flex items-end gap-2 rounded-md border border-ui-border-base bg-ui-bg-field p-2 focus-within:border-ui-border-interactive"
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleTextareaInput}
          onKeyDown={handleKeyDown}
          placeholder={tt("chat.messages.placeholder")}
          className="min-h-[44px] max-h-[180px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-ui-fg-base outline-none placeholder:text-ui-fg-muted"
          rows={1}
        />
        <Button
          type="submit"
          variant="primary"
          className="h-10 w-10 p-0"
          disabled={!input.trim()}
        >
          <SendIcon className="h-4 w-4" />
        </Button>
      </form>
    ) : (
      <div className="flex h-[52px] items-center justify-center rounded-md border border-ui-border-base bg-ui-bg-subtle">
        <Text size="small" className="text-ui-fg-muted">
          {activeConversation.status === "BOT_HANDLED" &&
            tt("chat.messages.botProcessing")}
          {activeConversation.status === "WAITING_ADMIN" &&
            tt("chat.messages.waitingForAdmin")}
          {(activeConversation.status === "CLOSED" ||
            activeConversation.status === "RESOLVED") &&
            tt("chat.messages.sessionClosed")}
        </Text>
      </div>
    )}
  </div>
);
