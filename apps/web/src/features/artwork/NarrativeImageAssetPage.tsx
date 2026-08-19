import { use, ViewTransition } from "react";
import { useLocation, useParams } from "react-router";
import {
  getNarrativeImageAssetWithMaterials,
  getNarrativeImageReverseReferences,
} from "../../api/images";
import type { NarrativeImageAsset } from "../../api/types";
import { assetTransitionName, formatBytes } from "../../api/utils";
import { useUi, useUiLanguage } from "../../i18n";
import {
  localeLanguageTag,
  requiredLocale,
  requiredNarrativeImageCategory,
  useCategoryLabel,
} from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ActionLink } from "../../shared/ui/Action";
import { ArtworkGrid } from "../../shared/ui/ArtworkGrid";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";
import { ArtworkImage } from "./ArtworkCard";
import {
  ArtworkGalleries,
  NarrativeImageOccurrences,
  BundleTextures,
  CharacterVariants,
} from "./NarrativeImageReverseReferences";
import { MaterialAssetCard } from "./MaterialAssetCard";

function ArtworkHero({ artwork, title }: { artwork: NarrativeImageAsset; title: string }) {
  return (
    <ViewTransition
      default="none"
      name={assetTransitionName(artwork.category, artwork.id)}
      share="morph"
    >
      <figure
        className="checkerboard m-0 grid place-items-center overflow-hidden border-[3px] border-ink"
        style={{ aspectRatio: `${artwork.width} / ${artwork.height}` }}
      >
        <ArtworkImage artwork={artwork} alt={title} priority />
      </figure>
    </ViewTransition>
  );
}

export function NarrativeImageAssetPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const labelCategory = useCategoryLabel();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const category = requiredNarrativeImageCategory(params["asset-category"]);
  const assetID = params["asset-id"] ?? "";
  const artworkRequest = getNarrativeImageAssetWithMaterials(category, assetID);
  const reverseReferencesRequest = getNarrativeImageReverseReferences(locale, category, assetID);
  const [artwork, sources] = use(artworkRequest);
  const reverseReferences = use(reverseReferencesRequest);
  const location = useLocation();
  const from = typeof location.state?.from === "string" ? location.state.from : undefined;
  const backTo = from?.startsWith(`/${locale}/`) ? from : `/${locale}/galleries`;
  const categoryName = labelCategory(artwork.category);
  const names = [...new Set(reverseReferences.names.map((name) => name.trim()).filter(Boolean))];
  const title = names[0] || t("artwork.artwork", { category: categoryName });

  return (
    <ArchivePage
      description={`${title} · ${categoryName} · ${artwork.id}`}
      image={artwork.previewUrl}
      title={names[0] || artwork.id}
    >
      <BackLink to={backTo}>{t("artwork.backToCollection")}</BackLink>
      <PageHeader
        description={names.length > 1 ? names.slice(1).join(" · ") : undefined}
        descriptionLanguage={names.length > 1 ? localeLanguageTag(locale) : undefined}
        eyebrow={t("artwork.record", { category: categoryName })}
        meta={
          <>
            <span>
              {new Intl.NumberFormat(language).format(artwork.width)} ×{" "}
              {new Intl.NumberFormat(language).format(artwork.height)} px
            </span>
            <span>{formatBytes(artwork.size, language)}</span>
          </>
        }
        title={title}
        titleLanguage={names.length ? localeLanguageTag(locale) : undefined}
      />
      <div className="mt-12 grid items-start gap-8 min-[56rem]:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]">
        <ArtworkHero artwork={artwork} title={`${title} — ${artwork.id}`} />
        <aside
          className="border-2 border-ink bg-surface p-6 min-[56rem]:sticky min-[56rem]:top-6"
          aria-label={t("artwork.detailsLabel")}
        >
          <Eyebrow>{t("artwork.archiveIdentity")}</Eyebrow>
          <code className="mb-8 block break-words text-sm font-extrabold" translate="no">
            narrative/{artwork.category}/{artwork.id}
          </code>
          <dl className="mb-8 border-t-2 border-ink">
            {[
              [t("artwork.format"), t("artwork.losslessPng")],
              [
                t("artwork.dimensions"),
                `${new Intl.NumberFormat(language).format(artwork.width)} × ${new Intl.NumberFormat(language).format(artwork.height)}`,
              ],
              [t("artwork.fileSize"), formatBytes(artwork.size, language)],
              [t("artwork.materials"), new Intl.NumberFormat(language).format(sources.length)],
            ].map(([term, value]) => (
              <div className="grid grid-cols-2 gap-4 border-b border-line py-4" key={term}>
                <dt className="text-xs font-extrabold tracking-wide text-muted uppercase">
                  {term}
                </dt>
                <dd className="m-0 text-right text-xs tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-3">
            <ActionLink download to={artwork.url}>
              {t("artwork.downloadOriginal")}
            </ActionLink>
            <ActionLink
              adornment="external"
              rel="noreferrer"
              target="_blank"
              to={artwork.url}
              variant="secondary"
            >
              {t("artwork.openOriginal")}
            </ActionLink>
          </div>
        </aside>
      </div>
      {sources.length ? (
        <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="source-layers-title">
          <SectionHeading
            eyebrow={
              sources.some((source) => source.materialType === "panel")
                ? t("artwork.panelAssembly")
                : t("artwork.characterAssembly")
            }
            meta={new Intl.NumberFormat(language).format(sources.length)}
            title={t("artwork.retainedSources")}
            titleId="source-layers-title"
          />
          <ArtworkGrid>
            {sources.map((source, index) => (
              <MaterialAssetCard
                artwork={artwork}
                index={index}
                key={`${source.category}:${source.id}`}
                source={source}
              />
            ))}
          </ArtworkGrid>
        </section>
      ) : null}
      <BundleTextures
        reverseReferences={reverseReferences}
        from={`${location.pathname}${location.search}`}
        locale={locale}
      />
      {category === "character" ? (
        <CharacterVariants
          reverseReferences={reverseReferences}
          currentArtworkID={artwork.id}
          from={backTo}
          locale={locale}
        />
      ) : null}
      <ArtworkGalleries locale={locale} reverseReferences={reverseReferences} />
      <NarrativeImageOccurrences locale={locale} reverseReferences={reverseReferences} />
    </ArchivePage>
  );
}
