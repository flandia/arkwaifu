import { useLocation } from "react-router";
import type { Locale } from "../api";
import { useUi } from "../i18n";
import { TransitionLink, useStorySections } from "../navigation";
import { Eyebrow } from "../shared/ui";

const logoUrl = "/arkwaifu_phantom@0.25x.png";
const repositoryUrl = "https://github.com/flandia/arkwaifu";

function NavItem({
  active,
  index,
  label,
  onNavigate,
  to,
}: {
  active: boolean;
  index: string;
  label: string;
  onNavigate?: () => void;
  to: string;
}) {
  return (
    <li>
      <TransitionLink
        aria-current={active ? "page" : undefined}
        className="grid min-h-12 grid-cols-[2.25rem_minmax(0,1fr)] items-center border-l-4 border-transparent px-4 py-2 text-sm text-white/80 no-underline transition-[background-color,border-color,color] hover:border-white/40 hover:bg-white/10 hover:text-white aria-[current=page]:border-signal aria-[current=page]:bg-brand aria-[current=page]:text-white"
        onClick={onNavigate}
        to={to}
      >
        <span className="font-mono text-[0.68rem] tabular-nums opacity-65" aria-hidden="true">
          {index}
        </span>
        <strong className="min-w-0 leading-snug">{label}</strong>
      </TransitionLink>
    </li>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="mt-4 border-t border-white/15 px-5 pt-5 pb-2 font-mono text-[0.65rem] tracking-[0.13em] text-white/55 uppercase first:mt-0 first:border-0 first:pt-3">
      {children}
    </p>
  );
}

export function SiteNavigation({
  locale,
  onNavigate,
}: {
  locale: Locale;
  onNavigate?: () => void;
}) {
  const { pathname } = useLocation();
  const { t } = useUi();
  const sections = useStorySections();

  return (
    <div className="flex min-h-full flex-col bg-ink text-white">
      <TransitionLink
        className="flex aspect-square w-full shrink-0 flex-col items-center justify-center border-b-2 border-white/20 bg-white px-5 text-center text-ink no-underline transition-colors hover:bg-paper"
        onClick={onNavigate}
        to={`/${locale}`}
      >
        <img
          alt=""
          className="aspect-square w-40 max-w-full object-contain"
          height="256"
          src={logoUrl}
          width="256"
        />
        <Eyebrow className="mb-0 text-ink" translate="no">
          Arkwaifu - Phantom
        </Eyebrow>
      </TransitionLink>

      <nav aria-label={t("navigation.primaryLabel")} className="pb-4">
        <SectionLabel>{t("navigation.directory")}</SectionLabel>
        <ul className="m-0 list-none p-0">
          <NavItem
            active={pathname === `/${locale}` || pathname === `/${locale}/`}
            index="00"
            label={t("navigation.overview")}
            onNavigate={onNavigate}
            to={`/${locale}`}
          />
        </ul>

        <SectionLabel>{t("navigation.stories")}</SectionLabel>
        <ul className="m-0 list-none p-0">
          {Object.entries(sections).map(([slug, section]) => (
            <NavItem
              active={pathname.startsWith(`/${locale}/stories/${slug}`)}
              index={section.index}
              key={slug}
              label={section.title}
              onNavigate={onNavigate}
              to={`/${locale}/stories/${slug}`}
            />
          ))}
        </ul>

        <SectionLabel>{t("navigation.collections")}</SectionLabel>
        <ul className="m-0 list-none p-0">
          <NavItem
            active={pathname.startsWith(`/${locale}/galleries`)}
            index="08"
            label={t("navigation.galleries")}
            onNavigate={onNavigate}
            to={`/${locale}/galleries`}
          />
          <NavItem
            active={pathname === `/${locale}/unreferenced`}
            index="09"
            label={t("navigation.unreferenced")}
            onNavigate={onNavigate}
            to={`/${locale}/unreferenced`}
          />
        </ul>

        <SectionLabel>{t("navigation.aboutSection")}</SectionLabel>
        <ul className="m-0 list-none p-0">
          <NavItem
            active={pathname === `/${locale}/about`}
            index="10"
            label={t("navigation.about")}
            onNavigate={onNavigate}
            to={`/${locale}/about`}
          />
        </ul>
      </nav>

      <a
        className="mt-auto flex min-h-14 items-center justify-between border-t-2 border-white/20 px-5 py-3 text-xs font-bold tracking-wide text-white/75 uppercase no-underline transition-colors hover:bg-white hover:text-ink"
        href={repositoryUrl}
        rel="noreferrer"
        target="_blank"
      >
        <span>{t("navigation.sourceAndLicense")}</span>
        <span aria-hidden="true">↗</span>
      </a>
    </div>
  );
}
