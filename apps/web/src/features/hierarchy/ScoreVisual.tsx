import { useEffect, useRef, useState } from "react";
import type { ScoreImage, ScoreVideo } from "../../api/types";
import { useBackgroundMotion } from "../../shared/BackgroundMotion";
import { cn } from "../../shared/ui/cn";

/** The nested Score-directory mark used by the in-game archive navigation. */
export function ScoreArchiveMark({ className }: { className?: string }) {
  return (
    <span aria-hidden="true" className={cn("relative block aspect-square", className)}>
      <span className="absolute inset-x-[7%] top-[29%] bottom-[5%] border-[3px] border-current/20" />
      <span className="absolute inset-x-[20%] top-[20%] bottom-[18%] border-[3px] border-current/40" />
      <span className="absolute inset-x-[33%] top-[32%] bottom-[31%] border-[3px] border-current/80" />
      <span className="absolute top-[4%] left-1/2 size-0 -translate-x-1/2 border-x-[0.8em] border-t-[1em] border-x-transparent border-t-current" />
    </span>
  );
}

export function ScoreImageAsset({
  alt,
  asset,
  className,
  eager = false,
}: {
  alt: string;
  asset: ScoreImage | null;
  className?: string;
  eager?: boolean;
}) {
  if (!asset?.image) return null;
  return (
    <img
      alt={alt}
      className={className}
      decoding="async"
      fetchPriority={eager ? "high" : "auto"}
      height={asset.image.height}
      loading={eager ? "eager" : "lazy"}
      src={asset.image.url}
      width={asset.image.width}
    />
  );
}

/** Renders a static Score background and enables its video only when motion is welcome. */
export function ScoreBackdrop({
  image,
  video,
  className,
  imageClassName,
  priority = false,
  viewportGated = false,
}: {
  image: ScoreImage | null;
  video: ScoreVideo | null;
  className?: string;
  imageClassName?: string;
  priority?: boolean;
  viewportGated?: boolean;
}) {
  const { paused, reducedMotion } = useBackgroundMotion();
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [nearViewport, setNearViewport] = useState(!viewportGated);
  const [failedVideo, setFailedVideo] = useState<string>();
  const poster = image?.image?.url;
  const videoUrl = video?.video?.url;
  const activeVideo =
    !reducedMotion && nearViewport && failedVideo !== videoUrl ? video?.video : null;

  useEffect(() => {
    const element = videoRef.current;
    if (!element) return;
    if (paused) element.pause();
    else void element.play().catch(() => {});
  }, [paused, activeVideo?.url]);

  useEffect(() => {
    if (!viewportGated) {
      setNearViewport(true);
      return;
    }
    const element = containerRef.current;
    if (!element || typeof IntersectionObserver === "undefined") {
      setNearViewport(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => setNearViewport(entry?.isIntersecting ?? false),
      { rootMargin: "240px 0px", threshold: 0.01 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [viewportGated]);

  return (
    <>
      <div
        aria-hidden="true"
        className={cn("absolute inset-0 overflow-hidden", className)}
        ref={containerRef}
      >
        <ScoreImageAsset
          alt=""
          asset={image}
          className={cn("size-full object-cover", imageClassName)}
          eager={priority}
        />
        {activeVideo ? (
          // The upstream Score videos are visual loops without meaningful dialogue.
          // oxlint-disable-next-line jsx-a11y/media-has-caption
          <video
            autoPlay={!paused}
            className={cn("absolute inset-0 size-full object-cover", imageClassName)}
            height={activeVideo.height}
            loop
            muted
            onError={() => setFailedVideo(videoUrl)}
            playsInline
            poster={poster}
            preload="metadata"
            ref={videoRef}
            src={activeVideo.url}
            tabIndex={-1}
            width={activeVideo.width}
          />
        ) : null}
      </div>
    </>
  );
}
