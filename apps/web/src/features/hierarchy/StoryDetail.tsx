import { useLocation } from "react-router";
import type { Locale, StoryDetail } from "../../api/types";
import { uniqueStoryArtReferences } from "../../api/utils";
import { useUi } from "../../i18n";
import { localeLanguageTag } from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { SectionHeading } from "../../shared/ui/Typography";
import { ArtworkCollection } from "../artwork/ArtworkCollection";
import { StoryMediaCollection } from "./MediaCollection";

export function OwnedStoryDetail({
  backTo,
  locale,
  story,
}: {
  backTo: string;
  locale: Locale;
  story: StoryDetail;
}) {
  const { t } = useUi();
  const location = useLocation();
  const language = localeLanguageTag(locale);
  const artReferences = uniqueStoryArtReferences(story.artReferences);
  const title = story.name || story.code || t("story.untitled");

  return (
    <ArchivePage
      description={story.info || t("story.description")}
      image={
        artReferences.find((reference) => reference.thumbnailContentUrl)?.thumbnailContentUrl ??
        undefined
      }
      title={title}
    >
      <BackLink to={backTo}>{t("story.back")}</BackLink>
      <PageHeader
        description={story.info || t("story.description")}
        descriptionLanguage={story.info ? language : undefined}
        eyebrow={t("story.record")}
        meta={
          <>
            <code translate="no">{story.code || story.id}</code>
            <span>{story.tagText || story.tag}</span>
            <span>{t("story.artCount", { count: artReferences.length })}</span>
          </>
        }
        title={title}
        titleLanguage={language}
      />
      <ArtworkCollection
        artworks={artReferences}
        from={`${location.pathname}${location.search}`}
        language={language}
        locale={locale}
      />
      <StoryMediaCollection
        from={`${location.pathname}${location.search}`}
        locale={locale}
        media={story.media}
      />
      {story.text ? (
        <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="story-text-title">
          <SectionHeading
            eyebrow={t("story.record")}
            title={t("story.text")}
            titleId="story-text-title"
          />
          <div
            className="border-y-2 border-ink/20 bg-surface px-5 py-6 font-mono text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere] sm:px-8 sm:py-8"
            lang={language}
          >
            {story.text}
          </div>
        </section>
      ) : null}
    </ArchivePage>
  );
}
