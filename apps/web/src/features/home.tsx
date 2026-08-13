import { use } from "react";
import { useParams } from "react-router";
import { getHomeCollections, type ArtCategory } from "../api";
import { useUi } from "../i18n";
import {
  requiredLocale,
  storySections,
  TransitionLink,
  useCategoryLabel,
  useStorySections,
  type StorySection,
} from "../navigation";
import { ArchivePage } from "../shared/Page";
import { ActionLink, Eyebrow, SectionHeading, cn } from "../shared/ui";

const artCategories: ArtCategory[] = ["image", "background", "item", "character"];

function EntryCard({
  count,
  featured = false,
  index,
  label,
  to,
}: {
  count: number;
  featured?: boolean;
  index: string;
  label: string;
  to: string;
}) {
  return (
    <TransitionLink
      className={cn(
        "group grid min-h-48 grid-cols-[2.5rem_minmax(0,1fr)_auto] gap-4 border-r-2 border-b-2 border-ink bg-surface p-5 no-underline transition-colors hover:bg-brand-soft",
        featured && "bg-brand text-white hover:bg-brand/90",
      )}
      to={to}
    >
      <span className="font-mono text-xs font-extrabold tabular-nums opacity-70" aria-hidden="true">
        {index}
      </span>
      <h3 className="m-0 self-center text-[clamp(1.5rem,3vw,2.75rem)] leading-none font-black tracking-tight text-balance uppercase">
        {label}
      </h3>
      <strong className="self-end font-mono text-[clamp(2.5rem,5vw,4.5rem)] leading-none tabular-nums">
        {new Intl.NumberFormat().format(count)}
      </strong>
    </TransitionLink>
  );
}

export function HomePage() {
  const { t } = useUi();
  const locale = requiredLocale(useParams().locale);
  const localizedSections = useStorySections();
  const labelCategory = useCategoryLabel();
  const [groups, galleries] = use(getHomeCollections(locale));

  const counts = Object.fromEntries(
    Object.entries(storySections).map(([slug, section]) => [
      slug,
      groups.filter((group) => group.type === section.type).length,
    ]),
  ) as Record<StorySection, number>;

  return (
    <ArchivePage description={t("home.description")} title={t("home.pageTitle")}>
      <section className="grid min-h-[min(44rem,calc(100vh-9rem))] border-[3px] border-ink bg-surface min-[56rem]:grid-cols-[minmax(0,1.35fr)_minmax(16rem,0.65fr)]">
        <div className="self-center p-[clamp(2rem,6vw,6rem)]">
          <Eyebrow>{t("home.eyebrow", { locale })}</Eyebrow>
          <h1
            className="m-0 max-w-[9ch] font-display text-[clamp(4.5rem,10vw,10rem)] leading-[0.88] font-black tracking-[-0.035em] text-balance max-sm:text-[clamp(3rem,17vw,5rem)]"
            translate="no"
          >
            {t("home.title")}
          </h1>
          <p className="mt-7 max-w-3xl text-[clamp(1.05rem,1.8vw,1.35rem)] leading-relaxed text-ink/75">
            {t("home.description")}
          </p>
          <div className="mt-8 flex flex-wrap gap-4 max-[42rem]:grid">
            <ActionLink adornment="forward" to={`/${locale}/stories/main`} transition="forward">
              {t("home.browseStories")}
            </ActionLink>
            <ActionLink variant="secondary" to={`/${locale}/galleries`}>
              {t("home.openGalleries")}
            </ActionLink>
          </div>
        </div>
        <div className="relative grid min-h-64 overflow-hidden border-t-[3px] border-ink bg-brand text-white min-[56rem]:border-t-0 min-[56rem]:border-l-[3px]">
          <span
            className="m-auto font-display text-[clamp(9rem,22vw,22rem)] leading-[0.75] tracking-[-0.12em] opacity-50"
            aria-hidden="true"
          >
            AW
          </span>
          <small className="absolute right-6 bottom-6 border-2 border-white px-3 py-2 font-mono text-xs font-black tracking-widest uppercase">
            {t("home.signal")}
          </small>
        </div>
      </section>

      <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="archive-summary-title">
        <SectionHeading
          eyebrow={t("home.indexEyebrow")}
          title={t("home.indexTitle")}
          titleId="archive-summary-title"
        />
        <div className="grid border-t-2 border-l-2 border-ink md:grid-cols-2">
          {Object.entries(localizedSections).map(([slug, section]) => (
            <EntryCard
              count={counts[slug as StorySection]}
              index={section.index}
              key={slug}
              label={section.title}
              to={`/${locale}/stories/${slug}`}
            />
          ))}
          <EntryCard
            count={galleries.length}
            featured
            index="08"
            label={t("navigation.galleries")}
            to={`/${locale}/galleries`}
          />
        </div>
      </section>

      <section className="mt-[clamp(4rem,9vw,8rem)]" aria-labelledby="art-taxonomy-title">
        <SectionHeading
          eyebrow={t("home.taxonomyEyebrow")}
          title={t("home.taxonomyTitle")}
          titleId="art-taxonomy-title"
        />
        <ul className="m-0 grid list-none border-t-2 border-l-2 border-ink p-0 sm:grid-cols-2 lg:grid-cols-4">
          {artCategories.map((category) => (
            <li className="border-r-2 border-b-2 border-ink bg-surface p-5" key={category}>
              <strong className="text-lg font-black uppercase">
                {labelCategory(category, true)}
              </strong>
            </li>
          ))}
        </ul>
      </section>
    </ArchivePage>
  );
}
