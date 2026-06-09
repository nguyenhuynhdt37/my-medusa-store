"use client"

import { useTranslation } from "react-i18next"
import { Button, Heading, Text } from "@modules/common/components/ui"
import LocalizedClientLink from "@modules/common/components/localized-client-link"

const SignInPrompt = () => {
  const { t } = useTranslation()

  return (
    <div className="bg-white flex items-center justify-between">
      <div>
        <Heading level="h2" className="txt-xlarge">
          {t("cart.signInPrompt")}
        </Heading>
        <Text className="txt-medium text-ui-fg-subtle mt-2">
          {t("cart.signInPromptText")}
        </Text>
      </div>
      <div>
        <LocalizedClientLink href="/account">
          <Button variant="secondary" className="h-10" data-testid="sign-in-button">
            {t("common.actions.signIn")}
          </Button>
        </LocalizedClientLink>
      </div>
    </div>
  )
}

export default SignInPrompt
