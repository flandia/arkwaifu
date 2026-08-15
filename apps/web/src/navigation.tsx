import {
  ViewTransition,
  addTransitionType,
  startTransition,
  useEffect,
  useTransition,
  type MouseEvent,
  type ReactNode,
} from "react";
import type { TFunction } from "i18next";
import { Link, useNavigate, type LinkProps } from "react-router";
import { ApiError } from "./api/client";
import type { ArchiveKind, ArtCategory, Locale, StoryParent } from "./api/types";
import { i18n, useUi } from "./i18n";
import { cn } from "./shared/ui/cn";

export type NavigationKind = "lateral" | "forward" | "back";

export const archiveKinds = {
  events: {
    labelKey: "archive.kinds.events",
    index: "A1",
  },
  "operator-record": {
    labelKey: "archive.kinds.operatorRecord",
    index: "A2",
  },
  "integrated-strategies": {
    labelKey: "archive.kinds.integratedStrategies",
    index: "A3",
  },
  "reclamation-algorithm": {
    labelKey: "archive.kinds.reclamationAlgorithm",
    index: "A4",
  },
  others: {
    labelKey: "archive.kinds.others",
    index: "A5",
  },
} as const;

export function isLocale(value: string | undefined): value is Locale {
  return value === "CN" || value === "EN" || value === "JP" || value === "KR" || value === "TW";
}

export function requiredLocale(value: string | undefined): Locale {
  if (!isLocale(value)) throw new ApiError(i18n.t("errors.unsupportedLocale"), 404);
  return value;
}

export function localeLanguageTag(locale: Locale): string {
  return {
    CN: "zh-CN",
    EN: "en",
    JP: "ja",
    KR: "ko",
    TW: "zh-TW",
  }[locale];
}

export function isArchiveKind(value: string | undefined): value is ArchiveKind {
  return value !== undefined && Object.hasOwn(archiveKinds, value);
}

export function requiredArchiveKind(value: string | undefined): ArchiveKind {
  if (!isArchiveKind(value)) throw new ApiError(i18n.t("errors.missingArchiveKind"), 404);
  return value;
}

export function archiveKindLabel(kind: ArchiveKind, t: TFunction): string {
  return t(archiveKinds[kind].labelKey);
}

export function useArchiveKinds() {
  const { t } = useUi();
  return Object.fromEntries(
    Object.entries(archiveKinds).map(([kind, details]) => [
      kind,
      { ...details, title: t(details.labelKey) },
    ]),
  ) as Record<ArchiveKind, (typeof archiveKinds)[ArchiveKind] & { title: string }>;
}

export function storyParentPath(locale: Locale, parent: StoryParent): string {
  return parent.kind === "score"
    ? `/${locale}/scores/${encodeURIComponent(parent.movementID)}/${encodeURIComponent(parent.sectionID)}`
    : `/${locale}/archives/${parent.archiveKind}/${encodeURIComponent(parent.groupID)}`;
}

export function storyPath(locale: Locale, parent: StoryParent, storyID: string): string {
  return `${storyParentPath(locale, parent)}/${encodeURIComponent(storyID)}`;
}

export function isPathAtOrBelow(pathname: string, parentPath: string): boolean {
  return pathname === parentPath || pathname.startsWith(`${parentPath}/`);
}

const categoryKeys = {
  image: { singular: "art.category.image", plural: "art.categories.image" },
  background: { singular: "art.category.background", plural: "art.categories.background" },
  item: { singular: "art.category.item", plural: "art.categories.item" },
  character: { singular: "art.category.character", plural: "art.categories.character" },
} as const;

export function categoryLabel(category: ArtCategory, t: TFunction, plural = false): string {
  return t(categoryKeys[category][plural ? "plural" : "singular"]);
}

export function useCategoryLabel() {
  const { t } = useUi();
  return (category: ArtCategory, plural = false) => categoryLabel(category, t, plural);
}

interface TransitionLinkProps extends LinkProps {
  transition?: NavigationKind;
}

function handlesClientNavigation(event: MouseEvent<HTMLAnchorElement>, target?: string): boolean {
  return (
    event.button === 0 &&
    !event.metaKey &&
    !event.ctrlKey &&
    !event.shiftKey &&
    !event.altKey &&
    (!target || target === "_self")
  );
}

export function TransitionLink({
  transition = "lateral",
  onClick,
  replace,
  state,
  target,
  to,
  ...props
}: TransitionLinkProps) {
  const navigate = useNavigate();
  const [isPending, startNavigation] = useTransition();

  useEffect(() => {
    if (!isPending) return;
    document.documentElement.dataset.navigationPending = "true";
    return () => {
      delete document.documentElement.dataset.navigationPending;
    };
  }, [isPending]);

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (event.defaultPrevented || !handlesClientNavigation(event, target)) return;

    event.preventDefault();
    startNavigation(() => {
      addTransitionType(`nav-${transition}`);
      void navigate(to, { replace, state });
    });
  }

  return (
    <Link
      {...props}
      aria-busy={isPending || undefined}
      onClick={handleClick}
      replace={replace}
      state={state}
      target={target}
      to={to}
    />
  );
}

export function beginNavigation(callback: () => void, kind: NavigationKind = "lateral"): void {
  startTransition(() => {
    addTransitionType(`nav-${kind}`);
    callback();
  });
}

export function PageTransition({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <ViewTransition
      default="none"
      enter={{
        "nav-forward": "nav-forward",
        "nav-back": "nav-back",
        "nav-lateral": "fade-in",
        default: "slide-up",
      }}
      exit={{
        "nav-forward": "nav-forward",
        "nav-back": "nav-back",
        "nav-lateral": "fade-out",
        default: "slide-down",
      }}
    >
      <div className={cn("min-h-full", className)}>
        <div className="@container/page mx-auto w-full max-w-[90rem] px-[clamp(1.25rem,4vw,4rem)] pt-[clamp(2rem,5vw,5rem)] pb-[clamp(4rem,8vw,8rem)]">
          {children}
        </div>
      </div>
    </ViewTransition>
  );
}

export function LoadingPage() {
  const { t } = useUi();
  return (
    <ViewTransition default="none" exit="slide-down">
      <div
        className="mx-auto grid min-h-[55vh] w-full max-w-[90rem] content-center px-[clamp(1.25rem,4vw,4rem)] pt-[clamp(2rem,5vw,5rem)] pb-[clamp(4rem,8vw,8rem)]"
        aria-live="polite"
        aria-busy="true"
      >
        <p className="mb-4 font-mono text-xs font-extrabold tracking-[0.12em] text-brand uppercase">
          {t("loading.eyebrow")}
        </p>
        <div className="mb-5 h-2 w-full max-w-2xl border-2 border-ink bg-brand" />
        <p className="text-lg font-bold">{t("loading.message")}</p>
      </div>
    </ViewTransition>
  );
}
