import { use } from "react";
import { useLocation, useParams } from "react-router";
import { ApiError } from "../../api/client";
import { getArchiveGroup } from "../../api/archives";
import { useUi } from "../../i18n";
import {
  archiveCategoryLabel,
  localeLanguageTag,
  requiredArchiveCategory,
  requiredLocale,
} from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ArtworkCollection } from "../artwork/ArtworkCollection";
import { GalleryGroups } from "../galleries/GalleryGroups";
import { OpeningMediaCollection, StoryMediaCollection } from "../hierarchy/MediaCollection";
import { StoryRecords } from "../hierarchy/StoryRecords";

export function ArchiveGroupPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const category = requiredArchiveCategory(params["archive-category"]);
  const group = use(getArchiveGroup(locale, category, params["group-id"] ?? ""));
  if (group.archiveCategory !== category) throw new ApiError(t("errors.wrongArchiveCategory"), 404);
  const language = localeLanguageTag(locale);
  const location = useLocation();
  const basePath = `/${locale}/archives/${category}/${encodeURIComponent(group.id)}`;
  const image = group.representativeAssetReference?.previewUrl ?? undefined;

  return (
    <ArchivePage
      description={t("archive.groupDescription", { name: group.name })}
      image={image}
      title={group.name || t("archive.untitledGroup")}
    >
      <BackLink to={`/${locale}/archives/${category}`}>
        {t("archive.backToCategory", { name: archiveCategoryLabel(category, t) })}
      </BackLink>
      <PageHeader
        eyebrow={archiveCategoryLabel(category, t)}
        meta={
          <>
            <code translate="no">{group.id}</code>
            <span>{t("story.count", { count: group.stories.length })}</span>
          </>
        }
        title={group.name || t("archive.untitledGroup")}
        titleLanguage={language}
      />
      <StoryRecords basePath={basePath} locale={locale} stories={group.stories} />
      {group.gallery ? <GalleryGroups gallery={group.gallery} locale={locale} /> : null}
      <OpeningMediaCollection
        from={`${location.pathname}${location.search}`}
        locale={locale}
        media={group.openingMedia}
      />
      <StoryMediaCollection
        from={`${location.pathname}${location.search}`}
        locale={locale}
        media={group.media}
      />
      <ArtworkCollection
        artworks={group.imageReferences}
        eyebrow={t("artwork.archiveReferences")}
        from={`${location.pathname}${location.search}`}
        language={language}
        locale={locale}
      />
    </ArchivePage>
  );
}
