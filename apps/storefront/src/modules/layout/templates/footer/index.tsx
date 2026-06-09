import FooterContent from "./FooterContent"
import { listCategories } from "@lib/data/categories"
import { listCollections } from "@lib/data/collections"

export default async function Footer() {
  const { collections } = await listCollections({ fields: "*products" })
  const productCategories = await listCategories()

  return <FooterContent collections={collections} categories={productCategories} />
}
