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
import { ApiError, type ArtCategory, type Locale, type StoryGroupType } from "./api";
import { i18n, useUi } from "./i18n";

export type NavigationKind = "lateral" | "forward" | "back";

export const storySections = {
  main: {
    type: "main_story",
    labelKey: "story.sections.main",
    index: "01",
  },
  events: {
    type: "major_event",
    labelKey: "story.sections.events",
    index: "02",
  },
  vignettes: {
    type: "minor_event",
    labelKey: "story.sections.vignettes",
    index: "03",
  },
  records: {
    type: "operator_record",
    labelKey: "story.sections.records",
    index: "04",
  },
  "integrated-strategies": {
    type: "integrated_strategies",
    labelKey: "story.sections.integratedStrategies",
    index: "05",
  },
  "reclamation-algorithm": {
    type: "reclamation_algorithm",
    labelKey: "story.sections.reclamationAlgorithm",
    index: "06",
  },
  others: {
    type: "others",
    labelKey: "story.sections.others",
    index: "07",
  },
} as const;

export type StorySection = keyof typeof storySections;

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

export function isStorySection(value: string | undefined): value is StorySection {
  return value !== undefined && Object.hasOwn(storySections, value);
}

export function requiredSection(value: string | undefined): StorySection {
  if (!isStorySection(value)) throw new ApiError(i18n.t("errors.missingSection"), 404);
  return value;
}

export function sectionForType(type: StoryGroupType): StorySection {
  const match = Object.entries(storySections).find(([, section]) => section.type === type);
  return match?.[0] as StorySection;
}

export function storySectionLabel(section: StorySection, t: TFunction): string {
  return t(storySections[section].labelKey);
}

export function useStorySections() {
  const { t } = useUi();
  return Object.fromEntries(
    Object.entries(storySections).map(([slug, section]) => [
      slug,
      { ...section, title: t(section.labelKey) },
    ]),
  ) as Record<StorySection, (typeof storySections)[StorySection] & { title: string }>;
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

export function PageTransition({ children }: { children: ReactNode }) {
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
      <div className="mx-auto w-full max-w-[90rem] px-[clamp(1.25rem,4vw,4rem)] pt-[clamp(2rem,5vw,5rem)] pb-[clamp(4rem,8vw,8rem)]">
        {children}
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
