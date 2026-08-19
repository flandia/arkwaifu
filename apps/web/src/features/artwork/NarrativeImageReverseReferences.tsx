import type {
  NarrativeImageReverseReferences,
  NarrativeAssetGalleryReference,
  NarrativeImageOccurrence,
  Locale,
  StoryOccurrence,
  StoryParent,
} from "../../api/types";
import { useUi } from "../../i18n";
import {
  archiveCategoryLabel,
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
  stories: StoryOccurrence[];
}

export function BundleTextures({
  reverseReferences,
  from,
  locale,
}: {
  reverseReferences: NarrativeImageReverseReferences;
  from: string;
  locale: Locale;
}) {
  const { t } = useUi();
  const language = localeLanguageTag(locale);
  if (!reverseReferences.textures.length) return null;

  return (
    <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="bundle-textures-title">
      <SectionHeading
        eyebrow={t("artwork.bundleContents")}
        meta={new Intl.NumberFormat(language).format(reverseReferences.textures.length)}
        title={t("artwork.textures")}
        titleId="bundle-textures-title"
      />
      <ArtworkGrid>
        {reverseReferences.textures.map((texture) => (
          <ArtworkCard
            category="illustration"
            from={from}
            id={texture.assetID}
            key={texture.assetID}
            language={language}
            locale={locale}
            thumbnailUrl={texture.previewUrl}
            title={texture.assetID.split("/").at(-1) ?? texture.assetID}
          />
        ))}
      </ArtworkGrid>
    </section>
  );
}

function groupOccurrences(occurrences: NarrativeImageOccurrence[]): OccurrenceGroup[] {
  const groups = new Map<string, OccurrenceGroup>();
  for (const occurrence of occurrences) {
    const parent = occurrence.parent;
    const key =
      parent.kind === "score"
        ? `score:${parent.movementID}:${parent.sectionID}`
        : `archive:${parent.archiveCategory}:${parent.groupID}`;
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

export function CharacterVariants({
  reverseReferences,
  currentArtworkID,
  from,
  locale,
}: {
  reverseReferences: NarrativeImageReverseReferences;
  currentArtworkID: string;
  from: string;
  locale: Locale;
}) {
  const { t } = useUi();
  const characterVariants = reverseReferences.characterVariants.filter(
    (variant) => variant.assetID !== currentArtworkID,
  );
  if (!characterVariants.length) return null;
  const language = localeLanguageTag(locale);

  return (
    <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="character-variants-title">
      <SectionHeading
        eyebrow={t("artwork.characterFamily")}
        meta={new Intl.NumberFormat(language).format(characterVariants.length)}
        title={t("artwork.characterVariants")}
        titleId="character-variants-title"
      />
      <ArtworkGrid>
        {characterVariants.map((variant) => (
          <ArtworkCard
            category="character"
            from={from}
            id={variant.assetID}
            key={variant.assetID}
            language={language}
            locale={locale}
            thumbnailUrl={variant.previewUrl}
            title={variant.names.filter(Boolean).join(" / ") || t("artwork.unnamedCharacter")}
          />
        ))}
      </ArtworkGrid>
    </section>
  );
}

export function StoryOccurrences({
  eyebrow,
  locale,
  occurrences,
  title,
  titleId,
}: {
  eyebrow: string;
  locale: Locale;
  occurrences: StoryOccurrence[];
  title: string;
  titleId: string;
}) {
  const { t } = useUi();
  const language = localeLanguageTag(locale);
  const groups = groupOccurrences(occurrences);
  if (!groups.length) return null;
  const storyCount = groups.reduce((count, group) => count + group.stories.length, 0);

  return (
    <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby={titleId}>
      <SectionHeading
        eyebrow={eyebrow}
        meta={t("artwork.usageSummary", { groups: groups.length, stories: storyCount })}
        title={title}
        titleId={titleId}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        {groups.map((group) => {
          const groupPath = storyParentPath(locale, group.parent);
          const ownerName =
            group.parent.kind === "score" ? group.parent.sectionName : group.parent.groupName;
          const hierarchy =
            group.parent.kind === "score"
              ? group.parent.movementName
              : archiveCategoryLabel(group.parent.archiveCategory, t);
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

export function NarrativeImageOccurrences({
  reverseReferences,
  locale,
}: {
  reverseReferences: NarrativeImageReverseReferences;
  locale: Locale;
}) {
  const { t } = useUi();
  return (
    <StoryOccurrences
      eyebrow={t("artwork.storyUsage")}
      locale={locale}
      occurrences={reverseReferences.occurrences}
      title={t("artwork.appearsIn")}
      titleId="artwork-occurrences-title"
    />
  );
}

function galleryReferencePath(locale: Locale, reference: NarrativeAssetGalleryReference): string {
  return `/${locale}/galleries/${encodeURIComponent(reference.galleryID)}/groups/${encodeURIComponent(reference.groupID)}/${encodeURIComponent(reference.cgID)}`;
}

export function ArtworkGalleries({
  reverseReferences,
  locale,
}: {
  reverseReferences: NarrativeImageReverseReferences;
  locale: Locale;
}) {
  const { t } = useUi();
  const language = localeLanguageTag(locale);
  if (!reverseReferences.galleries.length) return null;

  return (
    <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="artwork-galleries-title">
      <SectionHeading
        eyebrow={t("artwork.galleryUsage")}
        meta={new Intl.NumberFormat(language).format(reverseReferences.galleries.length)}
        title={t("artwork.galleryAppearances")}
        titleId="artwork-galleries-title"
      />
      <div className="grid gap-6 lg:grid-cols-2">
        {reverseReferences.galleries.map((reference) => (
          <article
            className="border-2 border-ink bg-surface p-5"
            key={`${reference.galleryID}:${reference.groupID}:${reference.cgID}`}
          >
            <Eyebrow>{reference.galleryName || t("gallery.title")}</Eyebrow>
            <h3 className="mb-3 text-2xl font-black" lang={language}>
              <TransitionLink
                className="hover:bg-brand-soft"
                to={galleryReferencePath(locale, reference)}
                transition="forward"
              >
                {reference.groupName || t("gallery.untitledGroup")}
              </TransitionLink>
            </h3>
            {reference.groupDescription || reference.galleryDescription ? (
              <p className="m-0 leading-relaxed text-muted" lang={language}>
                {reference.groupDescription || reference.galleryDescription}
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
