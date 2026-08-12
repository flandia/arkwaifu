import { useLocation, useNavigate } from "react-router";
import { localeNames, type Locale } from "../api";
import { useUi, useUiLanguage, type UiLanguage } from "../i18n";
import { beginNavigation } from "../navigation";

const controlClass =
  "min-h-11 min-w-40 border-2 border-ink bg-surface px-3 py-2 font-bold text-ink focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-ink";

export function LocaleControls({ locale }: { locale: Locale }) {
  const { t } = useUi();
  const { language, languages, changeLanguage } = useUiLanguage();
  const location = useLocation();
  const navigate = useNavigate();

  function changeLocale(nextLocale: Locale) {
    try {
      localStorage.setItem("arkwaifu-locale", nextLocale);
    } catch {
      // Browsing still works when storage is unavailable.
    }
    const parts = location.pathname.split("/");
    parts[1] = nextLocale;
    beginNavigation(() => void navigate(`${parts.join("/")}${location.search}`), "lateral");
  }

  return (
    <div className="grid w-full gap-3 sm:grid-cols-2 min-[74rem]:flex min-[74rem]:w-auto">
      <label className="grid gap-1 text-[0.68rem] font-extrabold tracking-wider uppercase min-[74rem]:grid-cols-[auto_minmax(10rem,1fr)] min-[74rem]:items-center">
        <span>{t("utility.archiveLocale")}</span>
        <select
          className={controlClass}
          name="archive-locale"
          onChange={(event) => changeLocale(event.currentTarget.value as Locale)}
          value={locale}
        >
          {Object.entries(localeNames).map(([value, label]) => (
            <option key={value} value={value}>
              {value} | {label}
            </option>
          ))}
        </select>
      </label>

      <label className="grid gap-1 text-[0.68rem] font-extrabold tracking-wider uppercase min-[74rem]:grid-cols-[auto_minmax(9rem,1fr)] min-[74rem]:items-center">
        <span>{t("utility.uiLanguage")}</span>
        <select
          className={controlClass}
          name="ui-language"
          onChange={(event) => void changeLanguage(event.currentTarget.value as UiLanguage)}
          value={language}
        >
          {languages.map((option) => (
            <option key={option.value} value={option.value}>
              {t(option.labelKey)}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
