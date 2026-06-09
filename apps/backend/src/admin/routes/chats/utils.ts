import type {
  ChatConversation,
  ChatMessage,
  ChatStatus,
  StatusMeta,
  Translate,
} from "./types";

export const CHAT_FALLBACKS: Record<string, string> = {
  "chat.sidebar.title": "Live Chat",
  "chat.sidebar.searchPlaceholder": "Tìm hội thoại hoặc khách hàng",
  "chat.sidebar.noConversations": "Không có hội thoại phù hợp",
  "chat.tabs.inbox": "Hộp thư",
  "chat.tabs.reports": "Báo cáo Chat",
  "chat.reports.title": "Báo cáo Chat",
  "chat.reports.description": "Hiệu quả xử lý giữa AI và nhân viên hỗ trợ.",
  "chat.stats.total": "Tổng chat",
  "chat.stats.aiHandled": "Bot xử lý",
  "chat.stats.escalated": "Chuyển nhân viên",
  "chat.stats.aiRate": "Tỷ lệ AI xử lý",
  "chat.stats.escTime": "Thời gian chuyển trung bình",
  "chat.stats.humanTime": "Thời gian xử lý bởi nhân viên",
  "chat.stats.waiting": "Khách đang chờ",
  "chat.empty.title": "Chọn một hội thoại",
  "chat.empty.description": "Nội dung trao đổi sẽ hiển thị tại đây.",
  "chat.notifications.baseTitle": "Medusan Chat",
  "chat.notifications.notificationTitle": "Medusan",
  "chat.sender.bot": "Trợ lý Medusan",
  "chat.sender.guest": "Khách hàng",
  "chat.sender.you": "Nhân viên hỗ trợ",
  "chat.sender.customer": "Khách hàng",
  "chat.sender.unknown": "Khách hàng",
  "chat.error.panelTitle": "Không thể hiển thị khung chat",
  "chat.error.panelDescription":
    "Có lỗi khi render khung chat. Chi tiết đã được ghi trong console.",
  "chat.error.loadConversations": "Không thể tải danh sách chat",
  "chat.error.loadMessages": "Không thể tải tin nhắn",
  "chat.error.sendMessage": "Gửi tin nhắn thất bại",
  "chat.error.updateStatus": "Không thể cập nhật trạng thái",
  "chat.success.updateStatus": "Cập nhật trạng thái thành công",
  "chat.presence.online": "Đang hoạt động",
  "chat.presence.offline": "Chưa có trạng thái",
  "chat.presence.justNow": "vừa xong",
  "chat.presence.minutesAgo": "{{count}} phút trước",
  "chat.presence.hoursAgo": "{{count}} giờ trước",
  "chat.presence.daysAgo": "{{count}} ngày trước",
  "chat.actions.takeOver": "Tiếp nhận hỗ trợ",
  "chat.actions.returnToBot": "Giao lại Bot",
  "chat.actions.closeSession": "Kết thúc hỗ trợ",
  "chat.actions.reopenSession": "Mở lại",
  "chat.messages.noMessages": "Chưa có tin nhắn nào",
  "chat.messages.placeholder": "Nhập phản hồi cho khách hàng",
  "chat.messages.botProcessing": "AI đang xử lý hội thoại này.",
  "chat.messages.waitingForAdmin": "Tiếp nhận hỗ trợ để bắt đầu trả lời.",
  "chat.messages.sessionClosed": "Hội thoại đã kết thúc.",
  "chat.messages.imageAlt": "Hình ảnh trong chat",
  "chat.status.botHandled.label": "Bot đang hỗ trợ",
  "chat.status.botHandled.short": "Bot",
  "chat.status.botHandled.description": "AI đang phụ trách hội thoại này.",
  "chat.status.waitingAdmin.label": "Chờ nhân viên",
  "chat.status.waitingAdmin.short": "Chờ hỗ trợ",
  "chat.status.waitingAdmin.description": "Khách đang chờ nhân viên tiếp nhận.",
  "chat.status.inProgress.label": "Nhân viên đang hỗ trợ",
  "chat.status.inProgress.short": "Nhân viên",
  "chat.status.inProgress.description": "Nhân viên đang hỗ trợ khách hàng.",
  "chat.status.closed.label": "Đã kết thúc",
  "chat.status.closed.short": "Đã kết thúc",
  "chat.status.closed.description": "Phiên hỗ trợ đã kết thúc.",
  "chat.status.resolved.label": "Đã kết thúc",
  "chat.status.resolved.short": "Đã kết thúc",
  "chat.status.resolved.description": "Phiên hỗ trợ đã kết thúc.",
  "common.loading": "Đang tải...",
  "common.error": "Lỗi",
  "common.success": "Thành công",
};

export const makeTranslate = (translate: any): Translate => {
  return (key, fallbackOrOptions) => {
    const fallback =
      typeof fallbackOrOptions === "string"
        ? fallbackOrOptions
        : CHAT_FALLBACKS[key] || key;
    const options =
      typeof fallbackOrOptions === "object"
        ? { ...fallbackOrOptions, defaultValue: fallback }
        : fallback;
    const translated = translate(key, options);
    return translated === key ? fallback : translated;
  };
};

export const sortMessagesByCreatedAt = (items: ChatMessage[]) => {
  return [...items].sort(
    (a, b) =>
      new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );
};

export const isAdminVisibleConversation = (conversation: ChatConversation) => {
  return ["WAITING_ADMIN", "IN_PROGRESS", "CLOSED", "RESOLVED"].includes(
    conversation.status,
  );
};

export const getStatusMeta = (
  status: ChatStatus,
  tt: Translate,
): StatusMeta => {
  switch (status) {
    case "BOT_HANDLED":
      return {
        label: tt("chat.status.botHandled.label"),
        shortLabel: tt("chat.status.botHandled.short"),
        description: tt("chat.status.botHandled.description"),
        badgeColor: "green",
        dotClassName: "bg-ui-fg-success",
      };
    case "WAITING_ADMIN":
      return {
        label: tt("chat.status.waitingAdmin.label"),
        shortLabel: tt("chat.status.waitingAdmin.short"),
        description: tt("chat.status.waitingAdmin.description"),
        badgeColor: "orange",
        dotClassName: "bg-ui-fg-warning",
      };
    case "IN_PROGRESS":
      return {
        label: tt("chat.status.inProgress.label"),
        shortLabel: tt("chat.status.inProgress.short"),
        description: tt("chat.status.inProgress.description"),
        badgeColor: "blue",
        dotClassName: "bg-ui-fg-interactive",
      };
    case "CLOSED":
    case "RESOLVED":
      return {
        label:
          status === "CLOSED"
            ? tt("chat.status.closed.label")
            : tt("chat.status.resolved.label"),
        shortLabel:
          status === "CLOSED"
            ? tt("chat.status.closed.short")
            : tt("chat.status.resolved.short"),
        description:
          status === "CLOSED"
            ? tt("chat.status.closed.description")
            : tt("chat.status.resolved.description"),
        badgeColor: "grey",
        dotClassName: "bg-ui-fg-muted",
      };
  }
};

export const getCustomerLabel = (conversation: ChatConversation) => {
  if (conversation.customer_name) {
    return conversation.customer_name;
  }

  if (conversation.customer_email) {
    return conversation.customer_email;
  }

  if (conversation.customer_id) {
    return `Khách ${conversation.customer_id.slice(-6).toUpperCase()}`;
  }

  const guestSuffix = (conversation.guest_id || conversation.id)
    .slice(-4)
    .toUpperCase();
  return `Khách #${guestSuffix}`;
};

export const getInitials = (name: string) => {
  const words = name.trim().split(/\s+/);
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }

  return `${words[0][0]}${words[words.length - 1][0]}`.toUpperCase();
};

export const formatTime = (iso?: string | null) => {
  if (!iso) {
    return "";
  }

  return new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
  });
};

export const formatDate = (iso?: string | null) => {
  if (!iso) {
    return "-";
  }

  return new Date(iso).toLocaleDateString("vi-VN");
};

export const formatMoney = (value?: number | null) => {
  if (!value) {
    return "-";
  }

  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(value);
};

export const formatLastSeen = (
  iso: string | null | undefined,
  tt: Translate,
) => {
  if (!iso) {
    return "";
  }

  const delta = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (delta < 60) return tt("chat.presence.justNow");
  if (delta < 3600) {
    return tt("chat.presence.minutesAgo", { count: Math.floor(delta / 60) });
  }
  if (delta < 86400) {
    return tt("chat.presence.hoursAgo", { count: Math.floor(delta / 3600) });
  }
  return tt("chat.presence.daysAgo", { count: Math.floor(delta / 86400) });
};
