import type { ArtContext, ArtOccurrence, Locale, StoryParent } from "../../api/types";
import { useUi } from "../../i18n";
import {
  archiveKindLabel,
  localeLanguageTag,
  storyParentPath,
  storyPath,
  TransitionLink,
} from "../../navigation";
import { ArtworkGrid } from "../../shared/ui/ArtworkGrid";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";
import { ArtworkCard } from "./ArtworkCard";

interface OccurrenceGroup {
  key: string;
  parent: StoryParent;
  stories: ArtOccurrence[];
}

function groupOccurrences(occurrences: ArtOccurrence[]): OccurrenceGroup[] {
  const groups = new Map<string, OccurrenceGroup>();
  for (const occurrence of occurrences) {
    const parent = occurrence.parent;
    const key =
      parent.kind === "score"
        ? `score:${parent.movementID}:${parent.sectionID}`
        : `archive:${parent.archiveKind}:${parent.groupID}`;
    const group = groups.get(key) ?? {
      key,
      parent,
      stories: [],
    };
    if (!group.stories.some((story) => story.storyID === occurrence.storyID)) {
      group.stories.push(occurrence);
    }
    groups.set(group.key, group);
  }
  return [...groups.values()];
}

export function SiblingCharacters({
  context,
  currentArtID,
  from,
  locale,
}: {
  context: ArtContext;
  currentArtID: string;
  from: string;
  locale: Locale;
}) {
  const { t } = useUi();
  const siblings = context.siblings.filter((sibling) => sibling.artID !== currentArtID);
  if (!siblings.length) return null;
  const language = localeLanguageTag(locale);

  return (
    <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="sibling-characters-title">
      <SectionHeading
        eyebrow={t("art.characterFamily")}
        meta={new Intl.NumberFormat(language).format(siblings.length)}
        title={t("art.siblingCharacters")}
        titleId="sibling-characters-title"
      />
      <ArtworkGrid>
        {siblings.map((sibling) => (
          <ArtworkCard
            category="character"
            from={from}
            id={sibling.artID}
            key={sibling.artID}
            language={language}
            locale={locale}
            thumbnailUrl={sibling.thumbnailContentUrl}
            title={sibling.names.filter(Boolean).join(" / ") || t("art.unnamedCharacter")}
          />
        ))}
      </ArtworkGrid>
    </section>
  );
}

export function ArtworkOccurrences({ context, locale }: { context: ArtContext; locale: Locale }) {
  const { t } = useUi();
  const language = localeLanguageTag(locale);
  const groups = groupOccurrences(context.occurrences);
  if (!groups.length) return null;
  const storyCount = groups.reduce((count, group) => count + group.stories.length, 0);

  return (
    <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="artwork-occurrences-title">
      <SectionHeading
        eyebrow={t("art.storyUsage")}
        meta={t("art.usageSummary", { groups: groups.length, stories: storyCount })}
        title={t("art.appearsIn")}
        titleId="artwork-occurrences-title"
      />
      <div className="grid gap-6 lg:grid-cols-2">
        {groups.map((group) => {
          const groupPath = storyParentPath(locale, group.parent);
          const ownerName =
            group.parent.kind === "score" ? group.parent.sectionName : group.parent.groupName;
          const hierarchy =
            group.parent.kind === "score"
              ? group.parent.movementName
              : archiveKindLabel(group.parent.archiveKind, t);
          return (
            <article className="border-2 border-ink bg-surface" key={group.key}>
              <header className="border-b-2 border-ink p-5">
                <Eyebrow>{hierarchy}</Eyebrow>
                <h3 className="m-0 text-2xl font-black" lang={language}>
                  <TransitionLink className="hover:bg-brand-soft" to={groupPath}>
                    {ownerName || t("story.untitledGroup")}
                  </TransitionLink>
                </h3>
                <code className="mt-2 block text-xs text-muted" translate="no">
                  {group.parent.kind === "score" ? group.parent.sectionID : group.parent.groupID}
                </code>
              </header>
              <ul className="m-0 list-none divide-y divide-line p-0">
                {group.stories.map((story) => (
                  <li key={story.storyID}>
                    <TransitionLink
                      className="grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-5 py-3 no-underline hover:bg-brand-soft"
                      to={storyPath(locale, story.parent, story.storyID)}
                      transition="forward"
                    >
                      <strong className="min-w-0 break-words" lang={language}>
                        {story.storyName || story.storyCode || t("story.untitledStage")}
                      </strong>
                      <span className="text-right font-mono text-xs text-muted">
                        {story.storyCode || story.storyTagText}
                      </span>
                    </TransitionLink>
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
      </div>
    </section>
  );
}
