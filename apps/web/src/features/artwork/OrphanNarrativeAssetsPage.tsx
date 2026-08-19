import { use } from "react";
import { useLocation, useParams } from "react-router";
import { getOrphanNarrativeAssets } from "../../api/orphans";
import { useUi, useUiLanguage } from "../../i18n";
import { requiredLocale } from "../../navigation";
import { ArchivePage, EmptyState, PageHeader } from "../../shared/Page";
import { MediaResourceCollection } from "../hierarchy/MediaCollection";
import { ArtworkCollection } from "./ArtworkCollection";

export function OrphanNarrativeAssetsPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const locale = requiredLocale(useParams().locale);
  const location = useLocation();
  const assets = use(getOrphanNarrativeAssets(locale));
  const artworks = assets.filter((asset) => asset.format === "image");
  const media = assets.filter((asset) => asset.format !== "image");
  const resourceCount = assets.length;
  const artworkCards = artworks.map((artwork) => ({
    asset: { category: artwork.category, id: artwork.id },
    previewUrl: artwork.previewUrl,
  }));

  return (
    <ArchivePage
      description={t("orphan.description")}
      image={artworkCards[0]?.previewUrl}
      title={t("orphan.title")}
    >
      <PageHeader
        description={t("orphan.description")}
        eyebrow={t("orphan.eyebrow")}
        meta={<span>{t("orphan.resourceCount", { count: resourceCount })}</span>}
        title={t("orphan.title")}
      />
      {resourceCount ? (
        <>
          <ArtworkCollection
            artworks={artworkCards}
            eyebrow={t("orphan.assetCategory")}
            from={`${location.pathname}${location.search}`}
            language={language}
            locale={locale}
          />
          <MediaResourceCollection
            from={`${location.pathname}${location.search}`}
            locale={locale}
            media={media}
          />
        </>
      ) : (
        <EmptyState title={t("orphan.empty")}>{t("orphan.emptyHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
