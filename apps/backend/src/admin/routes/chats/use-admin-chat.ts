import { toast } from "@medusajs/ui";
import { useEffect, useMemo, useRef, useState } from "react";
import { useChatNotifications } from "../../lib/chat-notifications";
import type {
  ChatConversation,
  ChatMessage,
  ChatPresenceMap,
  ChatStats,
  ChatStatusFilter,
  Translate,
} from "./types";
import {
  getCustomerLabel,
  isAdminVisibleConversation,
  sortMessagesByCreatedAt,
} from "./utils";

export const useAdminChat = (tt: Translate) => {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [filteredConversations, setFilteredConversations] = useState<
    ChatConversation[]
  >([]);
  const [selectedConversationId, setSelectedConversationIdState] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [presenceMap, setPresenceMap] = useState<ChatPresenceMap>({});
  const [customerTypingMap, setCustomerTypingMap] = useState<
    Record<string, boolean>
  >({});
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] =
    useState<ChatStatusFilter>("WAITING_ADMIN");
  const [stats, setStats] = useState<ChatStats | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const adminHeartbeatRef = useRef<number | null>(null);
  const messagesScrollRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const activeConversationRef = useRef<ChatConversation | null>(null);
  const selectedConversationIdRef = useRef<string | null>(null);
  const lastActiveConvIdRef = useRef<string | null>(null);
  const adminTypingStopRef = useRef<number | null>(null);
  const customerTypingTimeoutsRef = useRef<Record<string, number>>({});
  const shouldScrollToBottomRef = useRef(true);
  const isNearBottomRef = useRef(true);

  const { unreadCount, notify, markRead } = useChatNotifications({
    baseTitle: tt("chat.notifications.baseTitle"),
    notificationTitle: tt("chat.notifications.notificationTitle"),
  });

  const notifyRef = useRef(notify);
  const translateRef = useRef(tt);

  const activeConversation = useMemo(() => {
    if (!selectedConversationId) {
      return null;
    }

    return (
      conversations.find(
        (conversation) => conversation.id === selectedConversationId,
      ) || null
    );
  }, [conversations, selectedConversationId]);

  const setSelectedConversationId = (
    nextId: string | null,
    reason: string,
  ) => {
    setSelectedConversationIdState((currentId) => {
      if (currentId === nextId) {
        return currentId;
      }

      console.log("[SELECTED_CONVERSATION]", {
        old_id: currentId,
        new_id: nextId,
        reason,
      });
      selectedConversationIdRef.current = nextId;
      shouldScrollToBottomRef.current = true;
      return nextId;
    });
  };

  const selectConversation = (conversation: ChatConversation) => {
    setSelectedConversationId(conversation.id, "user_selected");
  };

  const getSidebarConversations = (list: ChatConversation[]) => {
    let result = list.filter(isAdminVisibleConversation);

    if (searchQuery) {
      const normalizedSearch = searchQuery.toLowerCase();
      result = result.filter((conversation) => {
        return [
          getCustomerLabel(conversation),
          conversation.customer_id,
          conversation.guest_id,
          conversation.customer_email,
        ].some((value) => value?.toLowerCase().includes(normalizedSearch));
      });
    }

    result = result.filter((conversation) =>
      statusFilter === "CLOSED"
        ? conversation.status === "CLOSED" || conversation.status === "RESOLVED"
        : conversation.status === statusFilter,
    );

    return result;
  };

  const syncSelectedConversationFromList = (
    list: ChatConversation[],
    reason: string,
  ) => {
    const currentId = selectedConversationIdRef.current;
    const sidebarList = getSidebarConversations(list);

    if (!currentId) {
      setSelectedConversationId(sidebarList[0]?.id || null, `${reason}:initial`);
      return;
    }

    const stillExists = list.some((conversation) => conversation.id === currentId);
    if (stillExists) {
      return;
    }

    setSelectedConversationId(
      sidebarList[0]?.id || null,
      `${reason}:selected_missing`,
    );
  };

  const fetchConversations = async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }

    try {
      const res = await fetch("/admin/chats");
      const data = await res.json();
      const list = data.conversations || [];
      setConversations(list);
      setStats(data.stats || null);
      syncSelectedConversationFromList(list, "fetch_conversations");
    } catch {
      toast.error(tt("common.error"), {
        description: tt("chat.error.loadConversations"),
      });
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  const fetchMessages = async (id: string) => {
    try {
      const res = await fetch(`/admin/chats/${id}/messages`);
      const data = await res.json();
      const history = Array.isArray(data.messages) ? data.messages : [];

      if (selectedConversationIdRef.current !== id) {
        return;
      }

      setMessages((current) => {
        const mergedById = new Map<string, ChatMessage>();
        for (const message of current) {
          mergedById.set(message.id, message);
        }
        for (const message of history) {
          mergedById.set(message.id, message);
        }
        return sortMessagesByCreatedAt(Array.from(mergedById.values()));
      });
    } catch {
      toast.error(tt("common.error"), {
        description: tt("chat.error.loadMessages"),
      });
    }
  };

  const emitAdminTyping = (event: "typing.start" | "typing.stop") => {
    const ws = wsRef.current;
    const selected = activeConversationRef.current;
    if (!selected || !ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }

    console.log(event, {
      conversation_id: selected.id,
      sender_type: "admin",
    });
    ws.send(
      JSON.stringify({
        event,
        data: {
          conversation_id: selected.id,
          sender_type: "admin",
          user_type: "admin",
          name: "Nhân viên hỗ trợ",
        },
      }),
    );
  };

  const sendMessage = async (event?: React.FormEvent) => {
    if (event) {
      event.preventDefault();
    }

    if (
      !input.trim() ||
      !activeConversation ||
      activeConversation.status !== "IN_PROGRESS"
    ) {
      return;
    }

    const tempInput = input.trim();
    setInput("");
    emitAdminTyping("typing.stop");
    if (adminTypingStopRef.current) {
      window.clearTimeout(adminTypingStopRef.current);
      adminTypingStopRef.current = null;
    }
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      await fetch(`/admin/chats/${activeConversation.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: tempInput }),
      });
    } catch {
      toast.error(tt("common.error"), {
        description: tt("chat.error.sendMessage"),
      });
    } finally {
      window.setTimeout(() => {
        textareaRef.current?.focus();
      }, 0);
    }
  };

  const updateStatus = async (
    status: "WAITING_ADMIN" | "IN_PROGRESS" | "CLOSED" | "BOT_HANDLED",
  ) => {
    if (!activeConversation) {
      return;
    }

    const endpoint =
      status === "WAITING_ADMIN"
        ? "handover"
        : status === "IN_PROGRESS"
          ? "assign"
          : status === "BOT_HANDLED"
            ? "return-to-bot"
            : "close";

    try {
      const res = await fetch(
        `/admin/chats/${activeConversation.id}/${endpoint}`,
        { method: "POST" },
      );
      const data = await res.json().catch(() => null);

      if (!res.ok) {
        throw new Error(
          data?.error || `Admin chat action failed with status ${res.status}`,
        );
      }

      const updatedConversation = data?.conversation as
        | ChatConversation
        | undefined;
      if (!updatedConversation) {
        throw new Error("Admin chat action response is missing conversation");
      }

      const nextConversations = isAdminVisibleConversation(updatedConversation)
        ? conversations.map((conversation) =>
            conversation.id === updatedConversation.id
              ? updatedConversation
              : conversation,
          )
        : conversations.filter(
            (conversation) => conversation.id !== updatedConversation.id,
          );

      setConversations(nextConversations);

      if (!isAdminVisibleConversation(updatedConversation)) {
        syncSelectedConversationFromList(
          nextConversations,
          "status_update_removed",
        );
      }

      toast.success(tt("common.success"), {
        description: tt("chat.success.updateStatus"),
      });
      void fetchConversations(false);
    } catch (err) {
      console.error("CHAT_ACTION_ERROR", err);
      toast.error(tt("common.error"), {
        description: tt("chat.error.updateStatus"),
      });
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  const handleTextareaInput = (
    event: React.ChangeEvent<HTMLTextAreaElement>,
  ) => {
    setInput(event.target.value);
    if (event.target.value.trim()) {
      emitAdminTyping("typing.start");
    } else {
      emitAdminTyping("typing.stop");
    }
    if (adminTypingStopRef.current) {
      window.clearTimeout(adminTypingStopRef.current);
    }
    adminTypingStopRef.current = window.setTimeout(() => {
      emitAdminTyping("typing.stop");
    }, 1200);
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 180)}px`;
  };

  useEffect(() => {
    activeConversationRef.current = activeConversation;
    selectedConversationIdRef.current = selectedConversationId;
    if (activeConversation) {
      markRead();
    }
  }, [activeConversation, markRead, selectedConversationId]);

  useEffect(() => {
    notifyRef.current = notify;
    translateRef.current = tt;
  }, [notify, tt]);

  useEffect(() => {
    void fetchConversations();
  }, []);

  useEffect(() => {
    const result = getSidebarConversations(conversations);
    setFilteredConversations(result);
  }, [conversations, searchQuery, statusFilter]);

  useEffect(() => {
    if (!activeConversation) {
      lastActiveConvIdRef.current = null;
      return;
    }

    if (activeConversation.id !== lastActiveConvIdRef.current) {
      lastActiveConvIdRef.current = activeConversation.id;
      setMessages([]);
      shouldScrollToBottomRef.current = true;
      void fetchMessages(activeConversation.id);
    }

    const fetchPresence = async () => {
      try {
        const res = await fetch(
          `/admin/chats/${activeConversation.id}/presence`,
        );
        const data = await res.json();
        const list = data.presences || [];
        const anyOnline = list.some((presence: any) => presence.online);
        const latest = list.reduce((acc: string | null, presence: any) => {
          if (!presence.last_seen_at) {
            return acc;
          }
          if (!acc) {
            return presence.last_seen_at;
          }
          return new Date(presence.last_seen_at) > new Date(acc)
            ? presence.last_seen_at
            : acc;
        }, null);

        setPresenceMap((current) => ({
          ...current,
          [activeConversation.id]: { online: anyOnline, last_seen_at: latest },
        }));
      } catch {
        // Presence should not block the inbox.
      }
    };

    void fetchPresence();
  }, [activeConversation]);

  useEffect(() => {
    const container = messagesScrollRef.current;
    if (!container) {
      return;
    }

    if (shouldScrollToBottomRef.current || isNearBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
      shouldScrollToBottomRef.current = false;
    }
  }, [messages]);

  useEffect(() => {
    let reconnectTimer: NodeJS.Timeout;

    const connect = () => {
      const wsBaseUrl = import.meta.env.VITE_CHAT_WS_URL || "ws://localhost:9001";
      const ws = new WebSocket(`${wsBaseUrl.replace(/\/$/, "")}/ws/chat/admin`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            event: "presence.subscribe",
            data: {
              user_type: "admin",
              name: "Nhân viên hỗ trợ",
            },
          }),
        );

        adminHeartbeatRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ event: "presence.heartbeat", data: {} }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);

          if (payload.event === "chat.message.created") {
            const msg = payload.data as ChatMessage;
            window.dispatchEvent(
              new CustomEvent("new_chat_message", { detail: payload }),
            );

            void notifyRef.current(
              {
                id: msg.id,
                conversationId: msg.conversation_id,
                senderLabel:
                  msg.sender_type === "bot"
                    ? translateRef.current("chat.sender.bot")
                    : translateRef.current("chat.sender.customer"),
                content: msg.content || "",
              },
              msg.sender_type !== "admin" &&
                (document.hidden ||
                  selectedConversationIdRef.current !== msg.conversation_id),
            );

            void fetchConversations(false);
          }

          if (payload.event === "conversation.status.updated") {
            const updated = payload.data?.conversation as
              | ChatConversation
              | undefined;
            if (updated) {
              setConversations((current) => {
                const exists = current.some(
                  (conversation) => conversation.id === updated.id,
                );
                return exists
                  ? current.map((conversation) =>
                      conversation.id === updated.id ? updated : conversation,
                    )
                  : [...current, updated];
              });

            }
          }

          if (
            payload.event === "typing.start" &&
            (payload.data?.sender_type || payload.data?.user_type) !== "admin"
          ) {
            const conversationId = payload.conversation_id;
            console.log("typing.start", {
              conversation_id: conversationId,
              sender_type: payload.data?.sender_type || payload.data?.user_type,
            });
            if (conversationId) {
              setCustomerTypingMap((current) => ({
                ...current,
                [conversationId]: true,
              }));
              const existing =
                customerTypingTimeoutsRef.current[conversationId];
              if (existing) {
                window.clearTimeout(existing);
              }
              customerTypingTimeoutsRef.current[conversationId] =
                window.setTimeout(() => {
                  setCustomerTypingMap((current) => ({
                    ...current,
                    [conversationId]: false,
                  }));
                }, 5000);
            }
          }

          if (
            payload.event === "typing.stop" &&
            (payload.data?.sender_type || payload.data?.user_type) !== "admin"
          ) {
            const conversationId = payload.conversation_id;
            console.log("typing.stop", {
              conversation_id: conversationId,
              sender_type: payload.data?.sender_type || payload.data?.user_type,
            });
            if (conversationId) {
              const existing =
                customerTypingTimeoutsRef.current[conversationId];
              if (existing) {
                window.clearTimeout(existing);
                delete customerTypingTimeoutsRef.current[conversationId];
              }
              setCustomerTypingMap((current) => ({
                ...current,
                [conversationId]: false,
              }));
            }
          }

          if (payload.event === "presence.updated") {
            const conversationId = payload.conversation_id;
            const list = payload.data || [];
            const anyOnline = list.some((presence: any) => presence.online);
            const latest = list.reduce((acc: string | null, presence: any) => {
              if (!presence.last_seen_at) {
                return acc;
              }
              if (!acc) {
                return presence.last_seen_at;
              }
              return new Date(presence.last_seen_at) > new Date(acc)
                ? presence.last_seen_at
                : acc;
            }, null);

            setPresenceMap((current) => ({
              ...current,
              [conversationId]: { online: anyOnline, last_seen_at: latest },
            }));
          }
        } catch {
          // Ignore malformed realtime payloads.
        }
      };

      ws.onclose = () => {
        if (adminHeartbeatRef.current) {
          window.clearInterval(adminHeartbeatRef.current);
          adminHeartbeatRef.current = null;
        }
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
      if (adminTypingStopRef.current) {
        window.clearTimeout(adminTypingStopRef.current);
      }
      if (adminHeartbeatRef.current) {
        window.clearInterval(adminHeartbeatRef.current);
        adminHeartbeatRef.current = null;
      }
      Object.values(customerTypingTimeoutsRef.current).forEach((timeoutId) =>
        window.clearTimeout(timeoutId),
      );
      customerTypingTimeoutsRef.current = {};
    };
  }, []);

  useEffect(() => {
    const handleNewMessage = (event: Event) => {
      const payload = (event as CustomEvent).detail;
      const msg = payload.data as ChatMessage;

      if (selectedConversationIdRef.current === msg.conversation_id) {
        setMessages((current) => {
          if (current.some((message) => message.id === msg.id)) {
            return current;
          }

          return sortMessagesByCreatedAt([...current, msg]);
        });
      }
    };

    window.addEventListener("new_chat_message", handleNewMessage);
    return () =>
      window.removeEventListener("new_chat_message", handleNewMessage);
  }, [activeConversation]);

  const handleMessagesScroll = () => {
    const container = messagesScrollRef.current;
    if (!container) {
      return;
    }

    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    isNearBottomRef.current = distanceFromBottom < 180;
  };

  return {
    activeConversation,
    conversations,
    customerTypingMap,
    filteredConversations,
    handleKeyDown,
    handleTextareaInput,
    input,
    loading,
    messages: sortMessagesByCreatedAt(messages),
    messagesEndRef,
    messagesScrollRef,
    presenceMap,
    searchQuery,
    sendMessage,
    selectedConversationId,
    setActiveConversation: selectConversation,
    setSearchQuery,
    setStatusFilter,
    stats,
    statusFilter,
    textareaRef,
    unreadCount,
    updateStatus,
    handleMessagesScroll,
  };
};
