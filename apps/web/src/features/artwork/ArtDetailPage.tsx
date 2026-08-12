import { use, ViewTransition } from "react";
import { useParams, useSearchParams } from "react-router";
import {
  ApiError,
  artTransitionName,
  formatBytes,
  getArtContext,
  getArtData,
  type ArtDetail,
  type ArtCategory,
} from "../../api";
import { useUi, useUiLanguage } from "../../i18n";
import { localeLanguageTag, requiredLocale, useCategoryLabel } from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ActionLink, ArtworkGrid, Eyebrow, SectionHeading } from "../../shared/ui";
import { ArtworkImage } from "./ArtworkCard";
import { ArtworkOccurrences, SiblingCharacters } from "./ArtworkContext";
import { SourceLayerCard } from "./SourceLayerCard";

function isArtCategory(value: string | undefined): value is ArtCategory {
  return value === "image" || value === "background" || value === "item" || value === "character";
}

function ArtworkHero({ art, title }: { art: ArtDetail; title: string }) {
  return (
    <ViewTransition default="none" name={artTransitionName(art.category, art.id)} share="morph">
      <figure
        className="checkerboard m-0 grid place-items-center overflow-hidden border-[3px] border-ink"
        style={{ aspectRatio: `${art.image.width} / ${art.image.height}` }}
      >
        <ArtworkImage art={art} alt={title} priority />
      </figure>
    </ViewTransition>
  );
}

export function ArtDetailPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const labelCategory = useCategoryLabel();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  if (!isArtCategory(params.category)) throw new ApiError(t("errors.missingArtCategory"), 404);
  const category = params.category;
  const artID = params.artID ?? "";
  const artRequest = getArtData(category, artID);
  const contextRequest = getArtContext(locale, category, artID);
  const [art, sources] = use(artRequest);
  const context = use(contextRequest);
  const [searchParams] = useSearchParams();
  const from = searchParams.get("from");
  const backTo =
    typeof from === "string" && from.startsWith(`/${locale}/`) ? from : `/${locale}/galleries`;
  const categoryName = labelCategory(art.category);
  const names = [...new Set(context.names.map((name) => name.trim()).filter(Boolean))];
  const title = names[0] || t("art.artwork", { category: categoryName });

  return (
    <ArchivePage title={names[0] || art.id}>
      <BackLink to={backTo}>{t("art.backToCollection")}</BackLink>
      <PageHeader
        description={names.length > 1 ? names.slice(1).join(" · ") : undefined}
        descriptionLanguage={names.length > 1 ? localeLanguageTag(locale) : undefined}
        eyebrow={t("art.record", { category: categoryName })}
        meta={
          <>
            <span>
              {new Intl.NumberFormat(language).format(art.image.width)} ×{" "}
              {new Intl.NumberFormat(language).format(art.image.height)} px
            </span>
            <span>{formatBytes(art.image.byteSize, language)}</span>
          </>
        }
        title={title}
        titleLanguage={names.length ? localeLanguageTag(locale) : undefined}
      />
      <div className="mt-12 grid items-start gap-8 min-[56rem]:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]">
        <ArtworkHero art={art} title={`${title} — ${art.id}`} />
        <aside
          className="border-2 border-ink bg-surface p-6 min-[56rem]:sticky min-[56rem]:top-6"
          aria-label={t("art.detailsLabel")}
        >
          <Eyebrow>{t("art.archiveIdentity")}</Eyebrow>
          <code className="mb-8 block break-words text-sm font-extrabold" translate="no">
            {art.category}/{art.id}
          </code>
          <dl className="mb-8 border-t-2 border-ink">
            {[
              [t("art.format"), t("art.losslessPng")],
              [
                t("art.dimensions"),
                `${new Intl.NumberFormat(language).format(art.image.width)} × ${new Intl.NumberFormat(language).format(art.image.height)}`,
              ],
              [t("art.fileSize"), formatBytes(art.image.byteSize, language)],
              [t("art.sourceLayers"), new Intl.NumberFormat(language).format(sources.length)],
            ].map(([term, value]) => (
              <div className="grid grid-cols-2 gap-4 border-b border-line py-4" key={term}>
                <dt className="text-xs font-extrabold tracking-wide text-muted uppercase">
                  {term}
                </dt>
                <dd className="m-0 text-right text-xs tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <ActionLink
            className="w-full"
            adornment="external"
            rel="noreferrer"
            target="_blank"
            to={art.image.contentUrl}
          >
            {t("art.openOriginal")}
          </ActionLink>
        </aside>
      </div>
      {sources.length ? (
        <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="source-layers-title">
          <SectionHeading
            eyebrow={t("art.characterAssembly")}
            meta={new Intl.NumberFormat(language).format(sources.length)}
            title={t("art.retainedLayers")}
            titleId="source-layers-title"
          />
          <ArtworkGrid>
            {sources.map((source) => (
              <SourceLayerCard composition={art} key={source.id} source={source} />
            ))}
          </ArtworkGrid>
        </section>
      ) : null}
      {category === "character" ? (
        <SiblingCharacters context={context} currentArtID={art.id} from={backTo} locale={locale} />
      ) : null}
      <ArtworkOccurrences context={context} locale={locale} />
    </ArchivePage>
  );
}
