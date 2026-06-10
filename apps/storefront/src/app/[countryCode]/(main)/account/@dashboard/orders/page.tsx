import { Metadata } from "next"

import { notFound } from "next/navigation"
import { listOrders } from "@lib/data/orders"
import OrdersPageContent from "./OrdersPageContent"

export const metadata: Metadata = {
  title: "Orders",
  description: "Overview of your previous orders.",
}

export default async function Orders() {
  const orders = await listOrders()

  if (!orders) {
    notFound()
  }

  return <OrdersPageContent orders={orders} />
}
