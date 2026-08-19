import { use } from "react";
import { useParams } from "react-router";
import { getArchiveGroups } from "../../api/archives";
import type { ArchiveGroupSummary } from "../../api/types";
import { useUi } from "../../i18n";
import { archiveCategoryLabel, requiredArchiveCategory, requiredLocale } from "../../navigation";
import { CollectionControls, useCollectionIndex } from "../../shared/CollectionIndex";
import { ArchivePage, BackLink, EmptyState, PageHeader } from "../../shared/Page";
import { ArchiveGroupCard } from "./ArchiveCards";

function groupSearchValues(group: ArchiveGroupSummary): string[] {
  return [group.name, group.id, group.type];
}

export function ArchiveGroupsPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const category = requiredArchiveCategory(params["archive-category"]);
  const groups = use(getArchiveGroups(locale, category));
  const index = useCollectionIndex(groups, groupSearchValues);
  const title = archiveCategoryLabel(category, t);

  return (
    <ArchivePage description={t("archive.categoryDescription", { name: title })} title={title}>
      <BackLink to={`/${locale}/archives`}>{t("archive.backToArchives")}</BackLink>
      <PageHeader
        eyebrow={t("archive.categoryEyebrow")}
        meta={<span>{t("common.locale", { locale })}</span>}
        title={title}
      />
      <CollectionControls
        count={index.visible.length}
        noun={t("collection.groupNoun", { count: index.visible.length })}
        onOrder={index.setOrder}
        onQuery={index.setQuery}
        order={index.order}
        query={index.query}
      />
      {index.visible.length ? (
        <section
          className="grid border-t-2 border-l-2 border-ink md:grid-cols-2"
          aria-label={title}
        >
          {index.visible.map((group) => (
            <ArchiveGroupCard group={group} key={group.id} locale={locale} />
          ))}
        </section>
      ) : (
        <EmptyState title={t("archive.noGroups")}>{t("archive.noGroupsHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
