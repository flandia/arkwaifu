import { use } from "react";
import { useLocation, useParams } from "react-router";
import { ApiError } from "../../api/client";
import { getArchiveGroup } from "../../api/archives";
import { useUi } from "../../i18n";
import {
  archiveKindLabel,
  localeLanguageTag,
  requiredArchiveKind,
  requiredLocale,
} from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ArtworkCollection } from "../artwork/ArtworkCollection";
import { GalleryDisplays } from "../galleries/GalleryDisplays";
import { OpeningMediaCollection } from "../hierarchy/MediaCollection";
import { StoryRecords } from "../hierarchy/StoryRecords";

export function ArchiveGroupPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const kind = requiredArchiveKind(params.kind);
  const group = use(getArchiveGroup(locale, kind, params.groupID ?? ""));
  if (group.kind !== kind) throw new ApiError(t("errors.wrongArchiveKind"), 404);
  const language = localeLanguageTag(locale);
  const location = useLocation();
  const basePath = `/${locale}/archives/${kind}/${encodeURIComponent(group.id)}`;
  const image = group.representativeArtReference?.thumbnailContentUrl ?? undefined;

  return (
    <ArchivePage
      description={t("archive.groupDescription", { name: group.name })}
      image={image}
      title={group.name || t("archive.untitledGroup")}
    >
      <BackLink to={`/${locale}/archives/${kind}`}>
        {t("archive.backToKind", { name: archiveKindLabel(kind, t) })}
      </BackLink>
      <PageHeader
        eyebrow={archiveKindLabel(kind, t)}
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
      {group.gallery ? <GalleryDisplays gallery={group.gallery} locale={locale} /> : null}
      <OpeningMediaCollection
        from={`${location.pathname}${location.search}`}
        locale={locale}
        media={group.openingMedia}
      />
      <ArtworkCollection
        artworks={group.artReferences}
        eyebrow={t("art.archiveReferences")}
        from={`${location.pathname}${location.search}`}
        language={language}
        locale={locale}
      />
    </ArchivePage>
  );
}
