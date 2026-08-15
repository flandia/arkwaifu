import { cachedRequest, fetchJson, pathSegment } from "./client";
import type {
  ArchiveGroupDetail,
  ArchiveGroupSummary,
  ArchiveKind,
  ArchiveKindSummary,
  Locale,
  StoryDetail,
} from "./types";

/** Fetches the non-Score Archive kinds and their group counts. */
export function getArchiveKinds(locale: Locale): Promise<ArchiveKindSummary[]> {
  return cachedRequest(`archive-kinds:${locale}`, () => fetchJson(`/api/${locale}/archives`));
}

/** Fetches the groups owned by one Archive kind. */
export function getArchiveGroups(
  locale: Locale,
  kind: ArchiveKind,
): Promise<ArchiveGroupSummary[]> {
  return cachedRequest(`archive-groups:${locale}:${kind}`, () =>
    fetchJson(`/api/${locale}/archives/${pathSegment(kind)}`),
  );
}

/** Fetches one Archive group with its stories, artwork, and gallery. */
export function getArchiveGroup(
  locale: Locale,
  kind: ArchiveKind,
  groupID: string,
): Promise<ArchiveGroupDetail> {
  return cachedRequest(`archive-group:${locale}:${kind}:${groupID}`, () =>
    fetchJson(`/api/${locale}/archives/${pathSegment(kind)}/${pathSegment(groupID)}`),
  );
}

/** Fetches one story owned by an Archive group. */
export function getArchiveStory(
  locale: Locale,
  kind: ArchiveKind,
  groupID: string,
  storyID: string,
): Promise<StoryDetail> {
  return cachedRequest(`archive-story:${locale}:${kind}:${groupID}:${storyID}`, () =>
    fetchJson(
      `/api/${locale}/archives/${pathSegment(kind)}/${pathSegment(groupID)}/${pathSegment(storyID)}`,
    ),
  );
}
