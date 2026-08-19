import { use } from "react";
import { useLocation, useParams } from "react-router";
import { getMaterialAsset } from "../../api/images";
import { formatBytes } from "../../api/utils";
import { useUi, useUiLanguage } from "../../i18n";
import { requiredLocale, requiredNarrativeImageCategory, useCategoryLabel } from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ActionLink } from "../../shared/ui/Action";
import { ArtworkGrid } from "../../shared/ui/ArtworkGrid";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";
import { ArtworkCard } from "./ArtworkCard";

export function MaterialAssetDetailPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const labelCategory = useCategoryLabel();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const category = requiredNarrativeImageCategory(params["asset-category"]);
  const source = use(getMaterialAsset(category, params["asset-id"] ?? ""));
  const location = useLocation();
  const currentPath = `${location.pathname}${location.search}`;
  const from = typeof location.state?.from === "string" ? location.state.from : undefined;
  const backTo = from?.startsWith(`/${locale}/`) ? from : `/${locale}/galleries`;
  const categoryName = labelCategory(source.category);
  const kind =
    source.materialType === "character" && source.role
      ? t(`artwork.${source.role === "whole_body" ? "wholeBody" : source.role}`)
      : t("artwork.artworkPanel", { position: 1 });
  const details = [
    [t("artwork.format"), t("artwork.losslessPng")],
    [
      t("artwork.dimensions"),
      `${new Intl.NumberFormat(language).format(source.width)} × ${new Intl.NumberFormat(language).format(source.height)}`,
    ],
    [t("artwork.fileSize"), formatBytes(source.size, language)],
    [t("artwork.assetCategory"), categoryName],
    [t("artwork.sourceKind"), kind],
    source.characterID ? [t("artwork.characterID"), source.characterID] : null,
    source.variant ? [t("artwork.variant"), source.variant] : null,
  ].filter((detail): detail is string[] => detail !== null);

  return (
    <ArchivePage description={`${categoryName} · ${source.id}`} title={source.id}>
      <BackLink to={backTo}>{t("artwork.backToCollection")}</BackLink>
      <PageHeader
        eyebrow={t("artwork.sourceRecord", { category: categoryName })}
        meta={
          <>
            <span>
              {new Intl.NumberFormat(language).format(source.width)} ×{" "}
              {new Intl.NumberFormat(language).format(source.height)} px
            </span>
            <span>{formatBytes(source.size, language)}</span>
          </>
        }
        title={source.id}
      />
      <div className="mt-12 grid items-start gap-8 min-[56rem]:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]">
        <figure
          className="checkerboard m-0 grid place-items-center overflow-hidden border-[3px] border-ink"
          style={{ aspectRatio: `${source.width} / ${source.height}` }}
        >
          <img
            alt={source.id}
            className="block size-full object-contain"
            height={source.height}
            src={source.url}
            width={source.width}
          />
        </figure>
        <aside
          aria-label={t("artwork.sourceDetailsLabel")}
          className="border-2 border-ink bg-surface p-6 min-[56rem]:sticky min-[56rem]:top-6"
        >
          <Eyebrow>{t("artwork.archiveIdentity")}</Eyebrow>
          <code className="mb-8 block break-words text-sm font-extrabold" translate="no">
            material/{source.category}/{source.id}
          </code>
          <dl className="mb-8 border-t-2 border-ink">
            {details.map(([term, value]) => (
              <div className="grid grid-cols-2 gap-4 border-b border-line py-4" key={term}>
                <dt className="text-xs font-extrabold tracking-wide text-muted uppercase">
                  {term}
                </dt>
                <dd className="m-0 break-all text-right text-xs tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-3">
            <ActionLink download to={source.url}>
              {t("artwork.downloadOriginal")}
            </ActionLink>
            <ActionLink
              adornment="external"
              rel="noreferrer"
              target="_blank"
              to={source.url}
              variant="secondary"
            >
              {t("artwork.openOriginal")}
            </ActionLink>
          </div>
        </aside>
      </div>
      <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="source-used-by-title">
        <SectionHeading
          eyebrow={t("artwork.reverseReferences")}
          meta={new Intl.NumberFormat(language).format(source.reverseReferences.length)}
          title={t("artwork.imageReferences")}
          titleId="source-used-by-title"
        />
        {source.reverseReferences.length ? (
          <ArtworkGrid>
            {source.reverseReferences.map((artwork) => (
              <ArtworkCard
                category={artwork.category}
                from={currentPath}
                id={artwork.id}
                key={`${artwork.category}:${artwork.id}`}
                language={language}
                locale={locale}
                shared={false}
                thumbnailUrl={null}
                title={artwork.id}
              />
            ))}
          </ArtworkGrid>
        ) : (
          <p className="m-0 text-muted">{t("artwork.noNarrativeAssetReferences")}</p>
        )}
      </section>
    </ArchivePage>
  );
}
