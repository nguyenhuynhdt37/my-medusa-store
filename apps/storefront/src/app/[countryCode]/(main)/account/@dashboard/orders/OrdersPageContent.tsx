"use client"

import { useTranslation } from "react-i18next"
import { HttpTypes } from "@medusajs/types"
import OrderOverview from "@modules/account/components/order-overview"
import Divider from "@modules/common/components/divider"
import TransferRequestForm from "@modules/account/components/transfer-request-form"

function OrdersPageContent({
  orders,
}: {
  orders: HttpTypes.StoreOrder[]
}) {
  const { t } = useTranslation()

  return (
    <div className="w-full" data-testid="orders-page-wrapper">
      <div className="mb-8 flex flex-col gap-y-4">
        <h1 className="text-2xl-semi">{t("account.dashboard.ordersTitle")}</h1>
        <p className="text-base-regular">
          {t("account.dashboard.ordersDescription")}
        </p>
      </div>
      <div>
        <OrderOverview orders={orders} />
        <Divider className="mb-8 mt-8" />
        <TransferRequestForm />
      </div>
    </div>
  )
}

export default OrdersPageContent
