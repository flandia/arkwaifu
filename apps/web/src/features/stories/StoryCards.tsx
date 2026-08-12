import type { Locale, Story, StoryGroup } from "../../api";
import { useUi } from "../../i18n";
import { localeLanguageTag, TransitionLink, type StorySection } from "../../navigation";
import { CardBackdrop, Eyebrow } from "../../shared/ui";

function previewUrls(record: StoryGroup | Story): string[] {
  const references = record.previewArtReferences?.length
    ? record.previewArtReferences
    : record.representativeArtReference
      ? [record.representativeArtReference]
      : [];

  return [
    ...new Set(
      references
        .map(({ thumbnailContentUrl }) => thumbnailContentUrl)
        .filter((url): url is string => Boolean(url)),
    ),
  ].slice(0, 3);
}

export function StoryGroupCard({
  group,
  locale,
  section,
}: {
  group: StoryGroup;
  locale: Locale;
  section: StorySection;
}) {
  const { t } = useUi();
  const backgrounds = previewUrls(group);
  return (
    <article className="min-w-0 [contain-intrinsic-size:auto_18rem] [content-visibility:auto]">
      <TransitionLink
        className="group relative flex min-h-72 flex-col justify-end overflow-hidden border-r-2 border-b-2 border-ink bg-brand p-6 text-white no-underline"
        to={`/${locale}/stories/${section}/${encodeURIComponent(group.id)}`}
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
          <Eyebrow className="text-white/75">{t("story.groupCard")}</Eyebrow>
          <h2
            className="mb-5 max-w-[22ch] break-words text-[clamp(1.6rem,3vw,2.6rem)] leading-none font-black tracking-tight text-balance"
            lang={localeLanguageTag(locale)}
          >
            {group.name || t("story.untitledGroup")}
          </h2>
          <code className="text-white/70" translate="no">
            {group.id}
          </code>
        </div>
      </TransitionLink>
    </article>
  );
}

export function StageCard({
  groupID,
  index,
  locale,
  section,
  story,
}: {
  groupID: string;
  index: number;
  locale: Locale;
  section: StorySection;
  story: Story;
}) {
  const { t } = useUi();
  const backgrounds = previewUrls(story);
  return (
    <li className="min-w-0 [contain-intrinsic-size:auto_14rem] [content-visibility:auto]">
      <TransitionLink
        className="group relative flex min-h-56 flex-col justify-end overflow-hidden border-r-2 border-b-2 border-ink bg-brand p-5 text-white no-underline"
        to={`/${locale}/stories/${section}/${encodeURIComponent(groupID)}/${encodeURIComponent(story.id)}`}
        transition="forward"
      >
        <CardBackdrop scrim={backgrounds.length ? "strong" : "brand"} sources={backgrounds} />
        <span
          className="relative z-10 mb-auto font-mono text-xs font-extrabold tabular-nums text-white/70"
          aria-hidden="true"
        >
          {String(index + 1).padStart(2, "0")}
        </span>
        <div className="relative z-10">
          <Eyebrow className="text-white/70">
            {story.code || story.tagText || t("story.stageEyebrow")}
          </Eyebrow>
          <h3
            className="mb-3 break-words text-[clamp(1.25rem,2.2vw,2rem)] leading-tight font-black text-balance"
            lang={localeLanguageTag(locale)}
          >
            {story.name || t("story.untitledStage")}
          </h3>
          <code className="line-clamp-1 text-white/65" translate="no">
            {story.id}
          </code>
        </div>
      </TransitionLink>
    </li>
  );
}
