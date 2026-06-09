import { Container, Heading, Text } from "@medusajs/ui";
import type { ChatConversation, ChatStats, Translate } from "../types";

type ChatReportsProps = {
  conversations: ChatConversation[];
  stats: ChatStats | null;
  tt: Translate;
};

export const ChatReports = ({
  conversations,
  stats,
  tt,
}: ChatReportsProps) => {
  const waitingCount = conversations.filter(
    (conversation) => conversation.status === "WAITING_ADMIN",
  ).length;

  return (
    <Container className="flex h-[calc(100vh-170px)] flex-col overflow-hidden border border-ui-border-base bg-ui-bg-base p-0">
      <div className="border-b border-ui-border-base px-6 py-5">
        <Heading level="h1" className="text-xl">
          {tt("chat.reports.title")}
        </Heading>
        <Text size="small" className="mt-1 text-ui-fg-muted">
          {tt("chat.reports.description")}
        </Text>
      </div>
      <div className="grid grid-cols-3 gap-px bg-ui-border-base">
        {[
          [
            tt("chat.stats.total"),
            stats?.total_conversations ?? conversations.length,
          ],
          [tt("chat.stats.aiHandled"), stats?.ai_handled_conversations ?? 0],
          [tt("chat.stats.escalated"), stats?.escalated_conversations ?? 0],
          [tt("chat.stats.aiRate"), `${stats?.ai_resolution_rate ?? 0}%`],
          [
            tt("chat.stats.escTime"),
            stats?.average_escalation_time_minutes != null
              ? `${stats.average_escalation_time_minutes}m`
              : "-",
          ],
          [
            tt("chat.stats.humanTime"),
            stats?.human_resolution_time_minutes != null
              ? `${stats.human_resolution_time_minutes}m`
              : "-",
          ],
          [tt("chat.stats.waiting"), waitingCount],
        ].map(([label, value]) => (
          <div key={label} className="min-h-[120px] bg-ui-bg-base p-5">
            <Text size="small" className="text-ui-fg-muted">
              {label}
            </Text>
            <Text size="xlarge" weight="plus" className="mt-3 text-ui-fg-base">
              {value}
            </Text>
          </div>
        ))}
      </div>
    </Container>
  );
};
