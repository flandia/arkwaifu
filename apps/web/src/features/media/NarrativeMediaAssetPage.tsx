import { use } from "react";
import { useLocation, useParams } from "react-router";
import { ApiError } from "../../api/client";
import { getNarrativeMediaAsset, getNarrativeMediaReverseReferences } from "../../api/media";
import type {
  Locale,
  NarrativeMediaAsset,
  NarrativeMediaCategory,
  StoryParent,
} from "../../api/types";
import { formatBytes } from "../../api/utils";
import { useUi, useUiLanguage } from "../../i18n";
import {
  archiveCategoryLabel,
  localeLanguageTag,
  requiredLocale,
  storyParentPath,
  TransitionLink,
} from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ActionLink } from "../../shared/ui/Action";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";
import { StoryOccurrences } from "../artwork/NarrativeImageReverseReferences";

function isNarrativeMediaCategory(value: string | undefined): value is NarrativeMediaCategory {
  return value === "audio" || value === "video";
}

function MediaPlayer({ media }: { media: NarrativeMediaAsset }) {
  return (
    <figure className="m-0 grid min-h-44 place-items-center overflow-hidden border-[3px] border-ink bg-black">
      {media.category === "video" ? (
        // oxlint-disable-next-line jsx-a11y/media-has-caption
        <video className="block h-auto w-full" controls preload="metadata">
          <source src={media.url} type={media.mime} />
        </video>
      ) : (
        // oxlint-disable-next-line jsx-a11y/media-has-caption
        <audio className="mx-4 w-[calc(100%_-_2rem)] max-w-3xl" controls preload="metadata">
          <source src={media.url} type={media.mime} />
        </audio>
      )}
    </figure>
  );
}

function CollectionReferences({
  collections,
  locale,
}: {
  collections: StoryParent[];
  locale: Locale;
}) {
  const { t } = useUi();
  const language = localeLanguageTag(locale);
  if (!collections.length) return null;

  return (
    <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="media-collections-title">
      <SectionHeading
        eyebrow={t("mediaAsset.collectionUsage")}
        meta={new Intl.NumberFormat(language).format(collections.length)}
        title={t("mediaAsset.collectionReferences")}
        titleId="media-collections-title"
      />
      <div className="grid gap-6 lg:grid-cols-2">
        {collections.map((parent) => {
          const key =
            parent.kind === "score"
              ? `score:${parent.movementID}:${parent.sectionID}`
              : `archive:${parent.archiveCategory}:${parent.groupID}`;
          const title = parent.kind === "score" ? parent.sectionName : parent.groupName;
          const hierarchy =
            parent.kind === "score"
              ? parent.movementName
              : archiveCategoryLabel(parent.archiveCategory, t);
          return (
            <article className="border-2 border-ink bg-surface p-5" key={key}>
              <Eyebrow>{hierarchy}</Eyebrow>
              <h3 className="m-0 text-2xl font-black" lang={language}>
                <TransitionLink
                  className="hover:bg-brand-soft"
                  to={storyParentPath(locale, parent)}
                  transition="forward"
                >
                  {title || t("story.untitledGroup")}
                </TransitionLink>
              </h3>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function NarrativeMediaAssetPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const category = params["asset-category"];
  if (!isNarrativeMediaCategory(category)) throw new ApiError(t("errors.notFound"), 404);
  const assetID = params["asset-id"] ?? "";
  const mediaRequest = getNarrativeMediaAsset(category, assetID);
  const reverseReferencesRequest = getNarrativeMediaReverseReferences(locale, category, assetID);
  const media = use(mediaRequest);
  const reverseReferences = use(reverseReferencesRequest);
  const location = useLocation();
  const from = typeof location.state?.from === "string" ? location.state.from : undefined;
  const backTo = from?.startsWith(`/${locale}/`) ? from : `/${locale}`;
  const kindLabel = t(`mediaAsset.${media.category}`);
  const dimensions =
    media.width && media.height
      ? `${new Intl.NumberFormat(language).format(media.width)} × ${new Intl.NumberFormat(language).format(media.height)} px`
      : null;
  const details = [
    [t("mediaAsset.format"), media.mime],
    [t("mediaAsset.fileSize"), formatBytes(media.size, language)],
    media.duration
      ? [
          t("mediaAsset.duration"),
          `${new Intl.NumberFormat(language, { maximumFractionDigits: 2 }).format(media.duration)} s`,
        ]
      : null,
    media.sampleRate
      ? [
          t("mediaAsset.sampleRate"),
          `${new Intl.NumberFormat(language).format(media.sampleRate)} Hz`,
        ]
      : null,
    dimensions ? [t("mediaAsset.dimensions"), dimensions] : null,
    media.frameRate
      ? [
          t("mediaAsset.frameRate"),
          `${new Intl.NumberFormat(language, { maximumFractionDigits: 3 }).format(media.frameRate)} fps`,
        ]
      : null,
    media.frameCount
      ? [t("mediaAsset.frameCount"), new Intl.NumberFormat(language).format(media.frameCount)]
      : null,
  ].filter((detail): detail is string[] => detail !== null);

  return (
    <ArchivePage description={`${kindLabel} · ${media.id}`} title={media.id}>
      <BackLink to={backTo}>{t("mediaAsset.backToCollection")}</BackLink>
      <PageHeader
        eyebrow={t("mediaAsset.record", { kind: kindLabel })}
        meta={
          <>
            <span>{media.mime}</span>
            <span>{formatBytes(media.size, language)}</span>
          </>
        }
        title={media.id}
      />
      <div className="mt-12 grid items-start gap-8 min-[56rem]:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]">
        <MediaPlayer media={media} />
        <aside
          aria-label={t("mediaAsset.detailsLabel")}
          className="border-2 border-ink bg-surface p-6 min-[56rem]:sticky min-[56rem]:top-6"
        >
          <Eyebrow>{t("mediaAsset.archiveIdentity")}</Eyebrow>
          <code className="mb-8 block break-words text-sm font-extrabold" translate="no">
            narrative/{media.category}/{media.id}
          </code>
          <dl className="mb-8 border-t-2 border-ink">
            {details.map(([term, value]) => (
              <div className="grid grid-cols-2 gap-4 border-b border-line py-4" key={term}>
                <dt className="text-xs font-extrabold tracking-wide text-muted uppercase">
                  {term}
                </dt>
                <dd className="m-0 text-right text-xs tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-3">
            <ActionLink download to={media.url}>
              {t("mediaAsset.downloadOriginal")}
            </ActionLink>
            <ActionLink
              adornment="external"
              rel="noreferrer"
              target="_blank"
              to={media.url}
              variant="secondary"
            >
              {t("mediaAsset.openOriginal")}
            </ActionLink>
          </div>
        </aside>
      </div>
      <StoryOccurrences
        eyebrow={t("mediaAsset.storyUsage")}
        locale={locale}
        occurrences={reverseReferences.occurrences}
        title={t("mediaAsset.storyReferences")}
        titleId="media-occurrences-title"
      />
      <CollectionReferences collections={reverseReferences.collections} locale={locale} />
    </ArchivePage>
  );
}
