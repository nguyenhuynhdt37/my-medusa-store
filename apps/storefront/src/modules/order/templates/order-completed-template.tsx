import { cookies as nextCookies } from "next/headers"
import OnboardingCta from "@modules/order/components/onboarding-cta"
import OrderCompletedContent from "./OrderCompletedContent"
import { HttpTypes } from "@medusajs/types"

type OrderCompletedTemplateProps = {
  order: HttpTypes.StoreOrder
}

export default async function OrderCompletedTemplate({
  order,
}: OrderCompletedTemplateProps) {
  const cookies = await nextCookies()
  const isOnboarding = cookies.get("_medusa_onboarding")?.value === "true"

  return (
    <>
      {isOnboarding && <OnboardingCta orderId={order.id} />}
      <OrderCompletedContent order={order} />
    </>
  )
}
