import { use } from "react";
import { useLocation, useParams } from "react-router";
import { getUnclassifiedArts } from "../../api";
import { useUi, useUiLanguage } from "../../i18n";
import { requiredLocale } from "../../navigation";
import { ArchivePage, EmptyState, PageHeader } from "../../shared/Page";
import { ArtworkCollection } from "./ArtworkCollection";

export function UnclassifiedPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const locale = requiredLocale(useParams().locale);
  const location = useLocation();
  const arts = use(getUnclassifiedArts());
  const artworks = arts.map((art) => ({
    artID: art.id,
    category: art.category,
    thumbnailContentUrl: art.thumbnailContentUrl,
  }));

  return (
    <ArchivePage title={t("unclassified.title")}>
      <PageHeader
        description={t("unclassified.description")}
        eyebrow={t("unclassified.eyebrow")}
        meta={<span>{t("unclassified.artworkCount", { count: arts.length })}</span>}
        title={t("unclassified.title")}
      />
      {artworks.length ? (
        <ArtworkCollection
          artworks={artworks}
          eyebrow={t("unclassified.assetCategory")}
          from={`${location.pathname}${location.search}`}
          language={language}
          locale={locale}
        />
      ) : (
        <EmptyState title={t("unclassified.empty")}>{t("unclassified.emptyHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
