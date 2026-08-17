import { cachedRequest, fetchJson, pathSegment } from "./client";
import type { MediaDetail, MediaKind } from "./types";

/** Fetches one independently addressable audio or video resource. */
export function getMedia(kind: MediaKind, mediaID: string): Promise<MediaDetail> {
  return cachedRequest(`media:${kind}:${mediaID}`, () =>
    fetchJson(`/api/media/${kind}/${pathSegment(mediaID)}`),
  );
}
