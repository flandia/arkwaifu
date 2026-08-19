import type { ArchiveGroupSummary, ArchiveCategory, Locale } from "../../api/types";
import { useUi } from "../../i18n";
import { archiveCategoryLabel, localeLanguageTag, TransitionLink } from "../../navigation";
import { CardBackdrop } from "../../shared/ui/CardBackdrop";
import { Eyebrow } from "../../shared/ui/Typography";

function previewUrls(group: ArchiveGroupSummary): string[] {
  const references = group.previewAssetReferences.length
    ? group.previewAssetReferences
    : group.representativeAssetReference
      ? [group.representativeAssetReference]
      : [];
  return references.flatMap((reference) => (reference.previewUrl ? [reference.previewUrl] : []));
}

export function ArchiveGroupCard({
  group,
  locale,
}: {
  group: ArchiveGroupSummary;
  locale: Locale;
}) {
  const { t } = useUi();
  const backgrounds = previewUrls(group);
  return (
    <article className="min-w-0 [contain-intrinsic-size:auto_20rem] [content-visibility:auto]">
      <TransitionLink
        className="group relative flex min-h-80 flex-col justify-end overflow-hidden border-r-2 border-b-2 border-ink bg-brand p-6 text-white no-underline"
        to={`/${locale}/archives/${group.archiveCategory}/${encodeURIComponent(group.id)}`}
        transition="forward"
      >
        <CardBackdrop scrim={backgrounds.length ? "dark" : "brand"} sources={backgrounds} />
        <span
          className="relative z-10 mb-auto ml-auto grid size-10 place-items-center border-2 border-white bg-black/35 font-black"
          aria-hidden="true"
        >
          ↗
        </span>
        <div className="relative z-10">
          <Eyebrow className="text-white/70">{t(`archive.groupTypes.${group.type}`)}</Eyebrow>
          <h2
            className="mb-4 max-w-[22ch] break-words text-[clamp(1.6rem,3vw,2.7rem)] leading-none font-black text-balance"
            lang={localeLanguageTag(locale)}
          >
            {group.name || t("archive.untitledGroup")}
          </h2>
          <code className="text-xs text-white/65" translate="no">
            {group.id}
          </code>
        </div>
      </TransitionLink>
    </article>
  );
}

export function ArchiveCategoryCard({
  category,
  count,
  index,
  locale,
}: {
  category: ArchiveCategory;
  count: number;
  index: string;
  locale: Locale;
}) {
  const { t } = useUi();
  return (
    <li className="min-w-0 [contain-intrinsic-size:auto_14rem] [content-visibility:auto]">
      <TransitionLink
        className="grid min-h-56 grid-cols-[3rem_minmax(0,1fr)_auto] items-center gap-5 border-r-2 border-b-2 border-ink bg-surface p-6 no-underline hover:bg-brand-soft"
        to={`/${locale}/archives/${category}`}
        transition="forward"
      >
        <span className="font-mono text-xs font-black text-muted" aria-hidden="true">
          {index}
        </span>
        <h2 className="m-0 text-[clamp(1.6rem,3.5vw,3rem)] leading-none font-black tracking-tight uppercase">
          {archiveCategoryLabel(category, t)}
        </h2>
        <strong className="font-mono text-[clamp(2.8rem,6vw,5rem)] leading-none tabular-nums">
          {new Intl.NumberFormat().format(count)}
        </strong>
      </TransitionLink>
    </li>
  );
}
