"use client"

import { useTranslation } from "react-i18next"
import { HttpTypes } from "@medusajs/types"
import AddressBook from "@modules/account/components/address-book"

function AddressesPageContent({
  customer,
  region,
}: {
  customer: HttpTypes.StoreCustomer
  region: HttpTypes.StoreRegion
}) {
  const { t } = useTranslation()

  return (
    <div className="w-full" data-testid="addresses-page-wrapper">
      <div className="mb-8 flex flex-col gap-y-4">
        <h1 className="text-2xl-semi">{t("account.dashboard.addressesTitle")}</h1>
        <p className="text-base-regular">
          {t("account.dashboard.addressesDescription")}
        </p>
      </div>
      <AddressBook customer={customer} region={region} />
    </div>
  )
}

export default AddressesPageContent
