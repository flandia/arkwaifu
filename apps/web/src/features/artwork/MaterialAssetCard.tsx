import { useLocation, useParams } from "react-router";
import type { NarrativeImageAsset, MaterialAsset } from "../../api/types";
import { formatBytes } from "../../api/utils";
import { useUi, useUiLanguage } from "../../i18n";
import { requiredLocale, TransitionLink } from "../../navigation";
import { Eyebrow } from "../../shared/ui/Typography";

export function MaterialAssetCard({
  source,
  artwork,
  index = 0,
}: {
  source: MaterialAsset;
  artwork: NarrativeImageAsset;
  index?: number;
}) {
  const { t } = useUi();
  const { language } = useUiLanguage();
  const locale = requiredLocale(useParams().locale);
  const location = useLocation();
  const role =
    source.materialType === "character" && source.role
      ? t(`artwork.${source.role === "whole_body" ? "wholeBody" : source.role}`)
      : t("artwork.artworkPanel", { position: index + 1 });
  return (
    <article className="min-w-0 border-2 border-ink bg-surface [contain-intrinsic-size:auto_28rem] [content-visibility:auto]">
      <TransitionLink
        aria-label={t("artwork.openMaterialAsset", { role: role.toLocaleLowerCase(language) })}
        className="checkerboard group relative grid min-h-72 max-h-[30rem] place-items-center overflow-hidden border-b-2 border-ink text-inherit no-underline"
        state={{ from: `${location.pathname}${location.search}` }}
        to={`/${locale}/assets/material/${source.category}/${encodeURIComponent(source.id)}`}
        transition="forward"
      >
        <img
          alt={t("artwork.sourceLayerAlt", { role, id: artwork.id })}
          className="size-full object-contain"
          decoding="async"
          height={source.height}
          loading="lazy"
          src={source.url}
          width={source.width}
        />
        <span
          className="absolute right-3 bottom-3 grid size-10 place-items-center border-2 border-ink bg-brand font-black text-white group-hover:bg-ink"
          aria-hidden="true"
        >
          ↗
        </span>
      </TransitionLink>
      <div className="p-5">
        <Eyebrow>
          {source.materialType === "character"
            ? t("artwork.layer", { role })
            : t("artwork.panelSource", { position: index + 1 })}
        </Eyebrow>
        <code className="block break-words" translate="no">
          {source.id}
        </code>
        <small className="mt-2 block text-[0.68rem] text-muted tabular-nums">
          {new Intl.NumberFormat(language).format(source.width)} ×{" "}
          {new Intl.NumberFormat(language).format(source.height)} ·{" "}
          {formatBytes(source.size, language)}
        </small>
      </div>
    </article>
  );
}
