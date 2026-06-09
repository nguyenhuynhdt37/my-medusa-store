"use client"

import { useTranslation } from "react-i18next"
import { resetOnboardingState } from "@lib/data/onboarding"
import { Button, Container, Text } from "@modules/common/components/ui"

export default function OnboardingCta({ orderId }: { orderId: string }) {
  const { t } = useTranslation()

  return (
    <Container className="max-w-4xl h-full bg-ui-bg-subtle w-full">
      <div className="flex flex-col gap-y-4 center p-4 md:items-center">
        <Text className="text-ui-fg-base text-xl">
          {t("onboarding.welcomeText")}
        </Text>
        <Text className="text-ui-fg-subtle text-small-regular">
          {t("onboarding.createProducts")}
        </Text>
        <Button
          className="w-fit"
          size="large"
          onClick={() => resetOnboardingState(orderId)}
        >
          {t("onboarding.viewOrders")}
        </Button>
      </div>
    </Container>
  )
}
