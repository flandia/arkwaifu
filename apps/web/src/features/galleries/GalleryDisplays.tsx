import type { GalleryDetail, GalleryDisplay, Locale } from "../../api/types";
import { useUi } from "../../i18n";
import { localeLanguageTag, TransitionLink } from "../../navigation";
import { CardBackdrop } from "../../shared/ui/CardBackdrop";
import { Eyebrow, SectionHeading } from "../../shared/ui/Typography";

function GalleryDisplayCard({
  display,
  galleryID,
  locale,
}: {
  display: GalleryDisplay;
  galleryID: string;
  locale: Locale;
}) {
  const { t } = useUi();
  const cover = display.artworks[0];
  const title = display.name || t("gallery.untitledDisplay");
  const content = (
    <>
      <CardBackdrop
        imageClassName="object-cover"
        scrim={cover?.thumbnailContentUrl ? "dark" : "brand"}
        sources={cover?.thumbnailContentUrl ? [cover.thumbnailContentUrl] : []}
      />
      {display.artworks.length > 1 ? (
        <span
          className="absolute top-5 left-5 z-10 grid size-10 place-items-center border-2 border-white bg-black/35 font-mono text-sm font-black tabular-nums"
          aria-label={t("gallery.artworkCount", { count: display.artworks.length })}
        >
          {display.artworks.length}
        </span>
      ) : null}
      <div className="relative z-10">
        <Eyebrow className="text-white/75">{t("gallery.display")}</Eyebrow>
        <h3
          className="mb-3 max-w-[22ch] break-words text-[clamp(1.5rem,3vw,2.7rem)] leading-none font-black text-balance"
          lang={localeLanguageTag(locale)}
        >
          {title}
        </h3>
        {display.description ? (
          <p
            className="mb-3 line-clamp-3 max-w-2xl leading-relaxed text-white/80"
            lang={localeLanguageTag(locale)}
          >
            {display.description}
          </p>
        ) : null}
        <code className="text-xs text-white/65" translate="no">
          {display.id}
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
          to={`/${locale}/galleries/${encodeURIComponent(galleryID)}/displays/${encodeURIComponent(display.id)}/${encodeURIComponent(cover.cgID)}`}
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

export function GalleryDisplays({
  gallery,
  locale,
  tone = "light",
}: {
  gallery: GalleryDetail;
  locale: Locale;
  tone?: "light" | "dark";
}) {
  const { t } = useUi();
  if (!gallery.displays.length) return null;

  return (
    <section className="mt-16" aria-labelledby={`gallery-${gallery.id}-displays`}>
      <SectionHeading
        eyebrow={t("gallery.selection")}
        meta={new Intl.NumberFormat(localeLanguageTag(locale)).format(gallery.displays.length)}
        title={t("gallery.displays")}
        titleId={`gallery-${gallery.id}-displays`}
        tone={tone}
      />
      <div
        className={
          tone === "dark"
            ? "grid border-t-2 border-l-2 border-black md:grid-cols-2 [&_a]:border-black"
            : "grid border-t-2 border-l-2 border-ink md:grid-cols-2"
        }
      >
        {gallery.displays.map((display) => (
          <GalleryDisplayCard
            display={display}
            galleryID={gallery.id}
            key={display.id}
            locale={locale}
          />
        ))}
      </div>
    </section>
  );
}
