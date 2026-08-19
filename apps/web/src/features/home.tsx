import { use } from "react";
import { useParams } from "react-router";
import { getHomeCollections } from "../api/home";
import type { ArchiveCategory } from "../api/types";
import { useUi } from "../i18n";
import {
  archiveCategoryLabel,
  archiveCategories,
  requiredLocale,
  TransitionLink,
} from "../navigation";
import { ArchivePage } from "../shared/Page";
import { ActionLink } from "../shared/ui/Action";
import { cn } from "../shared/ui/cn";
import { Eyebrow, SectionHeading } from "../shared/ui/Typography";

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
        "group grid min-h-48 grid-cols-[2.5rem_minmax(0,1fr)_auto] gap-4 border-r-2 border-b-2 border-ink bg-surface p-5 no-underline transition-colors hover:bg-brand-soft [contain-intrinsic-size:auto_12rem] [content-visibility:auto]",
        featured && "bg-brand text-white hover:bg-brand/90",
      )}
      to={to}
    >
      <span className="font-mono text-xs font-extrabold opacity-70 tabular-nums" aria-hidden="true">
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
  const { movements, archives, galleries } = use(getHomeCollections(locale));
  const archiveCounts = new Map(
    archives.map((summary) => [summary.archiveCategory, summary.groupCount]),
  );
  const scoreCollectionCount = movements.reduce(
    (count, movement) => count + movement.sectionCount,
    0,
  );

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
            <ActionLink adornment="forward" to={`/${locale}/scores`} transition="forward">
              {t("home.openScores")}
            </ActionLink>
            <ActionLink variant="secondary" to={`/${locale}/archives`}>
              {t("home.openArchives")}
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
          <EntryCard
            count={scoreCollectionCount}
            featured
            index="S"
            label={t("score.title")}
            to={`/${locale}/scores`}
          />
          {(Object.keys(archiveCategories) as ArchiveCategory[]).map((category) => (
            <EntryCard
              count={archiveCounts.get(category) ?? 0}
              index={archiveCategories[category].index}
              key={category}
              label={archiveCategoryLabel(category, t)}
              to={`/${locale}/archives/${category}`}
            />
          ))}
          <EntryCard
            count={galleries.length}
            index="C1"
            label={t("gallery.title")}
            to={`/${locale}/galleries`}
          />
        </div>
      </section>
    </ArchivePage>
  );
}
