import { useEffect, useRef, type ReactNode } from "react";
import { useParams } from "react-router";
import { useUi } from "../i18n";
import { isLocale, TransitionLink } from "../navigation";
import { LocaleControls } from "./LocaleControls";
import { SiteNavigation } from "./SiteNavigation";

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useUi();
  const { locale: rawLocale } = useParams();
  const locale = isLocale(rawLocale) ? rawLocale : "CN";
  const dialogRef = useRef<HTMLDialogElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 56.001rem)");
    const closeOnDesktop = (event: MediaQueryListEvent) => {
      if (event.matches) dialogRef.current?.close();
    };
    desktop.addEventListener("change", closeOnDesktop);
    return () => desktop.removeEventListener("change", closeOnDesktop);
  }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const restoreMenuFocus = () => window.setTimeout(() => menuButtonRef.current?.focus(), 0);
    dialog.addEventListener("close", restoreMenuFocus);
    return () => dialog.removeEventListener("close", restoreMenuFocus);
  }, []);

  function openMenu() {
    dialogRef.current?.showModal();
  }

  function closeMenu() {
    dialogRef.current?.close();
  }

  return (
    <>
      <a
        className="fixed top-3 left-3 z-[1000] -translate-y-[160%] bg-signal px-4 py-3 font-extrabold text-ink focus:translate-y-0"
        href="#main-content"
      >
        {t("navigation.skipToContent")}
      </a>
      <div className="min-h-screen bg-paper pt-[calc(4rem+env(safe-area-inset-top))] min-[56.001rem]:grid min-[56.001rem]:grid-cols-[20rem_minmax(0,1fr)] min-[56.001rem]:pt-0">
        <aside
          className="scrollbar-none sticky top-0 hidden h-screen overflow-y-auto overscroll-contain border-r-2 border-ink min-[56.001rem]:block"
          style={{ viewTransitionName: "persistent-nav" }}
        >
          <SiteNavigation locale={locale} />
        </aside>

        <header
          className="fixed top-0 right-0 left-0 z-50 grid h-[calc(4rem+env(safe-area-inset-top))] grid-cols-[4rem_minmax(0,1fr)_4rem] items-end border-b-2 border-ink bg-surface pt-[env(safe-area-inset-top)] min-[56.001rem]:hidden"
          style={{ viewTransitionName: "persistent-mobile-header" }}
        >
          <button
            aria-label={t("navigation.open")}
            className="grid h-16 w-16 place-content-center gap-1 border-0 border-r-2 border-ink bg-brand text-white hover:bg-ink"
            onClick={openMenu}
            ref={menuButtonRef}
            type="button"
          >
            <span className="block h-0.5 w-6 bg-current" aria-hidden="true" />
            <span className="block h-0.5 w-6 bg-current" aria-hidden="true" />
            <span className="block h-0.5 w-6 bg-current" aria-hidden="true" />
          </button>
          <TransitionLink
            className="grid h-16 place-items-center overflow-hidden px-4 font-display text-xl tracking-widest no-underline"
            to={`/${locale}`}
            translate="no"
          >
            ARKWAIFU
          </TransitionLink>
          <span className="grid h-16 place-items-center border-l-2 border-ink font-mono text-xs font-extrabold">
            {locale}
          </span>
        </header>

        {/* oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions -- The native modal supports Escape; this only adds pointer backdrop dismissal. */}
        <dialog
          aria-label={t("navigation.siteLabel")}
          className="m-0 hidden h-dvh max-h-none w-[min(88vw,22rem)] max-w-none overflow-hidden border-0 border-r-2 border-ink bg-ink p-0 text-white open:block"
          onClick={(event) => {
            if (event.target === event.currentTarget) closeMenu();
          }}
          ref={dialogRef}
        >
          <button
            aria-label={t("navigation.close")}
            className="absolute top-[max(0.75rem,env(safe-area-inset-top))] right-3 z-10 grid size-11 place-items-center border-2 border-ink bg-signal text-2xl leading-none text-ink hover:bg-white"
            onClick={closeMenu}
            type="button"
          >
            <span aria-hidden="true">×</span>
          </button>
          <div className="scrollbar-none h-full overflow-y-auto overscroll-contain pb-[env(safe-area-inset-bottom)]">
            <SiteNavigation locale={locale} onNavigate={closeMenu} />
          </div>
        </dialog>

        <div className="min-w-0 bg-paper">
          <section
            aria-label={t("utility.statusAndLocale")}
            className="grid min-h-18 gap-3 border-b-2 border-ink bg-surface px-[max(1rem,env(safe-area-inset-left))] py-3 min-[74rem]:flex min-[74rem]:items-center min-[74rem]:justify-between min-[74rem]:px-10"
            style={{ viewTransitionName: "persistent-utility" }}
          >
            <p className="hidden items-center gap-2 font-mono text-xs tracking-wider uppercase min-[74rem]:flex">
              <span className="size-3 border-2 border-ink bg-brand" aria-hidden="true" />
              {t("utility.publicArchive")}
            </p>
            <LocaleControls locale={locale} />
          </section>
          <main className="min-h-[calc(100vh-12rem)]" id="main-content" tabIndex={-1}>
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
