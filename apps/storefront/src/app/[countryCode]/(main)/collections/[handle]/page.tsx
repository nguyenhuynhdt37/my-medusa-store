import { Metadata } from "next"
import { notFound } from "next/navigation"

import { rethrowNextInternalError } from "@lib/util/next-errors"

import { getCollectionByHandle, listCollections } from "@lib/data/collections"
import { listRegions } from "@lib/data/regions"
import { StoreCollection, StoreRegion } from "@medusajs/types"
import CollectionTemplate from "@modules/collections/templates"
import { SortOptions } from "@modules/store/components/refinement-list/sort-products"

type Props = {
  params: Promise<{ handle: string; countryCode: string }>
  searchParams: Promise<{
    page?: string
    sortBy?: SortOptions
  }>
}

export const PRODUCT_LIMIT = 12

export async function generateStaticParams() {
  try {
    const { collections } = await listCollections({
      fields: "*products",
    })

    if (!collections.length) {
      return []
    }

    const countryCodes = await listRegions().then(
      (regions: StoreRegion[]) =>
        regions
          ?.map((r) => r.countries?.map((c) => c.iso_2))
          .flat()
          .filter(Boolean) as string[]
    )

    const collectionHandles = collections.map(
      (collection: StoreCollection) => collection.handle
    )

    return countryCodes
      ?.map((countryCode: string) =>
        collectionHandles.map((handle: string | undefined) => ({
          countryCode,
          handle,
        }))
      )
      .flat()
  } catch (error) {
    console.warn(
      `Skipping static collection generation: ${
        error instanceof Error ? error.message : "Medusa is unavailable"
      }.`
    )

    return []
  }
}

export async function generateMetadata(props: Props): Promise<Metadata> {
  const params = await props.params
  let collection = null

  try {
    collection = await getCollectionByHandle(params.handle)
  } catch (error) {
    rethrowNextInternalError(error)
    console.error(
      `[Collection generateMetadata] Error fetching collection "${params.handle}":`,
      error
    )
  }

  if (!collection) {
    return {
      title: "Collection Not Found | Medusa Store",
      description: "Collection details are currently unavailable.",
    }
  }

  const metadata = {
    title: `${collection.title} | Medusa Store`,
    description: `${collection.title} collection`,
  } as Metadata

  return metadata
}

export default async function CollectionPage(props: Props) {
  const searchParams = await props.searchParams
  const params = await props.params
  const { sortBy, page } = searchParams

  let collection = null
  try {
    collection = await getCollectionByHandle(params.handle)
  } catch (error) {
    rethrowNextInternalError(error)
    console.error(
      `[CollectionPage] Error fetching collection with handle "${params.handle}":`,
      error
    )
  }

  if (!collection) {
    notFound()
  }

  return (
    <CollectionTemplate
      collection={collection}
      page={page}
      sortBy={sortBy}
      countryCode={params.countryCode}
    />
  )
}
