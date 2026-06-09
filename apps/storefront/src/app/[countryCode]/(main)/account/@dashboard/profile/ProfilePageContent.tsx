"use client"

import { useTranslation } from "react-i18next"
import { HttpTypes } from "@medusajs/types"
import Divider from "@modules/common/components/divider"
import ProfilePhone from "@modules/account//components/profile-phone"
import ProfileBillingAddress from "@modules/account/components/profile-billing-address"
import ProfileEmail from "@modules/account/components/profile-email"
import ProfileName from "@modules/account/components/profile-name"

function ProfilePageContent({
  customer,
  regions,
}: {
  customer: HttpTypes.StoreCustomer
  regions: HttpTypes.StoreRegion[]
}) {
  const { t } = useTranslation()

  return (
    <div className="w-full" data-testid="profile-page-wrapper">
      <div className="mb-8 flex flex-col gap-y-4">
        <h1 className="text-2xl-semi">{t("account.dashboard.profileTitle")}</h1>
        <p className="text-base-regular">
          {t("account.dashboard.profileDescription")}
        </p>
      </div>
      <div className="flex flex-col gap-y-8 w-full">
        <ProfileName customer={customer} />
        <Divider />
        <ProfileEmail customer={customer} />
        <Divider />
        <ProfilePhone customer={customer} />
        <Divider />
        <ProfileBillingAddress customer={customer} regions={regions} />
      </div>
    </div>
  )
}

export default ProfilePageContent
