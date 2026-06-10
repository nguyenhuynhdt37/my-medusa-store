import { getLocale } from "@lib/data/locale-actions"
import vi from "./locales/vi.json"
import en from "./locales/en.json"

type TranslationValue = string | { [key: string]: TranslationValue }

const translations: Record<string, TranslationValue> = {
  vi,
  en,
}

export async function tServer(key: string, params?: Record<string, string | number>): Promise<string> {
  const locale = (await getLocale()) || "en"
  const localeData = translations[locale] || translations["en"]

  const keys = key.split(".")
  let value: TranslationValue | undefined = localeData

  for (const k of keys) {
    if (value && typeof value === "object" && k in value) {
      value = value[k]
    } else {
      return key
    }
  }

  if (typeof value !== "string") {
    return key
  }

  if (params) {
    return value.replace(/\{\{(\w+)\}\}/g, (_, k) => String(params[k] ?? `{{${k}}}`))
  }

  return value
}
