"use client"

import { HttpTypes } from "@medusajs/types"
import { useTranslation } from "react-i18next"
import { Text } from "@modules/common/components/ui"

type OrderDetailsProps = {
  order: HttpTypes.StoreOrder
  showStatus?: boolean
}

export default function OrderDetails({ order, showStatus }: OrderDetailsProps) {
  const { t } = useTranslation()

  const formatStatus = (str: string) => {
    const formatted = str.split("_").join(" ")
    return formatted.slice(0, 1).toUpperCase() + formatted.slice(1)
  }

  return (
    <div>
      <Text>
        {t("order.orderEmail", { email: order.email })}
      </Text>
      <Text className="mt-2">
        {t("order.orderDate")}:{" "}
        <span data-testid="order-date">
          {new Date(order.created_at).toDateString()}
        </span>
      </Text>
      <Text className="mt-2 text-ui-fg-interactive">
        {t("order.orderNumber")}: <span data-testid="order-id">{order.display_id}</span>
      </Text>

      <div className="flex items-center text-compact-small gap-x-4 mt-4">
        {showStatus && (
          <>
            <Text>
              {t("order.orderStatus")}:{" "}
              <span className="text-ui-fg-subtle " data-testid="order-status">
                {formatStatus(order.fulfillment_status)}
              </span>
            </Text>
            <Text>
              {t("order.paymentStatus")}:{" "}
              <span
                className="text-ui-fg-subtle "
                sata-testid="order-payment-status"
              >
                {formatStatus(order.payment_status)}
              </span>
            </Text>
          </>
        )}
      </div>
    </div>
  )
}
