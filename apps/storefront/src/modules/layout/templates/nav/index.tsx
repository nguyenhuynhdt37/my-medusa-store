import NavContent from "./NavContent"
import { listLocales } from "@lib/data/locales"
import { getLocale } from "@lib/data/locale-actions"
import { listRegions } from "@lib/data/regions"
import { StoreRegion } from "@medusajs/types"
import CartButton from "@modules/layout/components/cart-button"
import { tServer } from "../../../../lib/i18n/server"

export default async function Nav() {
  const [regions, locales, currentLocale, storeTitle, account, cart] = await Promise.all([
    listRegions().then((regions: StoreRegion[]) => regions),
    listLocales(),
    getLocale(),
    tServer("common.store.title"),
    tServer("common.nav.account"),
    tServer("common.nav.cart"),
  ])

  return (
    <NavContent
      regions={regions}
      locales={locales}
      currentLocale={currentLocale}
      cartButton={<CartButton />}
      translations={{
        storeTitle,
        account,
        cart,
      }}
    />
  )
}
