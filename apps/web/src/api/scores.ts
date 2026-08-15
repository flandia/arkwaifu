import { cachedRequest, fetchJson, pathSegment } from "./client";
import type {
  Locale,
  MovementDetail,
  MovementSummary,
  ScoreSectionDetail,
  StoryDetail,
} from "./types";

export interface MovementReadingIndex {
  movement: MovementDetail;
  sections: ScoreSectionDetail[];
}

/** Fetches every Score Movement for one locale in archive order. */
export function getMovements(locale: Locale): Promise<MovementSummary[]> {
  return cachedRequest(`movements:${locale}`, () => fetchJson(`/api/${locale}/scores`));
}

/** Fetches one Score Movement and its ordered split/section sequence. */
export function getMovement(locale: Locale, movementID: string): Promise<MovementDetail> {
  return cachedRequest(`movement:${locale}:${movementID}`, () =>
    fetchJson(`/api/${locale}/scores/${pathSegment(movementID)}`),
  );
}

/** Fetches one Movement and the stories shown directly below it in the Score index. */
export function getMovementReadingIndex(
  locale: Locale,
  movementID: string,
): Promise<MovementReadingIndex> {
  return cachedRequest(`movement-reading-index:${locale}:${movementID}`, async () => {
    const movement = await getMovement(locale, movementID);
    const sections = movement.items.flatMap((item) =>
      item.kind === "section" ? [item.section] : [],
    );
    return {
      movement,
      sections: await Promise.all(
        sections.map((section) => getScoreSection(locale, movement.id, section.id)),
      ),
    };
  });
}

/** Fetches one Movement section with its stories, artwork, and gallery. */
export function getScoreSection(
  locale: Locale,
  movementID: string,
  sectionID: string,
): Promise<ScoreSectionDetail> {
  return cachedRequest(`score-section:${locale}:${movementID}:${sectionID}`, () =>
    fetchJson(`/api/${locale}/scores/${pathSegment(movementID)}/${pathSegment(sectionID)}`),
  );
}

/** Fetches one story owned by a Score section. */
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
