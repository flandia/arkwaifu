import { formatBytes, type Art, type SourceArt } from "../../api";
import { useUi, useUiLanguage } from "../../i18n";
import { Eyebrow } from "../../shared/ui";

export function SourceLayerCard({ source, composition }: { source: SourceArt; composition: Art }) {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const role = t(`art.${source.role === "whole_body" ? "wholeBody" : source.role}`);
  return (
    <article className="min-w-0 border-2 border-ink bg-surface [contain-intrinsic-size:auto_28rem] [content-visibility:auto]">
      <a
        aria-label={t("art.openSourceLayer", { role: role.toLocaleLowerCase(language) })}
        className="checkerboard group relative grid min-h-72 max-h-[30rem] place-items-center overflow-hidden border-b-2 border-ink text-inherit no-underline"
        href={source.image.contentUrl}
        rel="noreferrer"
        target="_blank"
      >
        <img
          alt={t("art.sourceLayerAlt", { role, id: composition.id })}
          className="size-full object-contain"
          decoding="async"
          height={source.image.height}
          loading="lazy"
          src={source.image.contentUrl}
          width={source.image.width}
        />
        <span
          className="absolute right-3 bottom-3 grid size-10 place-items-center border-2 border-ink bg-brand font-black text-white group-hover:bg-ink"
          aria-hidden="true"
        >
          ↗
        </span>
      </a>
      <div className="p-5">
        <Eyebrow>{t("art.layer", { role })}</Eyebrow>
        <code className="block break-words" translate="no">
          {source.id}
        </code>
        <small className="mt-2 block text-[0.68rem] text-muted tabular-nums">
          {new Intl.NumberFormat(language).format(source.image.width)} ×{" "}
          {new Intl.NumberFormat(language).format(source.image.height)} ·{" "}
          {formatBytes(source.image.byteSize, language)}
        </small>
      </div>
    </article>
  );
}
