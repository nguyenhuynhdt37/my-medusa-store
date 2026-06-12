import { Metadata } from "next"
import { notFound } from "next/navigation"

import { rethrowNextInternalError } from "@lib/util/next-errors"
import { listProducts } from "@lib/data/products"
import { getRegion, listRegions } from "@lib/data/regions"
import ProductTemplate from "@modules/products/templates"
import { HttpTypes } from "@medusajs/types"

type Props = {
  params: Promise<{ countryCode: string; handle: string }>
  searchParams: Promise<{ v_id?: string }>
}

export async function generateStaticParams() {
  try {
    const countryCodes = await listRegions().then((regions) =>
      regions?.map((r) => r.countries?.map((c) => c.iso_2)).flat()
    )

    if (!countryCodes) {
      return []
    }

    const promises = countryCodes.map(async (country) => {
      const { response } = await listProducts({
        countryCode: country,
        queryParams: { limit: 100, fields: "handle" },
      })

      return {
        country,
        products: response.products,
      }
    })

    const countryProducts = await Promise.all(promises)

    return countryProducts
      .flatMap((countryData) =>
        countryData.products.map((product) => ({
          countryCode: countryData.country,
          handle: product.handle,
        }))
      )
      .filter((param) => param.handle)
  } catch (error) {
    console.error(
      `Failed to generate static paths for product pages: ${
        error instanceof Error ? error.message : "Unknown error"
      }.`
    )
    return []
  }
}

function getImagesForVariant(
  product: HttpTypes.StoreProduct,
  selectedVariantId?: string
) {
  if (!selectedVariantId || !product.variants) {
    return product.images
  }

  const variant = product.variants!.find((v) => v.id === selectedVariantId)
  if (!variant || !variant.images?.length) {
    return product.images
  }

  const imageIdsMap = new Map(variant.images!.map((i) => [i.id, true]))
  return product.images?.filter((i) => imageIdsMap.has(i.id)) ?? null
}

export async function generateMetadata(props: Props): Promise<Metadata> {
  const params = await props.params
  const { handle } = params

  let region = null
  let product = null

  try {
    region = await getRegion(params.countryCode)
    if (region) {
      product = await listProducts({
        countryCode: params.countryCode,
        queryParams: { handle },
      }).then(({ response }) => response.products[0])
    }
  } catch (error) {
    rethrowNextInternalError(error)
    console.error(
      `[Product generateMetadata] Error fetching data for product "${handle}":`,
      error
    )
  }

  if (!product) {
    return {
      title: "Product Not Found | Medusa Store",
      description: "Product details are currently unavailable.",
    }
  }

  return {
    title: `${product.title} | Medusa Store`,
    description: `${product.title}`,
    openGraph: {
      title: `${product.title} | Medusa Store`,
      description: `${product.title}`,
      images: product.thumbnail ? [product.thumbnail] : [],
    },
  }
}

export default async function ProductPage(props: Props) {
  const params = await props.params
  const searchParams = await props.searchParams

  const selectedVariantId = searchParams.v_id

  let region = null
  try {
    region = await getRegion(params.countryCode)
  } catch (error) {
    rethrowNextInternalError(error)
    console.error(
      `[ProductPage] Error fetching region for country code "${params.countryCode}":`,
      error
    )
  }

  if (!region) {
    notFound()
  }

  let pricedProduct = null
  try {
    pricedProduct = await listProducts({
      countryCode: params.countryCode,
      queryParams: { handle: params.handle },
    }).then(({ response }) => response.products[0])
  } catch (error) {
    rethrowNextInternalError(error)
    console.error(
      `[ProductPage] Error fetching product with handle "${params.handle}":`,
      error
    )
  }

  if (!pricedProduct) {
    notFound()
  }

  const images = getImagesForVariant(pricedProduct, selectedVariantId)

  return (
    <ProductTemplate
      product={pricedProduct}
      region={region}
      countryCode={params.countryCode}
      images={images ?? []}
    />
  )
}
