import { use } from "react";
import { useParams } from "react-router";
import { getGallery } from "../../api/galleries";
import { useUi } from "../../i18n";
import { localeLanguageTag, requiredLocale, storyParentPath } from "../../navigation";
import { ArchivePage, BackLink, EmptyState, PageHeader } from "../../shared/Page";
import { GalleryGroups } from "./GalleryGroups";

export function GalleryDetailPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const gallery = use(getGallery(locale, params["gallery-id"] ?? ""));
  const firstArtwork = gallery.groups
    .flatMap((group) => group.references)
    .find((artwork) => artwork.previewUrl);
  const language = localeLanguageTag(locale);

  return (
    <ArchivePage
      description={gallery.description || t("gallery.detailDescription")}
      image={firstArtwork?.previewUrl ?? undefined}
      title={gallery.name || t("gallery.untitled")}
    >
      <BackLink to={storyParentPath(locale, gallery.parent)}>{t("gallery.backToOwner")}</BackLink>
      <PageHeader
        description={gallery.description || t("gallery.detailDescription")}
        descriptionLanguage={gallery.description ? language : undefined}
        eyebrow={t("gallery.title")}
        meta={
          <>
            <code translate="no">{gallery.id}</code>
            <span>{t("gallery.groupCount", { count: gallery.groups.length })}</span>
          </>
        }
        title={gallery.name || t("gallery.untitled")}
        titleLanguage={language}
      />
      {gallery.groups.length ? (
        <GalleryGroups gallery={gallery} locale={locale} />
      ) : (
        <EmptyState title={t("gallery.noGroups")}>{t("gallery.noGroupsHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
