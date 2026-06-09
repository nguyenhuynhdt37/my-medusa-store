import { Avatar, Badge, Button, Heading, Text } from "@medusajs/ui";
import type { ChatConversation, StatusMeta } from "../types";
import {
  formatDate,
  formatMoney,
  getCustomerLabel,
  getInitials,
} from "../utils";

type CustomerProfileProps = {
  activeConversation: ChatConversation | null;
  activeStatusMeta: StatusMeta | null;
  updateStatus: (
    status: "WAITING_ADMIN" | "IN_PROGRESS" | "CLOSED" | "BOT_HANDLED",
  ) => void;
};

export const CustomerProfile = ({
  activeConversation,
  activeStatusMeta,
  updateStatus,
}: CustomerProfileProps) => (
  <aside className="h-full min-h-0 min-w-0 overflow-y-auto border-l border-ui-border-base bg-ui-bg-base p-4">
    <div className="mb-5">
      <Heading level="h2" className="text-base">
        Thông tin khách hàng
      </Heading>
      <Text size="small" className="mt-1 text-ui-fg-muted">
        Hồ sơ hỗ trợ và ngữ cảnh mua hàng
      </Text>
    </div>

    {!activeConversation ? (
      <div className="rounded-md border border-ui-border-base bg-ui-bg-subtle p-4 text-center">
        <Text size="small" className="text-ui-fg-muted">
          Chọn một hội thoại
        </Text>
      </div>
    ) : (
      <div className="flex flex-col gap-5">
        <div className="flex items-center gap-3">
          <Avatar
            src=""
            fallback={getInitials(getCustomerLabel(activeConversation))}
            size="large"
            variant="squared"
          />
          <div className="min-w-0">
            <Text size="small" weight="plus" className="truncate">
              {getCustomerLabel(activeConversation)}
            </Text>
            <Text size="xsmall" className="text-ui-fg-muted">
              {activeConversation.customer_id
                ? "Khách đã đăng nhập"
                : "Khách ẩn danh"}
            </Text>
          </div>
        </div>

        <section className="space-y-3 border-t border-ui-border-base pt-4">
          {activeConversation.customer_id ? (
            <>
              <ProfileRow
                label="Họ tên"
                value={activeConversation.customer_name || "Chưa có dữ liệu"}
              />
              <ProfileRow
                label="Email"
                value={activeConversation.customer_email || "Chưa có dữ liệu"}
              />
              <ProfileRow
                label="Số điện thoại"
                value={
                  activeConversation.admin_metadata?.customer_phone ||
                  "Chưa có dữ liệu"
                }
              />
              <ProfileRow
                label="Tổng đơn hàng"
                value={String(
                  activeConversation.admin_metadata?.total_orders ?? "-",
                )}
              />
              <ProfileRow
                label="Tổng chi tiêu"
                value={formatMoney(activeConversation.admin_metadata?.total_spent)}
              />
              <ProfileRow
                label="Đơn hàng gần nhất"
                value={activeConversation.admin_metadata?.latest_order_id || "-"}
              />
              <ProfileRow
                label="Ngày tham gia"
                value={formatDate(
                  activeConversation.admin_metadata?.joined_at ||
                    activeConversation.created_at,
                )}
              />
            </>
          ) : (
            <>
              <ProfileRow
                label="Guest ID"
                value={activeConversation.guest_id || "-"}
                breakValue
              />
              <ProfileRow
                label="Trình duyệt"
                value={
                  activeConversation.admin_metadata?.browser || "Chưa thu thập"
                }
              />
              <ProfileRow
                label="Thiết bị"
                value={
                  activeConversation.admin_metadata?.device || "Chưa thu thập"
                }
              />
              <ProfileRow
                label="Thời gian truy cập"
                value={formatDate(
                  activeConversation.admin_metadata?.first_seen_at ||
                    activeConversation.created_at,
                )}
              />
              <ProfileRow
                label="Quốc gia/IP"
                value={
                  activeConversation.admin_metadata?.country ||
                  activeConversation.admin_metadata?.ip ||
                  "Chưa thu thập"
                }
              />
            </>
          )}
        </section>

        <section className="space-y-3 border-t border-ui-border-base pt-4">
          <div>
            <Text size="xsmall" className="text-ui-fg-muted">
              Trạng thái
            </Text>
            <div className="mt-2">
              <Badge size="small" color={activeStatusMeta?.badgeColor || "grey"}>
                {activeStatusMeta?.label}
              </Badge>
            </div>
            <Text size="small" className="mt-2 text-ui-fg-muted">
              {activeStatusMeta?.description}
            </Text>
          </div>
          {activeConversation.escalation_reason && (
            <ProfileRow
              label="Lý do chuyển nhân viên"
              value={activeConversation.escalation_reason}
            />
          )}
        </section>

        <section className="space-y-2 border-t border-ui-border-base pt-4">
          {activeConversation.status === "WAITING_ADMIN" && (
            <Button
              variant="primary"
              className="w-full"
              onClick={() => updateStatus("IN_PROGRESS")}
            >
              Tiếp nhận hỗ trợ
            </Button>
          )}
          {activeConversation.status === "IN_PROGRESS" && (
            <>
              <Button
                variant="secondary"
                className="w-full"
                onClick={() => updateStatus("BOT_HANDLED")}
              >
                Giao lại Bot
              </Button>
              <Button
                variant="transparent"
                className="w-full"
                onClick={() => updateStatus("CLOSED")}
              >
                Kết thúc hỗ trợ
              </Button>
            </>
          )}
        </section>
      </div>
    )}
  </aside>
);

const ProfileRow = ({
  label,
  value,
  breakValue = false,
}: {
  label: string;
  value: string;
  breakValue?: boolean;
}) => (
  <div>
    <Text size="xsmall" className="text-ui-fg-muted">
      {label}
    </Text>
    <Text
      size="small"
      className={breakValue ? "break-all text-ui-fg-base" : "text-ui-fg-base"}
    >
      {value}
    </Text>
  </div>
);
