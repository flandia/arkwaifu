import { cachedRequest, fetchJson, pathSegment } from "./client";
import type {
  Locale,
  MediaReverseReferences,
  NarrativeMediaAsset,
  NarrativeMediaCategory,
} from "./types";

/** Fetches one independently addressable audio or video resource. */
export function getNarrativeMediaAsset(
  category: NarrativeMediaCategory,
  assetID: string,
): Promise<NarrativeMediaAsset> {
  return cachedRequest(`narrative-media:${category}:${assetID}`, () =>
    fetchJson(`/api/assets/narrative/${category}/${pathSegment(assetID)}`),
  );
}

/** Fetches locale-specific Story and collection references for one media resource. */
export function getNarrativeMediaReverseReferences(
  locale: Locale,
  category: NarrativeMediaCategory,
  assetID: string,
): Promise<MediaReverseReferences> {
  return cachedRequest(`narrative-media-references:${locale}:${category}:${assetID}`, () =>
    fetchJson(
      `/api/${locale}/assets/narrative/${category}/${pathSegment(assetID)}/reverse-references`,
    ),
  );
}
