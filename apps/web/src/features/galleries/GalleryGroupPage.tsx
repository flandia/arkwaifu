import { use, type ReactNode } from "react";
import { useParams } from "react-router";
import { getNarrativeImageAssetWithMaterials } from "../../api/images";
import { ApiError } from "../../api/client";
import { getGallery } from "../../api/galleries";
import type {
  NarrativeImageAsset,
  GalleryDetail,
  GalleryGroup,
  GalleryReference,
  Locale,
  MaterialAsset,
} from "../../api/types";
import { useUi, useUiLanguage } from "../../i18n";
import { localeLanguageTag, requiredLocale, TransitionLink } from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ActionLink } from "../../shared/ui/Action";
import { ArtworkGrid } from "../../shared/ui/ArtworkGrid";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";
import { ArtworkImage } from "../artwork/ArtworkCard";
import { MaterialAssetCard } from "../artwork/MaterialAssetCard";

function memberPath(locale: Locale, galleryID: string, groupID: string, cgID: string): string {
  return `/${locale}/galleries/${encodeURIComponent(galleryID)}/groups/${encodeURIComponent(groupID)}/${encodeURIComponent(cgID)}`;
}

function ViewerNavigation({
  group,
  galleryID,
  locale,
  selected,
}: {
  group: GalleryGroup;
  galleryID: string;
  locale: Locale;
  selected: GalleryReference;
}) {
  const { t } = useUi();
  const selectedIndex = group.references.indexOf(selected);
  const previous = group.references[selectedIndex - 1];
  const next = group.references[selectedIndex + 1];

  return (
    <>
      <Eyebrow>{t("gallery.groupArtworks")}</Eyebrow>
      <p className="mb-5 font-mono text-4xl font-black tabular-nums">
        {selectedIndex + 1}
        <span className="text-muted">/{group.references.length}</span>
      </p>
      <div className="mb-6 grid grid-cols-2 gap-3">
        {previous ? (
          <TransitionLink
            className="grid min-h-12 place-items-center border-2 border-ink bg-white font-black no-underline hover:bg-brand-soft"
            to={memberPath(locale, galleryID, group.id, previous.cgID)}
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
            to={memberPath(locale, galleryID, group.id, next.cgID)}
            transition="forward"
          >
            {t("gallery.next")} →
          </TransitionLink>
        ) : null}
      </div>
      <ol className="scrollbar-none m-0 grid max-h-80 list-none gap-2 overflow-y-auto p-0">
        {group.references.map((artwork, index) => (
          <li key={artwork.cgID}>
            <TransitionLink
              aria-current={artwork.cgID === selected.cgID ? "page" : undefined}
              className="grid min-h-11 grid-cols-[2rem_minmax(0,1fr)] items-center border-2 border-ink px-3 py-2 text-xs no-underline hover:bg-brand-soft aria-[current=page]:bg-brand aria-[current=page]:text-white"
              to={memberPath(locale, galleryID, group.id, artwork.cgID)}
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
        <Eyebrow>{t("artwork.imageUnavailable")}</Eyebrow>
        <p className="m-0 max-w-md leading-relaxed text-muted">{t("gallery.unavailableHint")}</p>
      </div>
    </div>
  );
}

function GalleryGroupLayout({
  artwork,
  gallery,
  group,
  locale,
  media,
  selected,
  sources,
}: {
  artwork: NarrativeImageAsset | null;
  gallery: GalleryDetail;
  group: GalleryGroup;
  locale: Locale;
  media: ReactNode;
  selected: GalleryReference;
  sources: MaterialAsset[];
}) {
  const { t } = useUi();
  const { language: uiLanguage } = useUiLanguage();
  const selectedIndex = group.references.indexOf(selected);
  const language = localeLanguageTag(locale);
  const title = group.name || gallery.name || t("gallery.untitledGroup");

  return (
    <ArchivePage
      description={group.description || gallery.description || t("gallery.detailDescription")}
      image={selected.previewUrl ?? undefined}
      title={title}
    >
      <BackLink to={`/${locale}/galleries/${encodeURIComponent(gallery.id)}`}>
        {t("gallery.backToGallery")}
      </BackLink>
      <PageHeader
        description={group.description || gallery.description || undefined}
        descriptionLanguage={group.description || gallery.description ? language : undefined}
        eyebrow={gallery.name || t("gallery.title")}
        meta={
          <>
            <span>
              {t("gallery.memberPosition", {
                current: selectedIndex + 1,
                total: group.references.length,
              })}
            </span>
            <code translate="no">{selected.cgID}</code>
            {group.relatedStageID ? <code translate="no">{group.relatedStageID}</code> : null}
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
            group={group}
            galleryID={gallery.id}
            locale={locale}
            selected={selected}
          />
          {artwork ? (
            <div className="mt-6 grid gap-3">
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
          ) : null}
        </aside>
      </div>

      {sources.length && artwork ? (
        <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="gallery-source-panels">
          <SectionHeading
            eyebrow={t("artwork.panelAssembly")}
            meta={new Intl.NumberFormat(uiLanguage).format(sources.length)}
            title={t("artwork.retainedSources")}
            titleId="gallery-source-panels"
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
    </ArchivePage>
  );
}

function AvailableGalleryArtwork({
  group,
  gallery,
  locale,
  selected,
}: {
  group: GalleryGroup;
  gallery: GalleryDetail;
  locale: Locale;
  selected: GalleryReference;
}) {
  const [artwork, sources] = use(
    getNarrativeImageAssetWithMaterials(selected.asset.category, selected.asset.id),
  );
  const title = group.name || gallery.name;
  return (
    <GalleryGroupLayout
      artwork={artwork}
      group={group}
      gallery={gallery}
      locale={locale}
      media={
        <ArtworkImage
          artwork={artwork}
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

export function GalleryGroupPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const gallery = use(getGallery(locale, params["gallery-id"] ?? ""));
  const group = gallery.groups.find((candidate) => candidate.id === params["group-id"]);
  if (!group?.references.length) throw new ApiError(t("errors.missingGalleryGroup"), 404);
  const selected = params["reference-id"]
    ? group.references.find((artwork) => artwork.cgID === params["reference-id"])
    : group.references[0];
  if (!selected) throw new ApiError(t("errors.missingGalleryArtwork"), 404);

  return selected.previewUrl ? (
    <AvailableGalleryArtwork group={group} gallery={gallery} locale={locale} selected={selected} />
  ) : (
    <GalleryGroupLayout
      artwork={null}
      group={group}
      gallery={gallery}
      locale={locale}
      media={<UnavailableArtwork />}
      selected={selected}
      sources={[]}
    />
  );
}
