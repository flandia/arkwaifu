import { use } from "react";
import { useParams } from "react-router";
import { getArchiveCategories } from "../../api/archives";
import type { ArchiveCategory } from "../../api/types";
import { useUi } from "../../i18n";
import { archiveCategories, requiredLocale } from "../../navigation";
import { ArchivePage, EmptyState, PageHeader } from "../../shared/Page";
import { ArchiveCategoryCard } from "./ArchiveCards";

export function ArchiveIndexPage() {
  const { t } = useUi();
  const locale = requiredLocale(useParams().locale);
  const summaries = use(getArchiveCategories(locale));
  const counts = new Map(summaries.map((summary) => [summary.archiveCategory, summary.groupCount]));

  return (
    <ArchivePage description={t("archive.description")} title={t("archive.title")}>
      <PageHeader
        description={t("archive.description")}
        eyebrow={t("archive.indexEyebrow")}
        meta={<span>{t("common.locale", { locale })}</span>}
        title={t("archive.title")}
      />
      {summaries.length ? (
        <ol className="m-0 mt-12 grid list-none border-t-2 border-l-2 border-ink p-0 md:grid-cols-2">
          {(Object.keys(archiveCategories) as ArchiveCategory[]).map((category) => (
            <ArchiveCategoryCard
              category={category}
              count={counts.get(category) ?? 0}
              index={archiveCategories[category].index}
              key={category}
              locale={locale}
            />
          ))}
        </ol>
      ) : (
        <EmptyState title={t("archive.noCategories")}>{t("archive.noCategoriesHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
