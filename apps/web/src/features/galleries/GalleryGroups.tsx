import type { GalleryDetail, GalleryGroup, Locale } from "../../api/types";
import { useUi } from "../../i18n";
import { localeLanguageTag, TransitionLink } from "../../navigation";
import { CardBackdrop } from "../../shared/ui/CardBackdrop";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";

function GalleryGroupCard({
  group,
  galleryID,
  locale,
}: {
  group: GalleryGroup;
  galleryID: string;
  locale: Locale;
}) {
  const { t } = useUi();
  const cover = group.references[0];
  const title = group.name || t("gallery.untitledGroup");
  const content = (
    <>
      <CardBackdrop
        imageClassName="object-cover"
        scrim={cover?.previewUrl ? "dark" : "brand"}
        sources={cover?.previewUrl ? [cover.previewUrl] : []}
      />
      {group.references.length > 1 ? (
        <span
          className="absolute top-5 left-5 z-10 grid size-10 place-items-center border-2 border-white bg-black/35 font-mono text-sm font-black tabular-nums"
          aria-label={t("gallery.artworkCount", { count: group.references.length })}
        >
          {group.references.length}
        </span>
      ) : null}
      <div className="relative z-10">
        <Eyebrow className="text-white/75">{t("gallery.group")}</Eyebrow>
        <h3
          className="mb-3 max-w-[22ch] break-words text-[clamp(1.5rem,3vw,2.7rem)] leading-none font-black text-balance"
          lang={localeLanguageTag(locale)}
        >
          {title}
        </h3>
        {group.description ? (
          <p
            className="mb-3 line-clamp-3 max-w-2xl leading-relaxed text-white/80"
            lang={localeLanguageTag(locale)}
          >
            {group.description}
          </p>
        ) : null}
        <code className="text-xs text-white/65" translate="no">
          {group.id}
        </code>
      </div>
    </>
  );

  return (
    <article className="min-w-0 [contain-intrinsic-size:auto_23rem] [content-visibility:auto]">
      {cover ? (
        <TransitionLink
          aria-label={t("common.open", { name: title })}
          className="group relative flex min-h-92 flex-col justify-end overflow-hidden border-r-2 border-b-2 border-ink bg-brand p-6 text-white no-underline"
          to={`/${locale}/galleries/${encodeURIComponent(galleryID)}/groups/${encodeURIComponent(group.id)}/${encodeURIComponent(cover.cgID)}`}
          transition="forward"
        >
          {content}
          <span
            className="absolute top-5 right-5 z-10 grid size-10 place-items-center border-2 border-white bg-black/35 font-black"
            aria-hidden="true"
          >
            ↗
          </span>
        </TransitionLink>
      ) : (
        <div className="relative flex min-h-92 flex-col justify-end overflow-hidden border-r-2 border-b-2 border-ink bg-brand p-6 text-white">
          {content}
        </div>
      )}
    </article>
  );
}

export function GalleryGroups({
  gallery,
  locale,
  tone = "light",
}: {
  gallery: GalleryDetail;
  locale: Locale;
  tone?: "light" | "dark";
}) {
  const { t } = useUi();
  if (!gallery.groups.length) return null;

  return (
    <section className="mt-16" aria-labelledby={`gallery-${gallery.id}-groups`}>
      <SectionHeading
        eyebrow={t("gallery.selection")}
        meta={new Intl.NumberFormat(localeLanguageTag(locale)).format(gallery.groups.length)}
        title={t("gallery.groups")}
        titleId={`gallery-${gallery.id}-groups`}
        tone={tone}
      />
      <div
        className={
          tone === "dark"
            ? "grid border-t-2 border-l-2 border-black md:grid-cols-2 [&_a]:border-black"
            : "grid border-t-2 border-l-2 border-ink md:grid-cols-2"
        }
      >
        {gallery.groups.map((group) => (
          <GalleryGroupCard group={group} galleryID={gallery.id} key={group.id} locale={locale} />
        ))}
      </div>
    </section>
  );
}
