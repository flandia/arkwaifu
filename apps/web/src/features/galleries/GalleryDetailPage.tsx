import { use } from "react";
import { useParams } from "react-router";
import { getGallery } from "../../api/galleries";
import { useUi } from "../../i18n";
import { localeLanguageTag, requiredLocale, storyParentPath } from "../../navigation";
import { ArchivePage, BackLink, EmptyState, PageHeader } from "../../shared/Page";
import { GalleryDisplays } from "./GalleryDisplays";

export function GalleryDetailPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const gallery = use(getGallery(locale, params.galleryID ?? ""));
  const firstArtwork = gallery.displays
    .flatMap((display) => display.artworks)
    .find((artwork) => artwork.thumbnailContentUrl);
  const language = localeLanguageTag(locale);

  return (
    <ArchivePage
      description={gallery.description || t("gallery.detailDescription")}
      image={firstArtwork?.thumbnailContentUrl ?? undefined}
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
            <span>{t("gallery.displayCount", { count: gallery.displays.length })}</span>
          </>
        }
        title={gallery.name || t("gallery.untitled")}
        titleLanguage={language}
      />
      {gallery.displays.length ? (
        <GalleryDisplays gallery={gallery} locale={locale} />
      ) : (
        <EmptyState title={t("gallery.noDisplays")}>{t("gallery.noDisplaysHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
