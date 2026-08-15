import { useLocation } from "react-router";
import type { Locale, StoryDetail } from "../../api/types";
import { uniqueStoryArtReferences } from "../../api/utils";
import { useUi } from "../../i18n";
import { localeLanguageTag } from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ArtworkCollection } from "../artwork/ArtworkCollection";

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
    </ArchivePage>
  );
}
