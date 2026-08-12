import { cachedRequest, fetchJson, pathSegment } from "./client";
import type {
  ArtReference,
  Locale,
  Story,
  StoryGroup,
  StoryGroupDetail,
  StoryGroupType,
} from "./types";
import { uniqueArtReferences } from "./utils";

export function getStoryGroups(locale: Locale): Promise<StoryGroup[]> {
  return cachedRequest(`groups:${locale}`, () => fetchJson(`/api/${locale}/story-groups`));
}

export function getStories(locale: Locale, groupID: string): Promise<Story[]> {
  return cachedRequest(`stories:${locale}:${groupID}`, () =>
    fetchJson(`/api/${locale}/story-groups/${pathSegment(groupID)}/stories`),
  );
}

export function getStoryGroup(locale: Locale, groupID: string): Promise<StoryGroupDetail> {
  return cachedRequest(`group:${locale}:${groupID}`, () =>
    fetchJson(`/api/${locale}/story-groups/${pathSegment(groupID)}`),
  );
}

export function getStory(locale: Locale, storyID: string): Promise<Story> {
  return cachedRequest(`story:${locale}:${storyID}`, () =>
    fetchJson(`/api/${locale}/stories/${pathSegment(storyID)}`),
  );
}

export function getStoryIndexData(locale: Locale, type: StoryGroupType): Promise<StoryGroup[]> {
  return cachedRequest(`group-index:${locale}:${type}`, async () => {
    const groups = await getStoryGroups(locale);
    return groups.filter((group) => group.type === type);
  });
}

export function getGroupData(
  locale: Locale,
  groupID: string,
): Promise<[StoryGroupDetail, Story[]]> {
  return cachedRequest(`group-page:${locale}:${groupID}`, async () => {
    return Promise.all([getStoryGroup(locale, groupID), getStories(locale, groupID)]);
  });
}

export function getStoryData(locale: Locale, storyID: string): Promise<[Story, ArtReference[]]> {
  return cachedRequest(`story-page:${locale}:${storyID}`, async () => {
    const story = await getStory(locale, storyID);
    return [story, uniqueArtReferences(story.artReferences)];
  });
}
