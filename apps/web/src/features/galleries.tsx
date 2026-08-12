import { use } from "react";
import { useLocation, useParams } from "react-router";
import { getGalleries, getGalleryData, type GallerySummary } from "../api";
import { useUi, useUiLanguage } from "../i18n";
import { localeLanguageTag, requiredLocale, TransitionLink, useCategoryLabel } from "../navigation";
import {
  AnimatedListItem,
  CollectionControls,
  useCollectionIndex,
} from "../shared/CollectionIndex";
import { ArchivePage, BackLink, EmptyState, PageHeader } from "../shared/Page";
import { ArtworkGrid, CardBackdrop, Eyebrow, SectionHeading } from "../shared/ui";
import { ArtworkCard } from "./artwork/ArtworkCard";

function gallerySearchValues(gallery: GallerySummary): string[] {
  return [gallery.name, gallery.id, gallery.description];
}

export function GalleriesPage() {
  const { t } = useUi();
  const locale = requiredLocale(useParams().locale);
  const galleries = use(getGalleries(locale));
  const index = useCollectionIndex(galleries, gallerySearchValues);
  const language = localeLanguageTag(locale);

  return (
    <ArchivePage title={t("gallery.title")}>
      <PageHeader
        eyebrow={t("gallery.indexEyebrow")}
        meta={<span>{t("common.locale", { locale })}</span>}
        title={t("gallery.title")}
      />
      <CollectionControls
        count={index.visible.length}
        noun={t("collection.galleryNoun", { count: index.visible.length })}
        onOrder={index.setOrder}
        onQuery={index.setQuery}
        order={index.order}
        query={index.query}
      />
      {index.visible.length ? (
        <section
          className="grid border-t-2 border-l-2 border-ink md:grid-cols-2"
          aria-label={t("gallery.label")}
        >
          {index.visible.map((gallery, itemIndex) => (
            <AnimatedListItem id={gallery.id} key={gallery.id}>
              <article className="aspect-video min-w-0 [contain-intrinsic-size:auto_22rem] [content-visibility:auto]">
                <TransitionLink
                  className="group relative flex size-full flex-col justify-end overflow-hidden border-r-2 border-b-2 border-ink bg-brand p-4 text-white no-underline sm:p-5 xl:p-6"
                  to={`/${locale}/galleries/${encodeURIComponent(gallery.id)}`}
                  transition="forward"
                >
                  <CardBackdrop
                    scrim={gallery.previewThumbnailContentUrls?.length ? "dark" : "brand"}
                    sources={gallery.previewThumbnailContentUrls}
                  />
                  <span
                    className="relative z-10 mb-auto font-mono text-2xl font-black text-white/70 tabular-nums sm:text-3xl xl:text-4xl"
                    aria-hidden="true"
                  >
                    {String(itemIndex + 1).padStart(3, "0")}
                  </span>
                  <div className="relative z-10">
                    <Eyebrow className="mb-1 text-white/75 sm:mb-2">{t("gallery.title")}</Eyebrow>
                    <h2
                      className="mb-2 max-w-[22ch] break-words text-[clamp(1.25rem,3vw,2.4rem)] leading-none font-black text-balance sm:mb-3"
                      lang={language}
                    >
                      {gallery.name || t("gallery.untitled")}
                    </h2>
                    <p
                      className="mb-3 hidden leading-relaxed text-white/80 sm:line-clamp-2 xl:line-clamp-3"
                      lang={language}
                      title={gallery.description || undefined}
                    >
                      {gallery.description || t("gallery.noDescription")}
                    </p>
                    <code className="hidden text-white/70 sm:block" translate="no">
                      {gallery.id}
                    </code>
                  </div>
                  <span
                    className="absolute top-3 right-3 z-10 grid size-9 place-items-center border-2 border-white bg-black/35 font-black sm:top-5 sm:right-5 sm:size-10"
                    aria-hidden="true"
                  >
                    ↗
                  </span>
                </TransitionLink>
              </article>
            </AnimatedListItem>
          ))}
        </section>
      ) : (
        <EmptyState title={t("gallery.noMatching")}>{t("gallery.noMatchingHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}

export function GalleryDetailPage() {
  const { t } = useUi();
  const { language: uiLanguage } = useUiLanguage();
  const labelCategory = useCategoryLabel();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const galleryID = params.galleryID ?? "";
  const [gallery, entries] = use(getGalleryData(locale, galleryID));
  const location = useLocation();
  const language = localeLanguageTag(locale);
  const identities = new Map<string, number>();
  for (const entry of entries) {
    const key = `${entry.category}:${entry.artID}`;
    identities.set(key, (identities.get(key) ?? 0) + 1);
  }

  return (
    <ArchivePage title={gallery.name}>
      <BackLink to={`/${locale}/galleries`}>{t("gallery.back")}</BackLink>
      <PageHeader
        description={gallery.description || t("gallery.detailDescription")}
        descriptionLanguage={gallery.description ? language : undefined}
        eyebrow={t("gallery.title")}
        meta={
          <>
            <code translate="no">{gallery.id}</code>
            <span>{t("gallery.entryCount", { count: entries.length })}</span>
          </>
        }
        title={gallery.name || t("gallery.untitled")}
        titleLanguage={language}
      />
      {entries.length ? (
        <section className="mt-16" aria-labelledby="gallery-art-title">
          <SectionHeading
            eyebrow={t("gallery.selection")}
            meta={new Intl.NumberFormat(uiLanguage).format(entries.length)}
            title={t("gallery.artwork")}
            titleId="gallery-art-title"
          />
          <ArtworkGrid>
            {entries.map((entry) => {
              const key = `${entry.category}:${entry.artID}`;
              return (
                <ArtworkCard
                  category={entry.category}
                  from={`${location.pathname}${location.search}`}
                  id={entry.artID}
                  key={entry.id}
                  language={language}
                  locale={locale}
                  shared={identities.get(key) === 1}
                  subtitle={entry.description}
                  thumbnailUrl={entry.thumbnailContentUrl}
                  title={entry.name || `${labelCategory(entry.category)} ${entry.position}`}
                />
              );
            })}
          </ArtworkGrid>
        </section>
      ) : (
        <EmptyState title={t("gallery.noEntries")}>{t("gallery.noEntriesHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
