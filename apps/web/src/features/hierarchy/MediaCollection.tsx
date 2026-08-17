import type { Locale, StoryMediaReference } from "../../api/types";
import { formatBytes, uniqueStoryMediaReferences } from "../../api/utils";
import { useUi } from "../../i18n";
import { TransitionLink } from "../../navigation";
import { ArtworkGrid } from "../../shared/ui/ArtworkGrid";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";

function MediaCard({
  from,
  locale,
  media,
}: {
  from: string;
  locale: Locale;
  media: StoryMediaReference;
}) {
  const { t } = useUi();
  const label =
    media.kind === "video"
      ? t("story.video")
      : media.kind === "sound"
        ? t("story.sound")
        : t("story.music");
  const assetKind = media.kind === "video" ? "video" : "audio";
  const destination = `/${locale}/media/${assetKind}/${encodeURIComponent(media.id)}`;

  return (
    <article className="flex min-w-0 flex-col border-2 border-ink bg-surface text-ink">
      <div className="relative border-b-2 border-ink bg-black">
        {media.contentUrl ? (
          <TransitionLink
            aria-label={t("common.open", { name: media.id })}
            className="absolute top-3 right-3 z-10 grid size-10 place-items-center border-2 border-ink bg-brand font-black text-white no-underline transition-colors hover:bg-ink"
            state={{ from }}
            to={destination}
            transition="forward"
          >
            ↗
          </TransitionLink>
        ) : null}
        {media.contentUrl ? (
          media.kind === "video" ? (
            // oxlint-disable-next-line jsx-a11y/media-has-caption
            <video
              aria-label={`${label}: ${media.id}`}
              className="block h-auto w-full"
              controls
              preload="none"
            >
              <source src={media.contentUrl} type={media.contentType ?? undefined} />
            </video>
          ) : (
            <div className="grid min-h-40 place-items-center bg-paper p-5 pt-16">
              {/* oxlint-disable-next-line jsx-a11y/media-has-caption */}
              <audio
                aria-label={`${label}: ${media.id}`}
                className="w-full"
                controls
                preload="none"
              >
                <source src={media.contentUrl} type={media.contentType ?? undefined} />
              </audio>
            </div>
          )
        ) : (
          <div className="grid min-h-40 place-items-center bg-paper p-5 text-center text-sm text-muted">
            {t("story.mediaUnavailable")}
          </div>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col p-5">
        <Eyebrow>{label}</Eyebrow>
        <code className="block break-all text-sm font-extrabold" translate="no">
          {media.id}
        </code>
        {media.contentType || media.byteSize ? (
          <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-4 font-mono text-xs text-muted">
            {media.contentType ? <span>{media.contentType}</span> : null}
            {media.byteSize ? <span>{formatBytes(media.byteSize)}</span> : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}

function MediaSection({
  media,
  from,
  locale,
  title,
  tone,
  variant,
}: {
  media: StoryMediaReference[];
  from: string;
  locale: Locale;
  title: string;
  tone: "light" | "dark";
  variant: "video" | "audio";
}) {
  const { t } = useUi();
  if (!media.length) return null;

  return (
    <section className="mt-[clamp(4rem,9vw,8rem)]">
      <SectionHeading
        eyebrow={t("story.media")}
        meta={new Intl.NumberFormat().format(media.length)}
        title={title}
        tone={tone}
      />
      <ArtworkGrid
        className={variant === "video" ? "grid-cols-1 md:grid-cols-1 xl:grid-cols-1" : undefined}
      >
        {media.map((item) => (
          <MediaCard from={from} key={`${item.kind}:${item.id}`} locale={locale} media={item} />
        ))}
      </ArtworkGrid>
    </section>
  );
}

export function StoryMediaCollection({
  from,
  locale,
  media,
  tone = "light",
}: {
  from: string;
  locale: Locale;
  media: StoryMediaReference[];
  tone?: "light" | "dark";
}) {
  const { t } = useUi();
  const uniqueMedia = uniqueStoryMediaReferences(media);
  const videos = uniqueMedia.filter((item) => item.kind === "video");
  const audio = uniqueMedia.filter((item) => item.kind !== "video");

  return (
    <>
      <MediaSection
        from={from}
        locale={locale}
        media={videos}
        title={t("story.video")}
        tone={tone}
        variant="video"
      />
      <MediaSection
        from={from}
        locale={locale}
        media={audio}
        title={t("story.audio")}
        tone={tone}
        variant="audio"
      />
    </>
  );
}

export function OpeningMediaCollection({
  from,
  locale,
  media,
  tone = "light",
}: {
  from: string;
  locale: Locale;
  media: StoryMediaReference[];
  tone?: "light" | "dark";
}) {
  const { t } = useUi();
  const uniqueMedia = uniqueStoryMediaReferences(media);
  if (!uniqueMedia.length) return null;

  return (
    <MediaSection
      from={from}
      locale={locale}
      media={uniqueMedia}
      title={t("story.prologue")}
      tone={tone}
      variant="video"
    />
  );
}
