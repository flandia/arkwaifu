import { cachedRequest, fetchJson, pathSegment } from "./client";
import type {
  ArtReference,
  Locale,
  StoryDetail,
  StoryGroupDetail,
  StoryGroupSummary,
  StoryGroupType,
  StorySummary,
} from "./types";
import { uniqueArtReferences } from "./utils";

export function getStoryGroups(locale: Locale): Promise<StoryGroupSummary[]> {
  return cachedRequest(`groups:${locale}`, () => fetchJson(`/api/${locale}/story-groups`));
}

export function getStoriesByGroup(locale: Locale, groupID: string): Promise<StorySummary[]> {
  return cachedRequest(`stories:${locale}:${groupID}`, () =>
    fetchJson(`/api/${locale}/story-groups/${pathSegment(groupID)}/stories`),
  );
}

export function getStoryGroup(locale: Locale, groupID: string): Promise<StoryGroupDetail> {
  return cachedRequest(`group:${locale}:${groupID}`, () =>
    fetchJson(`/api/${locale}/story-groups/${pathSegment(groupID)}`),
  );
}

export function getStory(locale: Locale, storyID: string): Promise<StoryDetail> {
  return cachedRequest(`story:${locale}:${storyID}`, () =>
    fetchJson(`/api/${locale}/stories/${pathSegment(storyID)}`),
  );
}

export function getStoryIndexData(
  locale: Locale,
  type: StoryGroupType,
): Promise<StoryGroupSummary[]> {
  return cachedRequest(`group-index:${locale}:${type}`, async () => {
    const groups = await getStoryGroups(locale);
    return groups.filter((group) => group.type === type);
  });
}

export function getStoryGroupData(
  locale: Locale,
  groupID: string,
): Promise<[StoryGroupDetail, StorySummary[]]> {
  return cachedRequest(`group-page:${locale}:${groupID}`, async () => {
    return Promise.all([getStoryGroup(locale, groupID), getStoriesByGroup(locale, groupID)]);
  });
}

export function getStoryData(
  locale: Locale,
  storyID: string,
): Promise<[StoryDetail, ArtReference[]]> {
  return cachedRequest(`story-page:${locale}:${storyID}`, async () => {
    const story = await getStory(locale, storyID);
    return [story, uniqueArtReferences(story.artReferences)];
  });
}
