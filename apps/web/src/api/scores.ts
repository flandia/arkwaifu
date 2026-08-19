import { cachedRequest, fetchJson, pathSegment } from "./client";
import type { Locale, MovementDetail, MovementSummary, SectionDetail, StoryDetail } from "./types";

/** Fetches every Score Movement for one locale in archive order. */
export function getMovements(locale: Locale): Promise<MovementSummary[]> {
  return cachedRequest(`movements:${locale}`, () => fetchJson(`/api/${locale}/scores`));
}

/** Fetches one Score Movement and its ordered divider/section sequence. */
export function getMovement(locale: Locale, movementID: string): Promise<MovementDetail> {
  return cachedRequest(`movement:${locale}:${movementID}`, () =>
    fetchJson(`/api/${locale}/scores/${pathSegment(movementID)}`),
  );
}

/** Fetches one Section with its stories, artwork, and gallery. */
export function getSection(
  locale: Locale,
  movementID: string,
  sectionID: string,
): Promise<SectionDetail> {
  return cachedRequest(`score-section:${locale}:${movementID}:${sectionID}`, () =>
    fetchJson(`/api/${locale}/scores/${pathSegment(movementID)}/${pathSegment(sectionID)}`),
  );
}

/** Fetches one story owned by a Section. */
export function getScoreStory(
  locale: Locale,
  movementID: string,
  sectionID: string,
  storyID: string,
): Promise<StoryDetail> {
  return cachedRequest(`score-story:${locale}:${movementID}:${sectionID}:${storyID}`, () =>
    fetchJson(
      `/api/${locale}/scores/${pathSegment(movementID)}/${pathSegment(sectionID)}/${pathSegment(storyID)}`,
    ),
  );
}
