import { use } from "react";
import { useLocation, useParams } from "react-router";
import { ApiError } from "../../api/client";
import { getMedia } from "../../api/media";
import type { MediaDetail, MediaKind } from "../../api/types";
import { formatBytes } from "../../api/utils";
import { useUi, useUiLanguage } from "../../i18n";
import { requiredLocale } from "../../navigation";
import { ArchivePage, BackLink, PageHeader } from "../../shared/Page";
import { ActionLink } from "../../shared/ui/Action";
import { Eyebrow } from "../../shared/ui/Typography";

function isMediaKind(value: string | undefined): value is MediaKind {
  return value === "audio" || value === "video";
}

function MediaPlayer({ media }: { media: MediaDetail }) {
  return (
    <figure className="m-0 grid min-h-44 place-items-center overflow-hidden border-[3px] border-ink bg-black">
      {media.kind === "video" ? (
        // oxlint-disable-next-line jsx-a11y/media-has-caption
        <video className="block h-auto w-full" controls preload="metadata">
          <source src={media.contentUrl} type={media.contentType} />
        </video>
      ) : (
        // oxlint-disable-next-line jsx-a11y/media-has-caption
        <audio className="mx-4 w-[calc(100%_-_2rem)] max-w-3xl" controls preload="metadata">
          <source src={media.contentUrl} type={media.contentType} />
        </audio>
      )}
    </figure>
  );
}

export function MediaDetailPage() {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  if (!isMediaKind(params.kind)) throw new ApiError(t("errors.notFound"), 404);
  const media = use(getMedia(params.kind, params.mediaID ?? ""));
  const location = useLocation();
  const from = typeof location.state?.from === "string" ? location.state.from : undefined;
  const backTo = from?.startsWith(`/${locale}/`) ? from : `/${locale}`;
  const kindLabel = t(`mediaAsset.${media.kind}`);
  const dimensions =
    media.width && media.height
      ? `${new Intl.NumberFormat(language).format(media.width)} × ${new Intl.NumberFormat(language).format(media.height)} px`
      : null;
  const details = [
    [t("mediaAsset.format"), media.contentType],
    [t("mediaAsset.fileSize"), formatBytes(media.byteSize, language)],
    media.duration
      ? [
          t("mediaAsset.duration"),
          `${new Intl.NumberFormat(language, { maximumFractionDigits: 2 }).format(media.duration)} s`,
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
            <span>{media.contentType}</span>
            <span>{formatBytes(media.byteSize, language)}</span>
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
            {media.kind}/{media.id}
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
          <ActionLink
            adornment="external"
            className="w-full"
            rel="noreferrer"
            target="_blank"
            to={media.contentUrl}
          >
            {t("mediaAsset.openOriginal")}
          </ActionLink>
        </aside>
      </div>
    </ArchivePage>
  );
}
