import { use } from "react";
import { useParams } from "react-router";
import { getGalleries } from "../../api/galleries";
import type { ArchiveKind, GallerySummary, Locale, StoryParent } from "../../api/types";
import { useUi } from "../../i18n";
import {
  archiveKindLabel,
  localeLanguageTag,
  requiredLocale,
  TransitionLink,
} from "../../navigation";
import {
  AnimatedListItem,
  CollectionControls,
  useCollectionIndex,
} from "../../shared/CollectionIndex";
import { ArchivePage, EmptyState, PageHeader } from "../../shared/Page";
import { CardBackdrop } from "../../shared/ui/CardBackdrop";
import { Eyebrow } from "../../shared/ui/Typography";

function gallerySearchValues(gallery: GallerySummary): string[] {
  const parent = gallery.parent;
  return [
    gallery.name,
    gallery.id,
    gallery.description,
    parent.kind === "score" ? parent.movementName : parent.groupName,
    parent.kind === "score" ? parent.sectionName : parent.archiveKind,
  ];
}

interface OwnerGroup {
  key: string;
  parent: StoryParent;
  galleries: GallerySummary[];
}

interface OwnerBranch {
  key: string;
  name: string;
  owners: OwnerGroup[];
}

interface GalleryHierarchy {
  score: OwnerBranch[];
  archive: OwnerBranch[];
}

function groupByOwner(galleries: GallerySummary[]): OwnerGroup[] {
  const groups = new Map<string, OwnerGroup>();
  for (const gallery of galleries) {
    const parent = gallery.parent;
    const key =
      parent.kind === "score"
        ? `score:${parent.movementID}:${parent.sectionID}`
        : `archive:${parent.archiveKind}:${parent.groupID}`;
    const group = groups.get(key) ?? { key, parent, galleries: [] };
    group.galleries.push(gallery);
    groups.set(key, group);
  }
  return [...groups.values()];
}

function groupHierarchy(galleries: GallerySummary[]): GalleryHierarchy {
  const movements = new Map<string, OwnerBranch>();
  const archiveKinds = new Map<string, OwnerBranch>();

  for (const owner of groupByOwner(galleries)) {
    const parent = owner.parent;
    if (parent.kind === "score") {
      const branch = movements.get(parent.movementID) ?? {
        key: parent.movementID,
        name: parent.movementName,
        owners: [],
      };
      branch.owners.push(owner);
      movements.set(parent.movementID, branch);
      continue;
    }

    const branch = archiveKinds.get(parent.archiveKind) ?? {
      key: parent.archiveKind,
      name: parent.archiveKind,
      owners: [],
    };
    branch.owners.push(owner);
    archiveKinds.set(parent.archiveKind, branch);
  }

  return { score: [...movements.values()], archive: [...archiveKinds.values()] };
}

function GalleryIndexCard({
  gallery,
  index,
  locale,
}: {
  gallery: GallerySummary;
  index: number;
  locale: Locale;
}) {
  const { t } = useUi();
  return (
    <article className="min-w-0 [contain-intrinsic-size:auto_21rem] [content-visibility:auto]">
      <TransitionLink
        className="group relative flex min-h-84 flex-col justify-end overflow-hidden border-r-2 border-b-2 border-ink bg-brand p-6 text-white no-underline"
        to={`/${locale}/galleries/${encodeURIComponent(gallery.id)}`}
        transition="forward"
      >
        <CardBackdrop
          scrim={gallery.previewThumbnailContentUrls.length ? "dark" : "brand"}
          sources={gallery.previewThumbnailContentUrls}
        />
        <span
          className="relative z-10 mb-auto font-mono text-3xl font-black text-white/65 tabular-nums"
          aria-hidden="true"
        >
          {String(index + 1).padStart(3, "0")}
        </span>
        <div className="relative z-10">
          <Eyebrow className="text-white/75">{t("gallery.collection")}</Eyebrow>
          <h4
            className="mb-3 break-words text-[clamp(1.6rem,3vw,2.7rem)] leading-none font-black text-balance"
            lang={localeLanguageTag(locale)}
          >
            {gallery.name || t("gallery.untitled")}
          </h4>
          <code className="text-xs text-white/65" translate="no">
            {gallery.id}
          </code>
        </div>
      </TransitionLink>
    </article>
  );
}

function GalleryBranch({
  branch,
  kind,
  locale,
}: {
  branch: OwnerBranch;
  kind: StoryParent["kind"];
  locale: Locale;
}) {
  const { t } = useUi();
  const title =
    kind === "score"
      ? branch.name || t("score.untitledMovement")
      : archiveKindLabel(branch.key as ArchiveKind, t);
  const galleryCount = branch.owners.reduce((count, owner) => count + owner.galleries.length, 0);

  return (
    <section
      aria-labelledby={`gallery-branch-${kind}-${branch.key}`}
      className="[contain-intrinsic-size:auto_42rem] [content-visibility:auto]"
    >
      <div className="mb-10 grid grid-cols-[minmax(0,1fr)_auto] items-end border-b-[3px] border-ink pb-4">
        <Eyebrow className="col-span-full">
          {kind === "score" ? t("score.movement") : t("archive.kindEyebrow")}
        </Eyebrow>
        <h3
          className="m-0 max-w-[24ch] text-[clamp(2rem,4vw,4rem)] leading-none font-black tracking-[-0.035em] uppercase"
          id={`gallery-branch-${kind}-${branch.key}`}
          lang={localeLanguageTag(locale)}
        >
          {title}
        </h3>
        <span className="pb-1 font-mono text-sm font-bold tabular-nums">
          {new Intl.NumberFormat(localeLanguageTag(locale)).format(galleryCount)}
        </span>
      </div>
      <div className="grid border-t-2 border-l-2 border-ink md:grid-cols-2">
        {branch.owners
          .flatMap((owner) => owner.galleries)
          .map((gallery, itemIndex) => (
            <AnimatedListItem id={gallery.id} key={gallery.id}>
              <GalleryIndexCard gallery={gallery} index={itemIndex} locale={locale} />
            </AnimatedListItem>
          ))}
      </div>
    </section>
  );
}

function GalleryFamily({
  branches,
  kind,
  locale,
}: {
  branches: OwnerBranch[];
  kind: StoryParent["kind"];
  locale: Locale;
}) {
  const { t } = useUi();
  if (!branches.length) return null;
  const title = kind === "score" ? t("score.title") : t("archive.title");

  return (
    <section aria-labelledby={`gallery-family-${kind}`}>
      <div className="mb-14 border-b-4 border-ink pb-5">
        <Eyebrow>{t("gallery.collection")}</Eyebrow>
        <h2
          className="m-0 text-[clamp(2.8rem,7vw,7rem)] leading-[0.82] font-black tracking-[-0.055em] uppercase"
          id={`gallery-family-${kind}`}
        >
          {title}
        </h2>
      </div>
      <div className="grid gap-20">
        {branches.map((branch) => (
          <GalleryBranch branch={branch} key={branch.key} kind={kind} locale={locale} />
        ))}
      </div>
    </section>
  );
}

export function GalleryIndexPage() {
  const { t } = useUi();
  const locale = requiredLocale(useParams().locale);
  const galleries = use(getGalleries(locale));
  const index = useCollectionIndex(galleries, gallerySearchValues, "archive");
  const hierarchy = groupHierarchy(index.visible);
  const hasGalleries = hierarchy.score.length > 0 || hierarchy.archive.length > 0;

  return (
    <ArchivePage description={t("gallery.description")} title={t("gallery.title")}>
      <PageHeader
        eyebrow={t("gallery.indexEyebrow")}
        meta={<span>{t("common.locale", { locale })}</span>}
        title={t("gallery.title")}
      />
      <CollectionControls
        count={index.visible.length}
        noun={t("collection.galleryNoun", { count: index.visible.length })}
        onOrder={index.setOrder}
        onQuery={index.setQuery}
        order={index.order}
        query={index.query}
      />
      {hasGalleries ? (
        <div className="grid gap-28">
          <GalleryFamily branches={hierarchy.archive} kind="archive" locale={locale} />
          <GalleryFamily branches={hierarchy.score} kind="score" locale={locale} />
        </div>
      ) : (
        <EmptyState title={t("gallery.noMatching")}>{t("gallery.noMatchingHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
