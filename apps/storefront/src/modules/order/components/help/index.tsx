"use client"

import { useTranslation } from "react-i18next"
import { Heading } from "@modules/common/components/ui"
import LocalizedClientLink from "@modules/common/components/localized-client-link"

export default function Help() {
  const { t } = useTranslation()

  return (
    <div className="mt-6">
      <Heading className="text-base-semi">{t("order.help")}</Heading>
      <div className="text-base-regular my-2">
        <ul className="gap-y-2 flex flex-col">
          <li>
            <LocalizedClientLink href="/contact">{t("order.helpContact")}</LocalizedClientLink>
          </li>
          <li>
            <LocalizedClientLink href="/contact">
              {t("order.helpReturns")}
            </LocalizedClientLink>
          </li>
        </ul>
      </div>
    </div>
  )
}
