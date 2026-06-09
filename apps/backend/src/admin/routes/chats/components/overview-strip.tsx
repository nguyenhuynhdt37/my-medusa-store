import { Badge, Heading, Text } from "@medusajs/ui";
import type { ChatConversation, ChatStats, Translate } from "../types";

type OverviewStripProps = {
  conversations: ChatConversation[];
  stats: ChatStats | null;
  tt: Translate;
};

export const OverviewStrip = ({
  conversations,
  stats,
  tt,
}: OverviewStripProps) => {
  const waitingCount = conversations.filter(
    (conversation) => conversation.status === "WAITING_ADMIN",
  ).length;
  const inProgressCount = conversations.filter(
    (conversation) => conversation.status === "IN_PROGRESS",
  ).length;
  const totalConversations = stats?.total_conversations ?? conversations.length;

  return (
    <div className="shrink-0 rounded-md border border-ui-border-base bg-ui-bg-base px-4 py-3">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Heading level="h1" className="text-lg">
            Tổng quan
          </Heading>
          <Badge size="small" color="green">
            Online
          </Badge>
        </div>
        <Badge size="small" color={waitingCount > 0 ? "orange" : "green"}>
          {waitingCount > 0 ? "Có khách đang chờ" : "Không có hàng chờ"}
        </Badge>
      </div>

      <div className="mt-3 grid grid-cols-5 gap-2">
        <MetricCard label="Chờ tiếp nhận" value={waitingCount} />
        <MetricCard label="Đang hỗ trợ" value={inProgressCount} />
        <MetricCard
          label={tt("chat.stats.aiRate")}
          value={`${stats?.ai_resolution_rate ?? 0}%`}
        />
        <MetricCard label="Tổng hội thoại" value={totalConversations} />
        <MetricCard
          label="Thời gian tiếp nhận"
          value={
            stats?.average_escalation_time_minutes != null
              ? `${stats.average_escalation_time_minutes}m`
              : "-"
          }
        />
      </div>
    </div>
  );
};

const MetricCard = ({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) => (
  <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle px-3 py-2">
    <Text size="xsmall" className="truncate text-ui-fg-muted">
      {label}
    </Text>
    <Text size="large" weight="plus" className="mt-1 text-ui-fg-base">
      {value}
    </Text>
  </div>
);
