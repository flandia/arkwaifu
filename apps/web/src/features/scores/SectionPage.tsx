import { use, useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router";
import { ApiError } from "../../api/client";
import { getMovement, getSection } from "../../api/scores";
import { useUi } from "../../i18n";
import { localeLanguageTag, requiredLocale } from "../../navigation";
import { ArchivePage, BackLink } from "../../shared/Page";
import { Eyebrow } from "../../shared/ui/Typography";
import { ArtworkCollection } from "../artwork/ArtworkCollection";
import { GalleryGroups } from "../galleries/GalleryGroups";
import { OpeningMediaCollection, StoryMediaCollection } from "../hierarchy/MediaCollection";
import { ScoreImageAsset } from "../hierarchy/ScoreVisual";
import { StoryRecords } from "../hierarchy/StoryRecords";

export function SectionPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const movementID = params["movement-id"] ?? "";
  const sectionID = params["section-id"] ?? "";
  const movementRequest = getMovement(locale, movementID);
  const sectionRequest = getSection(locale, movementID, sectionID);
  const movement = use(movementRequest);
  const section = use(sectionRequest);
  const canonical = movement.items.find(
    (item) => item.kind === "section" && item.section.id === section.id,
  );
  if (!canonical) throw new ApiError(t("errors.wrongSection"), 404);
  const language = localeLanguageTag(locale);
  const location = useLocation();
  const basePath = `/${locale}/scores/${encodeURIComponent(movement.id)}/${encodeURIComponent(section.id)}`;
  const heroBackground = section.retroBackground ?? section.background ?? section.keyVisual;
  const heroRef = useRef<HTMLElement>(null);
  const [heroPassed, setHeroPassed] = useState(false);

  useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return;

    setHeroPassed(false);
    const updateHeroPassed = () => {
      const nextHeroPassed = hero.getBoundingClientRect().bottom <= 0;
      setHeroPassed((current) => (current === nextHeroPassed ? current : nextHeroPassed));
    };
    updateHeroPassed();
    window.addEventListener("scroll", updateHeroPassed, { passive: true });
    window.addEventListener("resize", updateHeroPassed);
    return () => {
      window.removeEventListener("scroll", updateHeroPassed);
      window.removeEventListener("resize", updateHeroPassed);
    };
  }, [section.id]);

  return (
    <ArchivePage
      description={section.description || t("score.sectionDescription")}
      image={heroBackground?.image?.url ?? section.keyVisual?.image?.url ?? undefined}
      theme={heroPassed ? "light" : "dark"}
      title={section.name || t("score.untitledSection")}
    >
      <BackLink tone="dark" to={`/${locale}/scores/${encodeURIComponent(movement.id)}`}>
        {t("score.backToMovement", { name: movement.name })}
      </BackLink>

      <header className="mb-9 border-b-[3px] border-white/35 pb-[clamp(2rem,5vw,4rem)]">
        <Eyebrow className="text-white/60">
          {movement.name} / {t(`score.sectionTypes.${section.type}`)}
        </Eyebrow>
        <h1
          className="mb-6 max-w-[15ch] font-display text-[clamp(3.2rem,8vw,7rem)] leading-[0.88] font-black tracking-[-0.035em] uppercase"
          lang={language}
        >
          {section.name || t("score.untitledSection")}
        </h1>
        <div className="flex flex-wrap gap-x-6 gap-y-2 font-mono text-xs text-white/55">
          <code translate="no">{section.id}</code>
          <span>{t("story.count", { count: section.stories.length })}</span>
        </div>
      </header>

      <section className="relative overflow-hidden bg-black" ref={heroRef}>
        <ScoreImageAsset
          alt=""
          asset={heroBackground}
          className="block h-auto w-full object-contain"
          eager
        />
        <span
          className="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent to-transparent sm:bg-gradient-to-l sm:from-black/90 sm:via-black/15 sm:to-transparent"
          aria-hidden="true"
        />
        <ScoreImageAsset
          alt=""
          asset={section.decoration}
          className="absolute top-5 right-5 z-10 max-h-24 max-w-28 object-contain"
        />
        <div className="absolute right-0 bottom-0 z-10 w-full p-[clamp(1.25rem,5vw,4rem)] sm:w-[min(48rem,58%)]">
          <ScoreImageAsset
            alt={section.name}
            asset={section.titleImage}
            className="ml-auto mb-5 max-h-32 max-w-[min(100%,32rem)] object-contain object-right drop-shadow-xl"
          />
          <p
            className="ml-auto mb-0 hidden max-w-2xl whitespace-pre-line text-right leading-relaxed text-white/75 md:block"
            lang={language}
          >
            {section.description}
          </p>
        </div>
      </section>

      <div className="mt-16 bg-transparent px-[clamp(1rem,4vw,4rem)] pt-1 pb-[clamp(2rem,6vw,6rem)]">
        <StoryRecords
          basePath={basePath}
          locale={locale}
          stories={section.stories}
          tone={heroPassed ? "light" : "dark"}
        />
        {section.gallery ? (
          <GalleryGroups
            gallery={section.gallery}
            locale={locale}
            tone={heroPassed ? "light" : "dark"}
          />
        ) : null}
        <OpeningMediaCollection
          from={`${location.pathname}${location.search}`}
          locale={locale}
          media={section.openingMedia}
          tone={heroPassed ? "light" : "dark"}
        />
        <StoryMediaCollection
          from={`${location.pathname}${location.search}`}
          locale={locale}
          media={section.media}
          tone={heroPassed ? "light" : "dark"}
        />
        <ArtworkCollection
          artworks={section.imageReferences}
          eyebrow={t("artwork.sectionReferences")}
          from={`${location.pathname}${location.search}`}
          language={language}
          locale={locale}
          tone={heroPassed ? "light" : "dark"}
        />
      </div>
    </ArchivePage>
  );
}
