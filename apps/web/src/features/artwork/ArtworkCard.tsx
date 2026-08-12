import { useState, ViewTransition } from "react";
import { artTransitionName, type ArtCategory, type ArtDetail, type Locale } from "../../api";
import { useUi } from "../../i18n";
import { TransitionLink, useCategoryLabel } from "../../navigation";
import { Eyebrow, cn } from "../../shared/ui";

const ratioClasses: Record<ArtCategory, string> = {
  image: "aspect-video",
  background: "aspect-video",
  item: "aspect-[16/10]",
  character: "aspect-[4/5]",
};

function ImageFallback() {
  const { t } = useUi();
  return (
    <div className="grid size-full min-h-[inherit] place-items-center bg-paper">
      <span className="border-2 border-ink bg-surface p-2 font-mono text-[0.67rem] font-extrabold tracking-wider uppercase">
        {t("art.imageUnavailable")}
      </span>
    </div>
  );
}

function ArchiveImage({
  alt,
  height,
  priority = false,
  src,
  width,
}: {
  alt: string;
  height: number;
  priority?: boolean;
  src: string;
  width: number;
}) {
  const [failedUrl, setFailedUrl] = useState<string>();
  if (failedUrl === src) return <ImageFallback />;
  return (
    <img
      alt={alt}
      className="size-full object-contain"
      decoding="async"
      fetchPriority={priority ? "high" : "auto"}
      height={height}
      loading={priority ? "eager" : "lazy"}
      onError={() => setFailedUrl(src)}
      src={src}
      width={width}
    />
  );
}

export function ArtworkImage({
  art,
  alt,
  priority = false,
}: {
  art: ArtDetail;
  alt: string;
  priority?: boolean;
}) {
  return (
    <ArchiveImage
      alt={alt}
      height={art.image.height}
      priority={priority}
      src={art.image.contentUrl}
      width={art.image.width}
    />
  );
}

export interface ArtworkCardProps {
  category: ArtCategory;
  id: string;
  locale: Locale;
  title: string;
  subtitle?: string;
  from: string;
  shared?: boolean;
  language?: string;
  thumbnailUrl: string | null;
}

export function ArtworkCard({
  category,
  from,
  id,
  language,
  locale,
  shared = true,
  subtitle,
  thumbnailUrl,
  title,
}: ArtworkCardProps) {
  const { t } = useUi();
  const labelCategory = useCategoryLabel();
  const media = thumbnailUrl ? (
    <ArchiveImage
      alt={title}
      height={1000}
      src={thumbnailUrl}
      width={category === "character" ? 800 : 1600}
    />
  ) : (
    <ImageFallback />
  );
  const destination = `/${locale}/art/${category}/${encodeURIComponent(id)}?${new URLSearchParams({ from })}`;

  return (
    <article className="flex min-w-0 flex-col border-2 border-ink bg-surface [contain-intrinsic-size:auto_30rem] [content-visibility:auto]">
      <TransitionLink
        aria-label={t("common.open", { name: title })}
        className={cn(
          "checkerboard group relative grid place-items-center overflow-hidden border-b-2 border-ink",
          ratioClasses[category],
        )}
        to={destination}
        transition="forward"
      >
        {shared ? (
          <ViewTransition default="none" name={artTransitionName(category, id)} share="morph">
            {media}
          </ViewTransition>
        ) : (
          media
        )}
        <span
          className="absolute right-3 bottom-3 grid size-10 place-items-center border-2 border-ink bg-brand font-black text-white transition-colors group-hover:bg-ink"
          aria-hidden="true"
        >
          ↗
        </span>
      </TransitionLink>
      <div className="flex min-w-0 flex-1 flex-col p-5">
        <Eyebrow>{labelCategory(category)}</Eyebrow>
        <h3 className="mb-2 break-words text-xl font-black" lang={language}>
          {title}
        </h3>
        {subtitle ? (
          <p
            className="mb-4 line-clamp-3 leading-relaxed text-muted"
            lang={language}
            title={subtitle}
          >
            {subtitle}
          </p>
        ) : null}
        <code
          className="mt-auto block break-words border-t border-line pt-5 text-xs text-muted"
          translate="no"
        >
          {id}
        </code>
      </div>
    </article>
  );
}
