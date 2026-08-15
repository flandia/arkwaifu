import { use, type ReactNode } from "react";
import { useParams } from "react-router";
import { getArtWithSources } from "../../api/artwork";
import { ApiError } from "../../api/client";
import { getGallery } from "../../api/galleries";
import type {
  ArtDetail,
  GalleryDetail,
  GalleryDisplay,
  GalleryDisplayArtwork,
  Locale,
  SourceArt,
} from "../../api/types";
import { useUi, useUiLanguage } from "../../i18n";
import { localeLanguageTag, requiredLocale, TransitionLink } from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ActionLink } from "../../shared/ui/Action";
import { ArtworkGrid } from "../../shared/ui/ArtworkGrid";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";
import { ArtworkImage } from "../artwork/ArtworkCard";
import { SourceLayerCard } from "../artwork/SourceLayerCard";

function memberPath(locale: Locale, galleryID: string, displayID: string, cgID: string): string {
  return `/${locale}/galleries/${encodeURIComponent(galleryID)}/displays/${encodeURIComponent(displayID)}/${encodeURIComponent(cgID)}`;
}

function ViewerNavigation({
  display,
  galleryID,
  locale,
  selected,
}: {
  display: GalleryDisplay;
  galleryID: string;
  locale: Locale;
  selected: GalleryDisplayArtwork;
}) {
  const { t } = useUi();
  const selectedIndex = display.artworks.indexOf(selected);
  const previous = display.artworks[selectedIndex - 1];
  const next = display.artworks[selectedIndex + 1];

  return (
    <>
      <Eyebrow>{t("gallery.siblings")}</Eyebrow>
      <p className="mb-5 font-mono text-4xl font-black tabular-nums">
        {selectedIndex + 1}
        <span className="text-muted">/{display.artworks.length}</span>
      </p>
      <div className="mb-6 grid grid-cols-2 gap-3">
        {previous ? (
          <TransitionLink
            className="grid min-h-12 place-items-center border-2 border-ink bg-white font-black no-underline hover:bg-brand-soft"
            to={memberPath(locale, galleryID, display.id, previous.cgID)}
            transition="back"
          >
            ← {t("gallery.previous")}
          </TransitionLink>
        ) : (
          <span />
        )}
        {next ? (
          <TransitionLink
            className="grid min-h-12 place-items-center border-2 border-ink bg-brand font-black text-white no-underline hover:bg-ink"
            to={memberPath(locale, galleryID, display.id, next.cgID)}
            transition="forward"
          >
            {t("gallery.next")} →
          </TransitionLink>
        ) : null}
      </div>
      <ol className="scrollbar-none m-0 grid max-h-80 list-none gap-2 overflow-y-auto p-0">
        {display.artworks.map((artwork, index) => (
          <li key={artwork.cgID}>
            <TransitionLink
              aria-current={artwork.cgID === selected.cgID ? "page" : undefined}
              className="grid min-h-11 grid-cols-[2rem_minmax(0,1fr)] items-center border-2 border-ink px-3 py-2 text-xs no-underline hover:bg-brand-soft aria-[current=page]:bg-brand aria-[current=page]:text-white"
              to={memberPath(locale, galleryID, display.id, artwork.cgID)}
            >
              <strong className="font-mono tabular-nums">
                {String(index + 1).padStart(2, "0")}
              </strong>
              <code className="truncate" translate="no">
                {artwork.cgID}
              </code>
            </TransitionLink>
          </li>
        ))}
      </ol>
    </>
  );
}

function UnavailableArtwork() {
  const { t } = useUi();
  return (
    <div className="grid min-h-96 place-items-center bg-paper p-8 text-center">
      <div>
        <Eyebrow>{t("art.imageUnavailable")}</Eyebrow>
        <p className="m-0 max-w-md leading-relaxed text-muted">{t("gallery.unavailableHint")}</p>
      </div>
    </div>
  );
}

function GalleryDisplayLayout({
  art,
  gallery,
  display,
  locale,
  media,
  selected,
  sources,
}: {
  art: ArtDetail | null;
  gallery: GalleryDetail;
  display: GalleryDisplay;
  locale: Locale;
  media: ReactNode;
  selected: GalleryDisplayArtwork;
  sources: SourceArt[];
}) {
  const { t } = useUi();
  const { language: uiLanguage } = useUiLanguage();
  const selectedIndex = display.artworks.indexOf(selected);
  const language = localeLanguageTag(locale);
  const title = display.name || gallery.name || t("gallery.untitledDisplay");

  return (
    <ArchivePage
      description={display.description || gallery.description || t("gallery.detailDescription")}
      image={selected.thumbnailContentUrl ?? undefined}
      title={title}
    >
      <BackLink to={`/${locale}/galleries/${encodeURIComponent(gallery.id)}`}>
        {t("gallery.backToGallery")}
      </BackLink>
      <PageHeader
        description={display.description || gallery.description || undefined}
        descriptionLanguage={display.description || gallery.description ? language : undefined}
        eyebrow={gallery.name || t("gallery.title")}
        meta={
          <>
            <span>
              {t("gallery.memberPosition", {
                current: selectedIndex + 1,
                total: display.artworks.length,
              })}
            </span>
            <code translate="no">{selected.cgID}</code>
            {display.relatedStageID ? <code translate="no">{display.relatedStageID}</code> : null}
          </>
        }
        title={title}
        titleLanguage={language}
      />

      <div className="mt-12 grid items-start gap-8 min-[64rem]:grid-cols-[minmax(0,1fr)_18rem]">
        <figure className="checkerboard m-0 grid min-h-96 place-items-center overflow-hidden border-[3px] border-ink">
          {media}
        </figure>
        <aside className="border-2 border-ink bg-surface p-5 min-[64rem]:sticky min-[64rem]:top-6">
          <ViewerNavigation
            display={display}
            galleryID={gallery.id}
            locale={locale}
            selected={selected}
          />
          {art ? (
            <ActionLink
              adornment="external"
              className="mt-6 w-full"
              rel="noreferrer"
              target="_blank"
              to={art.image.contentUrl}
            >
              {t("art.openOriginal")}
            </ActionLink>
          ) : null}
        </aside>
      </div>

      {sources.length && art ? (
        <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="gallery-source-panels">
          <SectionHeading
            eyebrow={t("art.compositeAssembly")}
            meta={new Intl.NumberFormat(uiLanguage).format(sources.length)}
            title={t("art.retainedSources")}
            titleId="gallery-source-panels"
          />
          <ArtworkGrid>
            {sources.map((source, index) => (
              <SourceLayerCard
                composition={art}
                index={index}
                key={`${source.category}:${source.id}`}
                source={source}
              />
            ))}
          </ArtworkGrid>
        </section>
      ) : null}
    </ArchivePage>
  );
}

function AvailableGalleryArtwork({
  display,
  gallery,
  locale,
  selected,
}: {
  display: GalleryDisplay;
  gallery: GalleryDetail;
  locale: Locale;
  selected: GalleryDisplayArtwork;
}) {
  const [art, sources] = use(getArtWithSources(selected.category, selected.artID));
  const title = display.name || gallery.name;
  return (
    <GalleryDisplayLayout
      art={art}
      display={display}
      gallery={gallery}
      locale={locale}
      media={
        <ArtworkImage
          art={art}
          alt={`${title} — ${selected.cgID}`}
          className="block h-auto w-full object-contain"
          priority
        />
      }
      selected={selected}
      sources={sources}
    />
  );
}

export function GalleryDisplayPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const gallery = use(getGallery(locale, params.galleryID ?? ""));
  const display = gallery.displays.find((candidate) => candidate.id === params.displayID);
  if (!display?.artworks.length) throw new ApiError(t("errors.missingGalleryDisplay"), 404);
  const selected = params.cgID
    ? display.artworks.find((artwork) => artwork.cgID === params.cgID)
    : display.artworks[0];
  if (!selected) throw new ApiError(t("errors.missingGalleryArtwork"), 404);

  return selected.thumbnailContentUrl ? (
    <AvailableGalleryArtwork
      display={display}
      gallery={gallery}
      locale={locale}
      selected={selected}
    />
  ) : (
    <GalleryDisplayLayout
      art={null}
      display={display}
      gallery={gallery}
      locale={locale}
      media={<UnavailableArtwork />}
      selected={selected}
      sources={[]}
    />
  );
}
