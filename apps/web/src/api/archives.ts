import { cachedRequest, fetchJson, pathSegment } from "./client";
import type {
  ArchiveGroupDetail,
  ArchiveGroupSummary,
  ArchiveCategory,
  ArchiveCategorySummary,
  Locale,
  StoryDetail,
} from "./types";

/** Fetches the Archive Categories and their Story Group counts. */
export function getArchiveCategories(locale: Locale): Promise<ArchiveCategorySummary[]> {
  return cachedRequest(`archive-categories:${locale}`, () => fetchJson(`/api/${locale}/archives`));
}

/** Fetches the Story Groups owned by one Archive Category. */
export function getArchiveGroups(
  locale: Locale,
  category: ArchiveCategory,
): Promise<ArchiveGroupSummary[]> {
  return cachedRequest(`archive-groups:${locale}:${category}`, () =>
    fetchJson(`/api/${locale}/archives/${pathSegment(category)}`),
  );
}

/** Fetches one Archive group with its stories, artwork, and gallery. */
export function getArchiveGroup(
  locale: Locale,
  category: ArchiveCategory,
  groupID: string,
): Promise<ArchiveGroupDetail> {
  return cachedRequest(`archive-group:${locale}:${category}:${groupID}`, () =>
    fetchJson(`/api/${locale}/archives/${pathSegment(category)}/${pathSegment(groupID)}`),
  );
}

/** Fetches one story owned by an Archive group. */
export function getArchiveStory(
  locale: Locale,
  category: ArchiveCategory,
  groupID: string,
  storyID: string,
): Promise<StoryDetail> {
  return cachedRequest(`archive-story:${locale}:${category}:${groupID}:${storyID}`, () =>
    fetchJson(
      `/api/${locale}/archives/${pathSegment(category)}/${pathSegment(groupID)}/${pathSegment(storyID)}`,
    ),
  );
}
