import { use } from "react";
import { useLocation, useParams } from "react-router";
import { getUnreferencedArts } from "../../api";
import { useUi, useUiLanguage } from "../../i18n";
import { requiredLocale } from "../../navigation";
import { ArchivePage, EmptyState, PageHeader } from "../../shared/Page";
import { ArtworkCollection } from "./ArtworkCollection";

export function UnreferencedArtPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const locale = requiredLocale(useParams().locale);
  const location = useLocation();
  const arts = use(getUnreferencedArts());
  const artworks = arts.map((art) => ({
    artID: art.id,
    category: art.category,
    thumbnailContentUrl: art.thumbnailContentUrl,
  }));

  return (
    <ArchivePage title={t("unreferenced.title")}>
      <PageHeader
        description={t("unreferenced.description")}
        eyebrow={t("unreferenced.eyebrow")}
        meta={<span>{t("unreferenced.artworkCount", { count: arts.length })}</span>}
        title={t("unreferenced.title")}
      />
      {artworks.length ? (
        <ArtworkCollection
          artworks={artworks}
          eyebrow={t("unreferenced.assetCategory")}
          from={`${location.pathname}${location.search}`}
          language={language}
          locale={locale}
        />
      ) : (
        <EmptyState title={t("unreferenced.empty")}>{t("unreferenced.emptyHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
