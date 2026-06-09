"use client"

import { Suspense } from "react"
import { HttpTypes } from "@medusajs/types"

import { Locale } from "@lib/data/locales"
import LocalizedClientLink from "@modules/common/components/localized-client-link"
import SideMenu from "@modules/layout/components/side-menu"

type NavProps = {
  regions: HttpTypes.StoreRegion[] | null
  locales: Locale[] | null
  currentLocale: string | null
  cartButton: React.ReactNode
  translations: {
    storeTitle: string
    account: string
    cart: string
  }
}

export default function NavContent({ regions, locales, currentLocale, cartButton, translations }: NavProps) {
  return (
    <div className="sticky top-0 inset-x-0 z-50 group">
      <header className="relative h-16 mx-auto border-b duration-200 bg-white border-ui-border-base">
        <nav className="content-container txt-xsmall-plus text-ui-fg-subtle flex items-center justify-between w-full h-full text-small-regular">
          <div className="flex-1 basis-0 h-full flex items-center">
            <div className="h-full">
              <SideMenu regions={regions} locales={locales} currentLocale={currentLocale} />
            </div>
          </div>

          <div className="flex items-center h-full">
            <LocalizedClientLink
              href="/"
              className="txt-compact-xlarge-plus hover:text-ui-fg-base uppercase"
              data-testid="nav-store-link"
            >
              {translations.storeTitle}
            </LocalizedClientLink>
          </div>

          <div className="flex items-center gap-x-6 h-full flex-1 basis-0 justify-end">
            <div className="hidden small:flex items-center gap-x-6 h-full">
              <LocalizedClientLink
                className="hover:text-ui-fg-base"
                href="/account"
                data-testid="nav-account-link"
              >
                {translations.account}
              </LocalizedClientLink>
            </div>
            <Suspense
              fallback={
                <LocalizedClientLink
                  className="hover:text-ui-fg-base flex gap-2"
                  href="/cart"
                  data-testid="nav-cart-link"
                >
                  {translations.cart} (0)
                </LocalizedClientLink>
              }
            >
              {cartButton}
            </Suspense>
          </div>
        </nav>
      </header>
    </div>
  )
}
