import i18n from "i18next";
import { initReactI18next, useTranslation } from "react-i18next";
import { defaultNamespace, resources } from "./resources";

export type UiLanguage = keyof typeof resources;

export const UI_LANGUAGE_STORAGE_KEY = "arkwaifu-ui-language";

export const uiLanguages = [
  { value: "zh-CN", labelKey: "languages.zhCN" },
  { value: "en", labelKey: "languages.en" },
] as const;

export function isUiLanguage(value: unknown): value is UiLanguage {
  return value === "zh-CN" || value === "en";
}

function initialUiLanguage(): UiLanguage {
  try {
    const saved = localStorage.getItem(UI_LANGUAGE_STORAGE_KEY);
    if (isUiLanguage(saved)) return saved;
  } catch {
    // Chinese remains the default when storage is unavailable.
  }
  return "zh-CN";
}

const initialLanguage = initialUiLanguage();

void i18n.use(initReactI18next).init({
  resources,
  defaultNS: defaultNamespace,
  fallbackLng: "zh-CN",
  supportedLngs: Object.keys(resources),
  lng: initialLanguage,
  initAsync: false,
  returnNull: false,
  interpolation: { escapeValue: false },
});

function setDocumentLanguage(language: string): void {
  document.documentElement.lang = isUiLanguage(language) ? language : "zh-CN";
}

setDocumentLanguage(initialLanguage);
i18n.on("languageChanged", setDocumentLanguage);

export function useUi() {
  return useTranslation();
}

export function useUiLanguage() {
  const translation = useTranslation();
  const language = isUiLanguage(translation.i18n.resolvedLanguage)
    ? translation.i18n.resolvedLanguage
    : "zh-CN";

  async function changeLanguage(nextLanguage: UiLanguage): Promise<void> {
    try {
      localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, nextLanguage);
    } catch {
      // Language switching still works when storage is unavailable.
    }
    await translation.i18n.changeLanguage(nextLanguage);
  }

  return {
    t: translation.t,
    i18n: translation.i18n,
    ready: translation.ready,
    language,
    languages: uiLanguages,
    changeLanguage,
  };
}

export { i18n };
