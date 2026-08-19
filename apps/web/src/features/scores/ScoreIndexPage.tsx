import { Suspense, use, useEffect, useRef, useState } from "react";
import { useParams } from "react-router";
import { getMovement, getMovements } from "../../api/scores";
import type { Locale, MovementDetail, MovementSummary } from "../../api/types";
import { useUi } from "../../i18n";
import { localeLanguageTag, requiredLocale, TransitionLink } from "../../navigation";
import { CollectionControls, useCollectionIndex } from "../../shared/CollectionIndex";
import { ArchivePage, EmptyState, PageHeader } from "../../shared/Page";
import { Eyebrow } from "../../shared/ui/Typography";
import { ScoreArchiveMark, ScoreImageAsset } from "../hierarchy/ScoreVisual";
import { SectionCard } from "./ScoreCards";

function movementSearchValues(movement: MovementSummary): string[] {
  return [movement.name, movement.id];
}

function MovementHeading({ locale, movement }: { locale: Locale; movement: MovementSummary }) {
  const { t } = useUi();
  const language = localeLanguageTag(locale);
  const movementPath = `/${locale}/scores/${encodeURIComponent(movement.id)}`;

  return (
    <header className="mb-10 grid items-center gap-6 border-b-[3px] border-ink pb-7 sm:grid-cols-[8rem_minmax(0,1fr)_auto]">
      <div className="grid aspect-square w-28 place-items-center bg-ink p-3">
        <ScoreImageAsset alt="" asset={movement.logo} className="size-full object-contain" />
      </div>
      <div className="min-w-0">
        <ScoreImageAsset
          alt=""
          asset={movement.icon}
          className="mb-3 max-h-9 max-w-32 object-contain object-left"
        />
        <Eyebrow>{t("score.movement")}</Eyebrow>
        <h2
          className="mb-3 break-words text-[clamp(2.5rem,6vw,6rem)] leading-[0.86] font-black tracking-[-0.045em] uppercase"
          lang={language}
        >
          {movement.name || t("score.untitledMovement")}
        </h2>
        <code className="text-muted" translate="no">
          {movement.id}
        </code>
      </div>
      <TransitionLink
        aria-label={t("common.open", { name: movement.name })}
        className="grid size-12 place-items-center border-2 border-ink bg-brand font-black text-white no-underline hover:bg-ink"
        to={movementPath}
        transition="forward"
      >
        ↗
      </TransitionLink>
    </header>
  );
}

function SectionIndex({ locale, movement }: { locale: Locale; movement: MovementDetail }) {
  const sections = movement.items.flatMap((item) =>
    item.kind === "section" ? [item.section] : [],
  );

  return (
    <>
      <MovementHeading locale={locale} movement={movement} />
      {sections.length ? (
        <ol className="m-0 grid list-none gap-7 p-0 md:grid-cols-2 xl:grid-cols-3">
          {sections.map((section) => (
            <SectionCard
              key={section.id}
              locale={locale}
              movementID={movement.id}
              section={section}
            />
          ))}
        </ol>
      ) : null}
    </>
  );
}

function ResolvedSectionIndex({ locale, movement }: { locale: Locale; movement: MovementSummary }) {
  const detail = use(getMovement(locale, movement.id));
  return <SectionIndex locale={locale} movement={detail} />;
}

function SectionPlaceholder({ locale, movement }: { locale: Locale; movement: MovementSummary }) {
  return (
    <>
      <MovementHeading locale={locale} movement={movement} />
      <div className="grid min-h-96 animate-pulse place-items-center border-2 border-ink/20 bg-paper text-xs font-black tracking-[0.2em] text-muted uppercase">
        {movement.id}
      </div>
    </>
  );
}

function LazySectionIndex({
  eager,
  locale,
  movement,
}: {
  eager: boolean;
  locale: Locale;
  movement: MovementSummary;
}) {
  const articleRef = useRef<HTMLElement>(null);
  const [active, setActive] = useState(eager);

  useEffect(() => {
    if (active) return;
    const article = articleRef.current;
    if (!article || typeof IntersectionObserver === "undefined") {
      setActive(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        setActive(true);
        observer.disconnect();
      },
      { rootMargin: "160px 0px", threshold: 0.01 },
    );
    observer.observe(article);
    return () => observer.disconnect();
  }, [active]);

  return (
    <article
      className="min-w-0 [contain-intrinsic-block-size:auto_48rem] [content-visibility:auto]"
      ref={articleRef}
    >
      {active ? (
        <Suspense fallback={<SectionPlaceholder locale={locale} movement={movement} />}>
          <ResolvedSectionIndex locale={locale} movement={movement} />
        </Suspense>
      ) : (
        <SectionPlaceholder locale={locale} movement={movement} />
      )}
    </article>
  );
}

export function ScoreIndexPage() {
  const { t } = useUi();
  const locale = requiredLocale(useParams().locale);
  const movements = use(getMovements(locale));
  const index = useCollectionIndex(movements, movementSearchValues, "archive");

  return (
    <ArchivePage description={t("score.description")} title={t("score.title")}>
      <div className="mb-8 grid grid-cols-[5rem_minmax(0,1fr)] items-start gap-5">
        <ScoreArchiveMark className="mt-1 size-20 shrink-0 text-ink" />
        <PageHeader
          description={t("score.description")}
          eyebrow={t("score.indexEyebrow")}
          meta={<span>{t("common.locale", { locale })}</span>}
          title={t("score.title")}
        />
      </div>
      <CollectionControls
        count={index.visible.length}
        noun={t("collection.movementNoun", { count: index.visible.length })}
        onOrder={index.setOrder}
        onQuery={index.setQuery}
        order={index.order}
        query={index.query}
      />
      {index.visible.length ? (
        <section className="grid gap-28" aria-label={t("score.movements")}>
          {index.visible.map((movement, position) => (
            <LazySectionIndex
              eager={position === 0}
              key={movement.id}
              locale={locale}
              movement={movement}
            />
          ))}
        </section>
      ) : (
        <EmptyState title={t("score.noMovements")}>{t("score.noMovementsHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
