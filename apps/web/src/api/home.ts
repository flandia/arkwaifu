import { cachedRequest } from "./client";
import { getGalleries } from "./galleries";
import { getStoryGroups } from "./stories";
import type { GallerySummary, Locale, StoryGroupSummary } from "./types";

/** Fetches the story-group and gallery collections shown on the home page. */
export function getHomeCollections(
  locale: Locale,
): Promise<[StoryGroupSummary[], GallerySummary[]]> {
  return cachedRequest(`home:${locale}`, () =>
    Promise.all([getStoryGroups(locale), getGalleries(locale)]),
  );
}
