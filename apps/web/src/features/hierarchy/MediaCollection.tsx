import { useState } from "react";
import type { Locale, StoryMediaReference, OrphanNarrativeMediaAsset } from "../../api/types";
import { formatBytes, uniqueStoryMediaReferences } from "../../api/utils";
import { useUi } from "../../i18n";
import { TransitionLink } from "../../navigation";
import { ActionButton } from "../../shared/ui/Action";
import { ArtworkGrid } from "../../shared/ui/ArtworkGrid";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";

const initialAudioCount = 6;
type MediaCollectionItem = StoryMediaReference | OrphanNarrativeMediaAsset;

function mediaFields(media: MediaCollectionItem) {
  return "asset" in media
    ? {
        category: media.asset.category as "audio" | "video",
        id: media.asset.id,
        mime: media.mime,
        size: media.size,
        url: media.url,
        usage: media.usage,
      }
    : { ...media, usage: null };
}

function MediaCard({
  from,
  locale,
  media,
}: {
  from: string;
  locale: Locale;
  media: MediaCollectionItem;
}) {
  const { t } = useUi();
  const asset = mediaFields(media);
  const label =
    asset.category === "video"
      ? t("story.video")
      : asset.usage === "sound"
        ? t("story.sound")
        : asset.usage === "music"
          ? t("story.music")
          : t("story.audio");
  const destination = `/${locale}/assets/narrative/${asset.category}/${encodeURIComponent(asset.id)}`;
  const isVideo = asset.category === "video";

  return (
    <article
      className={`flex min-w-0 flex-col border-2 border-ink text-ink ${isVideo ? "bg-surface" : "bg-white"}`}
    >
      {isVideo ? (
        <div className="relative border-b-2 border-ink bg-black">
          {asset.url ? (
            <TransitionLink
              aria-label={t("common.open", { name: asset.id })}
              className="absolute top-3 right-3 z-10 grid size-10 place-items-center border-2 border-ink bg-brand font-black text-white no-underline transition-colors hover:bg-ink"
              state={{ from }}
              to={destination}
              transition="forward"
            >
              ↗
            </TransitionLink>
          ) : null}
          {asset.url ? (
            // oxlint-disable-next-line jsx-a11y/media-has-caption
            <video
              aria-label={`${label}: ${asset.id}`}
              className="block h-auto w-full"
              controls
              preload="none"
            >
              <source src={asset.url} type={asset.mime ?? undefined} />
            </video>
          ) : (
            <div className="grid min-h-40 place-items-center bg-paper p-5 text-center text-sm text-muted">
              {t("story.mediaUnavailable")}
            </div>
          )}
        </div>
      ) : (
        <div className="border-b-2 border-ink bg-white p-5">
          {asset.url ? (
            // oxlint-disable-next-line jsx-a11y/media-has-caption
            <audio
              aria-label={`${label}: ${asset.id}`}
              className="mx-auto block w-full"
              controls
              preload="none"
            >
              <source src={asset.url} type={asset.mime ?? undefined} />
            </audio>
          ) : (
            <p className="m-0 text-center text-sm text-muted">{t("story.mediaUnavailable")}</p>
          )}
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col p-5">
        <Eyebrow>{label}</Eyebrow>
        <code className="block break-all text-sm font-extrabold" translate="no">
          {asset.id}
        </code>
        {asset.mime || asset.size ? (
          <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-4 font-mono text-xs text-muted">
            {asset.mime ? <span>{asset.mime}</span> : null}
            {asset.size ? <span>{formatBytes(asset.size)}</span> : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}

function MediaSection({
  media,
  eyebrow,
  from,
  locale,
  title,
  showEmpty = false,
  tone,
  variant,
}: {
  media: MediaCollectionItem[];
  eyebrow?: string;
  from: string;
  locale: Locale;
  title: string;
  showEmpty?: boolean;
  tone: "light" | "dark";
  variant: "video" | "audio";
}) {
  const { t } = useUi();
  const [expanded, setExpanded] = useState(false);
  if (!media.length && !showEmpty) return null;
  const visibleMedia = variant === "audio" && !expanded ? media.slice(0, initialAudioCount) : media;

  return (
    <section className="mt-[clamp(4rem,9vw,8rem)]">
      <SectionHeading
        eyebrow={eyebrow ?? t("story.media")}
        meta={new Intl.NumberFormat().format(media.length)}
        title={title}
        tone={tone}
      />
      {visibleMedia.length ? (
        <ArtworkGrid
          className={variant === "video" ? "grid-cols-1 md:grid-cols-1 xl:grid-cols-1" : undefined}
        >
          {visibleMedia.map((item) => (
            <MediaCard
              from={from}
              key={`${mediaFields(item).category}:${mediaFields(item).id}`}
              locale={locale}
              media={item}
            />
          ))}
        </ArtworkGrid>
      ) : (
        <p className={tone === "dark" ? "m-0 text-white/70" : "m-0 text-muted"}>
          {t("story.noMediaInCategory", { category: title })}
        </p>
      )}
      {variant === "audio" && media.length > initialAudioCount ? (
        <div className="mt-8 flex justify-center">
          <ActionButton
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
            variant="secondary"
          >
            {expanded ? t("story.showFewer") : t("story.showMore")}
          </ActionButton>
        </div>
      ) : null}
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
  const videos = uniqueMedia.filter((item) => item.asset.category === "video");
  const audio = uniqueMedia.filter((item) => item.asset.category === "audio");

  return (
    <>
      <MediaSection
        from={from}
        key={`${from}:video`}
        locale={locale}
        media={videos}
        showEmpty
        title={t("story.video")}
        tone={tone}
        variant="video"
      />
      <MediaSection
        from={from}
        key={`${from}:audio`}
        locale={locale}
        media={audio}
        showEmpty
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

export function MediaResourceCollection({
  from,
  locale,
  media,
}: {
  from: string;
  locale: Locale;
  media: OrphanNarrativeMediaAsset[];
}) {
  const { t } = useUi();
  const videos = media.filter((item) => item.category === "video");
  const audio = media.filter((item) => item.category === "audio");

  return (
    <>
      <MediaSection
        eyebrow={t("orphan.assetCategory")}
        from={from}
        locale={locale}
        media={videos}
        showEmpty
        title={t("story.video")}
        tone="light"
        variant="video"
      />
      <MediaSection
        eyebrow={t("orphan.assetCategory")}
        from={from}
        locale={locale}
        media={audio}
        showEmpty
        title={t("story.audio")}
        tone="light"
        variant="audio"
      />
    </>
  );
}
