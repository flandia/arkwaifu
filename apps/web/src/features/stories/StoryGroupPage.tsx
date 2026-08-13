import { use } from "react";
import { useLocation, useParams } from "react-router";
import { ApiError, getStoryGroupWithStories } from "../../api";
import { useUi, useUiLanguage } from "../../i18n";
import {
  localeLanguageTag,
  requiredLocale,
  requiredSection,
  sectionForType,
  useStorySections,
} from "../../navigation";
import { ArchivePage, BackLink, EmptyState, PageHeader } from "../../shared/Page";
import { SectionHeading } from "../../shared/ui";
import { ArtworkCollection } from "../artwork/ArtworkCollection";
import { StageCard } from "./StoryCards";

export function StoryGroupPage() {
  const { t } = useUi();
  const { language: uiLanguage } = useUiLanguage();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const section = requiredSection(params.section);
  const groupID = params.groupID ?? "";
  const [group, stories] = use(getStoryGroupWithStories(locale, groupID));
  if (sectionForType(group.type) !== section)
    throw new ApiError(t("errors.wrongStorySection"), 404);
  const recordLanguage = localeLanguageTag(locale);
  const location = useLocation();
  const sectionTitle = useStorySections()[section].title;

  return (
    <ArchivePage
      description={`${group.name} · ${sectionTitle} · ${t("story.stageDescription")}`}
      image={group.representativeArtReference?.thumbnailContentUrl ?? undefined}
      title={group.name}
    >
      <BackLink to={`/${locale}/stories/${section}`}>
        {t("story.backToSection", { section: sectionTitle })}
      </BackLink>
      <PageHeader
        eyebrow={t("story.groupEyebrow")}
        meta={
          <>
            <code translate="no">{group.id}</code>
            <span>{t("story.stageCount", { count: stories.length })}</span>
          </>
        }
        title={group.name}
        titleLanguage={recordLanguage}
      />

      {stories.length ? (
        <section className="mt-16" aria-labelledby="stage-list-title">
          <SectionHeading
            eyebrow={t("story.orderedRecords")}
            meta={new Intl.NumberFormat(uiLanguage).format(stories.length)}
            title={t("story.stages")}
            titleId="stage-list-title"
          />
          <ol className="m-0 grid list-none border-t-2 border-l-2 border-ink p-0 md:grid-cols-2">
            {stories.map((story, index) => (
              <StageCard
                groupID={group.id}
                index={index}
                key={story.id}
                locale={locale}
                section={section}
                story={story}
              />
            ))}
          </ol>
        </section>
      ) : (
        <EmptyState title={t("story.noStages")}>{t("story.noStagesHint")}</EmptyState>
      )}

      <ArtworkCollection
        artworks={group.artReferences}
        from={`${location.pathname}${location.search}`}
        language={recordLanguage}
        locale={locale}
      />
    </ArchivePage>
  );
}
