import { cachedRequest, fetchJson, pathSegment } from "./client";
import type { GalleryDetail, GallerySummary, Locale } from "./types";

/** Fetches gallery summaries for one locale. */
export function getGalleries(locale: Locale): Promise<GallerySummary[]> {
  return cachedRequest(`galleries:${locale}`, () => fetchJson(`/api/${locale}/galleries`));
}

/** Fetches one gallery and its ordered entries. */
export function getGallery(locale: Locale, galleryID: string): Promise<GalleryDetail> {
  return cachedRequest(`gallery:${locale}:${galleryID}`, () =>
    fetchJson(`/api/${locale}/galleries/${pathSegment(galleryID)}`),
  );
}
