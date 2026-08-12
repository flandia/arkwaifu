import { cachedRequest } from "./client";
import { getGalleries } from "./galleries";
import { getStoryGroups } from "./stories";
import type { GallerySummary, Locale, StoryGroup } from "./types";

export function getHomeData(locale: Locale): Promise<[StoryGroup[], GallerySummary[]]> {
  return cachedRequest(`home:${locale}`, () =>
    Promise.all([getStoryGroups(locale), getGalleries(locale)]),
  );
}
