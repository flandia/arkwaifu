import { cachedRequest, fetchJson, pathSegment } from "./client";
import type {
  Locale,
  StoryDetail,
  StoryGroupDetail,
  StoryGroupSummary,
  StoryGroupType,
  StorySummary,
} from "./types";

/** Fetches story-group summaries for one locale. */
export function getStoryGroups(locale: Locale): Promise<StoryGroupSummary[]> {
  return cachedRequest(`groups:${locale}`, () => fetchJson(`/api/${locale}/story-groups`));
}

/** Fetches story summaries for one group. */
export function getStoriesByGroup(locale: Locale, groupID: string): Promise<StorySummary[]> {
  return cachedRequest(`stories:${locale}:${groupID}`, () =>
    fetchJson(`/api/${locale}/story-groups/${pathSegment(groupID)}/stories`),
  );
}

/** Fetches one story group and its artwork references. */
export function getStoryGroup(locale: Locale, groupID: string): Promise<StoryGroupDetail> {
  return cachedRequest(`group:${locale}:${groupID}`, () =>
    fetchJson(`/api/${locale}/story-groups/${pathSegment(groupID)}`),
  );
}

/** Fetches one story and its artwork references. */
export function getStory(locale: Locale, storyID: string): Promise<StoryDetail> {
  return cachedRequest(`story:${locale}:${storyID}`, () =>
    fetchJson(`/api/${locale}/stories/${pathSegment(storyID)}`),
  );
}

/** Fetches story groups for one locale and keeps groups of the requested type. */
export function getStoryGroupsByType(
  locale: Locale,
  type: StoryGroupType,
): Promise<StoryGroupSummary[]> {
  return cachedRequest(`groups-by-type:${locale}:${type}`, async () => {
    const groups = await getStoryGroups(locale);
    return groups.filter((group) => group.type === type);
  });
}

/** Fetches one story group and its story summaries concurrently. */
export function getStoryGroupWithStories(
  locale: Locale,
  groupID: string,
): Promise<[StoryGroupDetail, StorySummary[]]> {
  return cachedRequest(`group-with-stories:${locale}:${groupID}`, async () => {
    return Promise.all([getStoryGroup(locale, groupID), getStoriesByGroup(locale, groupID)]);
  });
}
