import { Suspense, use, type ReactNode } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { useLocation } from "react-router";
import { getMovements } from "../api/scores";
import type { Locale, ScoreImage } from "../api/types";
import { useUi } from "../i18n";
import { archiveKinds, isPathAtOrBelow, TransitionLink, useArchiveKinds } from "../navigation";
import { Eyebrow } from "../shared/ui/Typography";
import { ScoreArchiveMark } from "../features/hierarchy/ScoreVisual";

const logoUrl = "/arkwaifu_phantom@0.25x.png";
const repositoryUrl = "https://github.com/flandia/arkwaifu";

function NavItem({
  active,
  index,
  icon,
  label,
  mark,
  onNavigate,
  to,
}: {
  active: boolean;
  index: string;
  icon?: ScoreImage | null;
  label: string;
  mark?: ReactNode;
  onNavigate?: () => void;
  to: string;
}) {
  return (
    <li>
      <TransitionLink
        aria-current={active ? "page" : undefined}
        className="grid min-h-12 grid-cols-[2.25rem_minmax(0,1fr)] items-center border-l-4 border-transparent bg-ink px-4 py-2 text-sm text-white/80 no-underline transition-[background-color,border-color,color] hover:border-white/40 hover:bg-white/10 hover:text-white aria-[current=page]:border-signal aria-[current=page]:bg-brand aria-[current=page]:text-white"
        onClick={onNavigate}
        to={to}
      >
        {mark ??
          (icon?.image ? (
            <img
              alt=""
              className="size-7 object-contain"
              height={icon.image.height}
              loading="lazy"
              src={icon.image.contentUrl}
              width={icon.image.width}
            />
          ) : (
            <span
              className="font-mono text-[0.68rem] text-white/75 tabular-nums"
              aria-hidden="true"
            >
              {index}
            </span>
          ))}
        <strong className="flex min-h-7 min-w-0 translate-y-[0.06em] items-center leading-none">
          {label}
        </strong>
      </TransitionLink>
    </li>
  );
}

function MovementNavigation({ locale, onNavigate }: { locale: Locale; onNavigate?: () => void }) {
  const { pathname } = useLocation();
  const movements = use(getMovements(locale));
  return movements.map((movement, index) => {
    const movementPath = `/${locale}/scores/${encodeURIComponent(movement.id)}`;
    return (
      <NavItem
        active={isPathAtOrBelow(pathname, movementPath)}
        icon={movement.logo}
        index={`S${index + 1}`}
        key={movement.id}
        label={movement.name}
        onNavigate={onNavigate}
        to={movementPath}
      />
    );
  });
}

function MovementNavigationFallback() {
  return (
    <li
      className="mx-4 my-2 h-10 animate-pulse bg-white/10 motion-reduce:animate-none"
      aria-hidden="true"
    />
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
  const archives = useArchiveKinds();

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

        <SectionLabel>{t("navigation.scores")}</SectionLabel>
        <ul className="m-0 list-none p-0">
          <NavItem
            active={pathname === `/${locale}/scores`}
            index="S0"
            label={t("navigation.allScores")}
            mark={<ScoreArchiveMark className="size-7 text-white" />}
            onNavigate={onNavigate}
            to={`/${locale}/scores`}
          />
          <ErrorBoundary fallback={null}>
            <Suspense fallback={<MovementNavigationFallback />}>
              <MovementNavigation locale={locale} onNavigate={onNavigate} />
            </Suspense>
          </ErrorBoundary>
        </ul>

        <SectionLabel>{t("navigation.archives")}</SectionLabel>
        <ul className="m-0 list-none p-0">
          <NavItem
            active={pathname === `/${locale}/archives`}
            index="A0"
            label={t("navigation.allArchives")}
            onNavigate={onNavigate}
            to={`/${locale}/archives`}
          />
          {(Object.keys(archiveKinds) as Array<keyof typeof archiveKinds>).map((kind) => (
            <NavItem
              active={pathname.startsWith(`/${locale}/archives/${kind}`)}
              index={archiveKinds[kind].index}
              key={kind}
              label={archives[kind].title}
              onNavigate={onNavigate}
              to={`/${locale}/archives/${kind}`}
            />
          ))}
        </ul>

        <SectionLabel>{t("navigation.collections")}</SectionLabel>
        <ul className="m-0 list-none p-0">
          <NavItem
            active={pathname.startsWith(`/${locale}/galleries`)}
            index="C1"
            label={t("navigation.galleries")}
            onNavigate={onNavigate}
            to={`/${locale}/galleries`}
          />
          <NavItem
            active={pathname === `/${locale}/unreferenced`}
            index="C2"
            label={t("navigation.unreferenced")}
            onNavigate={onNavigate}
            to={`/${locale}/unreferenced`}
          />
        </ul>

        <SectionLabel>{t("navigation.aboutSection")}</SectionLabel>
        <ul className="m-0 list-none p-0">
          <NavItem
            active={pathname === `/${locale}/about`}
            index="I1"
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
