import { useMemo, useState, type CSSProperties } from "react";
import { cn } from "./cn";

const scrims = {
  dark: "bg-gradient-to-t from-black/90 via-black/55 to-black/15",
  strong: "bg-black/70",
  light: "bg-gradient-to-t from-white/95 via-white/75 to-white/30",
  brand: "bg-gradient-to-t from-brand/95 via-brand/70 to-brand/25",
} as const;

interface CardBackdropProps {
  sources?: readonly string[];
  scrim?: keyof typeof scrims;
  position?: CSSProperties["objectPosition"];
  className?: string;
  imageClassName?: string;
}

export function CardBackdrop({
  className,
  imageClassName,
  position,
  scrim = "dark",
  sources = [],
}: CardBackdropProps) {
  const [failedSources, setFailedSources] = useState<ReadonlySet<string>>(() => new Set());
  const [loadedSources, setLoadedSources] = useState<ReadonlySet<string>>(() => new Set());
  const [{ interval, startingPoint }] = useState(() => ({
    interval: 10_000 + Math.floor(Math.random() * 10_001),
    startingPoint: Math.random(),
  }));
  const usableSources = useMemo(() => {
    const available = [...new Set(sources)]
      .filter((source) => !failedSources.has(source))
      .slice(0, 3);
    const startIndex = Math.floor(startingPoint * available.length);
    return [...available.slice(startIndex), ...available.slice(0, startIndex)];
  }, [failedSources, sources, startingPoint]);
  const previewCount = usableSources.length;
  const canRotate = previewCount > 1 && usableSources.every((source) => loadedSources.has(source));

  function markFailed(source: string) {
    setFailedSources((current) => {
      if (current.has(source)) return current;
      const next = new Set(current);
      next.add(source);
      return next;
    });
  }

  function markLoaded(source: string) {
    setLoadedSources((current) => {
      if (current.has(source)) return current;
      const next = new Set(current);
      next.add(source);
      return next;
    });
  }

  return (
    <span aria-hidden="true" className={cn("pointer-events-none absolute inset-0", className)}>
      {usableSources.map((source, index) => (
        <img
          alt=""
          className={cn(
            "card-preview-frame absolute inset-0 size-full object-cover opacity-0 transition-transform duration-500 first:opacity-100 group-hover:scale-[1.03] group-hover:[animation-play-state:paused] group-focus-visible:[animation-play-state:paused] motion-reduce:transform-none",
            imageClassName,
          )}
          data-preview-count={previewCount}
          data-preview-ready={canRotate || undefined}
          decoding="async"
          height="1000"
          key={source}
          loading="lazy"
          onError={() => markFailed(source)}
          onLoad={() => markLoaded(source)}
          src={source}
          style={
            {
              "--preview-delay": `${-(previewCount - index) * interval}ms`,
              "--preview-duration": `${previewCount * interval}ms`,
              objectPosition: position,
            } as CSSProperties
          }
          width="1600"
        />
      ))}
      <span className={cn("absolute inset-0", scrims[scrim])} />
    </span>
  );
}
