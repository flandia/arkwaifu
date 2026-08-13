import { use } from "react";
import { useParams } from "react-router";
import { getStoryGroupsByType, type StoryGroupSummary } from "../../api";
import { useUi } from "../../i18n";
import { requiredLocale, requiredSection, useStorySections } from "../../navigation";
import {
  AnimatedListItem,
  CollectionControls,
  useCollectionIndex,
} from "../../shared/CollectionIndex";
import { ArchivePage, EmptyState, PageHeader } from "../../shared/Page";
import { StoryGroupCard } from "./StoryCards";

function groupSearchValues(group: StoryGroupSummary): string[] {
  return [group.name, group.id];
}

export function StoryIndexPage() {
  const { t } = useUi();
  const params = useParams();
  const locale = requiredLocale(params.locale);
  const section = requiredSection(params.section);
  const details = useStorySections()[section];
  const groups = use(getStoryGroupsByType(locale, details.type));
  const index = useCollectionIndex(groups, groupSearchValues);

  return (
    <ArchivePage description={`${details.title} · ${t("home.description")}`} title={details.title}>
      <PageHeader
        eyebrow={t("story.indexEyebrow", { index: details.index })}
        meta={<span>{t("common.locale", { locale })}</span>}
        title={details.title}
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
          aria-label={t("story.groupsLabel", { section: details.title })}
        >
          {index.visible.map((group) => (
            <AnimatedListItem id={group.id} key={group.id}>
              <StoryGroupCard group={group} locale={locale} section={section} />
            </AnimatedListItem>
          ))}
        </section>
      ) : (
        <EmptyState title={t("story.noMatchingGroups")}>
          {t("story.noMatchingGroupsHint")}
        </EmptyState>
      )}
    </ArchivePage>
  );
}
