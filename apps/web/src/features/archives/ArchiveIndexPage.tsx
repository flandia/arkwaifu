import { use } from "react";
import { useParams } from "react-router";
import { getArchiveKinds } from "../../api/archives";
import type { ArchiveKind } from "../../api/types";
import { useUi } from "../../i18n";
import { archiveKinds, requiredLocale } from "../../navigation";
import { ArchivePage, EmptyState, PageHeader } from "../../shared/Page";
import { ArchiveKindCard } from "./ArchiveCards";

export function ArchiveIndexPage() {
  const { t } = useUi();
  const locale = requiredLocale(useParams().locale);
  const summaries = use(getArchiveKinds(locale));
  const counts = new Map(summaries.map((summary) => [summary.kind, summary.groupCount]));

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
          {(Object.keys(archiveKinds) as ArchiveKind[]).map((kind) => (
            <ArchiveKindCard
              count={counts.get(kind) ?? 0}
              index={archiveKinds[kind].index}
              key={kind}
              kind={kind}
              locale={locale}
            />
          ))}
        </ol>
      ) : (
        <EmptyState title={t("archive.noKinds")}>{t("archive.noKindsHint")}</EmptyState>
      )}
    </ArchivePage>
  );
}
