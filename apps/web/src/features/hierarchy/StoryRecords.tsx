import type { Locale, StorySummary } from "../../api/types";
import { useUi } from "../../i18n";
import { localeLanguageTag, TransitionLink } from "../../navigation";
import { CardBackdrop } from "../../shared/ui/CardBackdrop";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";

function previewUrls(story: StorySummary): string[] {
  const references = story.previewAssetReferences.length
    ? story.previewAssetReferences
    : story.representativeAssetReference
      ? [story.representativeAssetReference]
      : [];
  return references.flatMap((reference) => (reference.previewUrl ? [reference.previewUrl] : []));
}

export function StoryRecordCard({
  basePath,
  index,
  locale,
  story,
}: {
  basePath: string;
  index: number;
  locale: Locale;
  story: StorySummary;
}) {
  const { t } = useUi();
  const backgrounds = previewUrls(story);
  return (
    <li className="min-w-0 [contain-intrinsic-block-size:auto_14rem] [content-visibility:auto]">
      <TransitionLink
        className="group relative flex min-h-56 flex-col justify-end overflow-hidden border-r-2 border-b-2 border-ink bg-brand p-5 text-white no-underline"
        to={`${basePath}/${encodeURIComponent(story.id)}`}
        transition="forward"
      >
        <CardBackdrop scrim={backgrounds.length ? "strong" : "brand"} sources={backgrounds} />
        <span
          className="relative z-10 mb-auto font-mono text-xs font-extrabold text-white/70 tabular-nums"
          aria-hidden="true"
        >
          {String(index + 1).padStart(2, "0")}
        </span>
        <div className="relative z-10">
          <Eyebrow className="text-white/70">
            {story.code || story.tagText || t("story.record")}
          </Eyebrow>
          <h3
            className="mb-3 break-words text-[clamp(1.25rem,2.2vw,2rem)] leading-tight font-black text-balance"
            lang={localeLanguageTag(locale)}
          >
            {story.name || t("story.untitled")}
          </h3>
          <code className="line-clamp-1 text-white/65" translate="no">
            {story.id}
          </code>
        </div>
      </TransitionLink>
    </li>
  );
}

export function StoryRecordGrid({
  basePath,
  locale,
  stories,
  tone = "light",
}: {
  basePath: string;
  locale: Locale;
  stories: StorySummary[];
  tone?: "light" | "dark";
}) {
  return (
    <div className="min-w-0">
      <ol
        className={
          tone === "dark"
            ? "m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(min(100%,22rem),1fr))] border-t-2 border-l-2 border-black p-0 [&_a]:border-black"
            : "m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(min(100%,22rem),1fr))] border-t-2 border-l-2 border-ink p-0"
        }
      >
        {stories.map((story, index) => (
          <StoryRecordCard
            basePath={basePath}
            index={index}
            key={story.id}
            locale={locale}
            story={story}
          />
        ))}
      </ol>
    </div>
  );
}

export function StoryRecords({
  basePath,
  locale,
  stories,
  tone = "light",
}: {
  basePath: string;
  locale: Locale;
  stories: StorySummary[];
  tone?: "light" | "dark";
}) {
  const { t } = useUi();
  if (!stories.length) return null;

  return (
    <section className="mt-16" aria-labelledby="story-records-title">
      <SectionHeading
        eyebrow={t("story.ordered")}
        meta={new Intl.NumberFormat(localeLanguageTag(locale)).format(stories.length)}
        title={t("story.title")}
        titleId="story-records-title"
        tone={tone}
      />
      <StoryRecordGrid basePath={basePath} locale={locale} stories={stories} tone={tone} />
    </section>
  );
}
