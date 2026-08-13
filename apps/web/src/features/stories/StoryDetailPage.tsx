import { use } from "react";
import { useLocation, useParams } from "react-router";
import { ApiError, getStory, getStoryGroups, uniqueStoryArtReferences } from "../../api";
import { useUi } from "../../i18n";
import {
  localeLanguageTag,
  requiredLocale,
  requiredSection,
  sectionForType,
} from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ArtworkCollection } from "../artwork/ArtworkCollection";

export function StoryDetailPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const section = requiredSection(params.section);
  const groupID = params.groupID ?? "";
  const storyID = params.storyID ?? "";
  const storyRequest = getStory(locale, storyID);
  const groupsRequest = getStoryGroups(locale);
  const story = use(storyRequest);
  const artReferences = uniqueStoryArtReferences(story.artReferences);
  const group = use(groupsRequest).find((value) => value.id === groupID);
  if (story.groupID !== groupID || !group || sectionForType(group.type) !== section) {
    throw new ApiError(t("errors.wrongStoryGroup"), 404);
  }
  const location = useLocation();
  const language = localeLanguageTag(locale);

  return (
    <ArchivePage
      description={story.info || t("story.stageDescription")}
      image={
        artReferences.find((reference) => reference.thumbnailContentUrl)?.thumbnailContentUrl ??
        undefined
      }
      title={story.name || story.code || t("story.untitledStage")}
    >
      <BackLink to={`/${locale}/stories/${section}/${encodeURIComponent(groupID)}`}>
        {t("story.backToGroup")}
      </BackLink>
      <PageHeader
        description={story.info || t("story.stageDescription")}
        descriptionLanguage={story.info ? language : undefined}
        eyebrow={t("story.stageEyebrow")}
        meta={
          <>
            <code translate="no">{story.code || story.id}</code>
            <span>{story.tagText || story.tag}</span>
            <span>{t("story.uniqueArtCount", { count: artReferences.length })}</span>
          </>
        }
        title={story.name || story.code || t("story.untitledStage")}
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
