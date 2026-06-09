import i18n from "i18next"
import { initReactI18next } from "react-i18next"
import LanguageDetector from "i18next-browser-languagedetector"

import vi from "./locales/vi.json"
import en from "./locales/en.json"

const LANGUAGE_COOKIE = "_medusa_locale"

const resources = {
  vi: { translation: vi },
  en: { translation: en },
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    supportedLngs: ["vi", "en"],
    fallbackLng: "en",
    defaultNS: "translation",
    ns: ["translation"],
    detection: {
      order: ["cookie", "localStorage", "navigator"],
      lookupCookie: LANGUAGE_COOKIE,
      lookupLocalStorage: LANGUAGE_COOKIE,
      caches: ["cookie", "localStorage"],
    },
    interpolation: {
      escapeValue: false,
    },
  })

export default i18n
export { LANGUAGE_COOKIE }
