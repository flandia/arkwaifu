import { use, useEffect, useRef, useState } from "react";
import { useParams } from "react-router";
import { getMovement } from "../../api/scores";
import type {
  MovementDetail,
  ScoreSectionItem,
  ScoreSectionSummary,
  ScoreSplit,
} from "../../api/types";
import { useUi } from "../../i18n";
import { localeLanguageTag, requiredLocale } from "../../navigation";
import { ArchivePage, BackLink, EmptyState } from "../../shared/Page";
import { Eyebrow } from "../../shared/ui/Typography";
import { ScoreBackdrop, ScoreImageAsset } from "../hierarchy/ScoreVisual";
import { MainThemeSectionRow, ScoreSectionCard, ScoreSplitCard } from "./ScoreCards";

function lastSplit(movement: MovementDetail): ScoreSplit | undefined {
  return movement.items.findLast((item): item is ScoreSplit => item.kind === "split");
}

function lastSection(movement: MovementDetail): ScoreSectionItem | undefined {
  return movement.items.findLast((item): item is ScoreSectionItem => item.kind === "section");
}

function movementSections(movement: MovementDetail): ScoreSectionSummary[] {
  return movement.items.flatMap((item) => (item.kind === "section" ? [item.section] : []));
}

function MainlineSectionShortcuts({ movement }: { movement: MovementDetail }) {
  const { t } = useUi();
  const sections = movementSections(movement);
  if (!sections.length) return null;

  return (
    <nav aria-label={t("score.orderedSections")} className="mt-8 bg-black py-4">
      <ol className="m-0 grid list-none grid-cols-2 gap-4 p-0 @min-[34rem]/page:grid-cols-3 @min-[54rem]/page:grid-cols-4">
        {sections.map((section) => (
          <li className="min-w-0" key={section.id}>
            <a
              className="group relative grid aspect-square overflow-hidden bg-black text-white no-underline"
              href={`#movement-section-${section.id}`}
              title={section.name}
            >
              <ScoreImageAsset
                alt=""
                asset={section.keyVisual}
                className="absolute inset-0 size-full object-contain opacity-70 transition-opacity group-hover:opacity-100"
              />
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function MovementSectionMasonry({
  locale,
  movementID,
  sections,
}: {
  locale: ReturnType<typeof requiredLocale>;
  movementID: string;
  sections: ScoreSectionSummary[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isTwoColumn, setIsTwoColumn] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;

    const updateColumns = (width: number) => {
      const nextIsTwoColumn = width >= 672;
      setIsTwoColumn((current) => (current === nextIsTwoColumn ? current : nextIsTwoColumn));
    };
    updateColumns(container.clientWidth);

    const observer = new ResizeObserver(([entry]) => {
      if (entry) updateColumns(entry.contentRect.width);
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const renderSection = (section: ScoreSectionSummary) => (
    <ScoreSectionCard key={section.id} locale={locale} movementID={movementID} section={section} />
  );

  return (
    <div className="relative z-10 mt-16" ref={containerRef}>
      {isTwoColumn ? (
        <div className="grid grid-cols-2 items-start gap-8">
          <ol className="m-0 grid min-w-0 list-none content-start gap-8 p-0">
            {sections.filter((_, index) => index % 2 === 0).map(renderSection)}
          </ol>
          <ol className="m-0 grid min-w-0 list-none content-start gap-8 p-0">
            {sections.filter((_, index) => index % 2 === 1).map(renderSection)}
          </ol>
        </div>
      ) : (
        <ol className="m-0 grid list-none gap-8 p-0">{sections.map(renderSection)}</ol>
      )}
    </div>
  );
}

export function MovementPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const movement = use(getMovement(locale, params.movementID ?? ""));
  const language = localeLanguageTag(locale);
  const isMainline = movement.id === "mainline";
  const activeSplit = isMainline ? lastSplit(movement) : undefined;
  const activeSection = isMainline ? lastSection(movement)?.section : undefined;
  const heroVideo = activeSplit?.video ?? movement.backgroundVideo;
  const heroImage = activeSection?.background ?? movement.background;
  const heroRatio = heroVideo?.video
    ? `${heroVideo.video.width} / ${heroVideo.video.height}`
    : undefined;
  const hero = (
    <header
      className={
        isMainline
          ? "relative grid w-full content-end overflow-hidden bg-black text-white"
          : "relative grid min-h-[min(48rem,78vh)] content-end overflow-hidden bg-black text-white"
      }
      style={isMainline && heroRatio ? { aspectRatio: heroRatio } : undefined}
    >
      <ScoreBackdrop
        image={heroImage}
        imageClassName={isMainline ? "object-cover" : "object-contain object-center"}
        priority
        video={heroVideo}
      />
      <span
        className="absolute inset-0 bg-gradient-to-tr from-black/95 via-black/30 to-transparent"
        aria-hidden="true"
      />
      <div className="relative z-10 flex w-full items-end gap-6 p-[clamp(2rem,6vw,6rem)]">
        <ScoreImageAsset
          alt=""
          asset={movement.logo}
          className="hidden aspect-square w-[clamp(5rem,11vw,10rem)] shrink-0 object-contain sm:block"
        />
        <div className="min-w-0 flex-1">
          <ScoreImageAsset
            alt=""
            asset={movement.icon}
            className="mb-5 max-h-12 max-w-40 object-contain object-left"
          />
          <Eyebrow className="text-white/70">{t("score.movement")}</Eyebrow>
          <h1
            className="m-0 max-w-full font-display text-[clamp(3.4rem,9vw,8rem)] leading-[0.86] font-black tracking-tight text-balance uppercase"
            lang={language}
          >
            {movement.name || t("score.untitledMovement")}
          </h1>
          <code className="mt-6 block text-xs text-white/65" translate="no">
            {movement.id}
          </code>
        </div>
      </div>
    </header>
  );

  return (
    <ArchivePage
      description={t("score.movementDescription", { name: movement.name })}
      image={movement.logo?.image?.contentUrl ?? heroImage?.image?.contentUrl ?? undefined}
      theme="dark"
      title={movement.name || t("score.untitledMovement")}
    >
      {isMainline ? (
        <>
          <BackLink tone="dark" to={`/${locale}/scores`}>
            {t("score.backToScores")}
          </BackLink>
          {hero}
          <MainlineSectionShortcuts movement={movement} />
        </>
      ) : (
        <>
          <BackLink tone="dark" to={`/${locale}/scores`}>
            {t("score.backToScores")}
          </BackLink>
          {hero}
        </>
      )}

      {movement.items.length ? (
        isMainline ? (
          <ol aria-label={t("score.orderedSections")} className="mt-16 grid list-none gap-8 p-0">
            {movement.items.map((item) =>
              item.kind === "split" ? (
                <ScoreSplitCard key={`split:${item.id}`} split={item} />
              ) : (
                <MainThemeSectionRow
                  key={`section:${item.section.id}`}
                  locale={locale}
                  movementID={movement.id}
                  section={item.section}
                />
              ),
            )}
          </ol>
        ) : (
          <MovementSectionMasonry
            locale={locale}
            movementID={movement.id}
            sections={movementSections(movement)}
          />
        )
      ) : (
        <div className="text-ink">
          <EmptyState title={t("score.noSections")}>{t("score.noSectionsHint")}</EmptyState>
        </div>
      )}
    </ArchivePage>
  );
}
