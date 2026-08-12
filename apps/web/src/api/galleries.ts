import { cachedRequest, fetchJson, pathSegment } from "./client";
import type { GalleryDetail, GalleryEntry, GallerySummary, Locale } from "./types";

export function getGalleries(locale: Locale): Promise<GallerySummary[]> {
  return cachedRequest(`galleries:${locale}`, () => fetchJson(`/api/${locale}/galleries`));
}

export function getGallery(locale: Locale, galleryID: string): Promise<GalleryDetail> {
  return cachedRequest(`gallery:${locale}:${galleryID}`, () =>
    fetchJson(`/api/${locale}/galleries/${pathSegment(galleryID)}`),
  );
}

export function getGalleryData(
  locale: Locale,
  galleryID: string,
): Promise<[GalleryDetail, GalleryEntry[]]> {
  return cachedRequest(`gallery-page:${locale}:${galleryID}`, async () => {
    const gallery = await getGallery(locale, galleryID);
    return [gallery, gallery.entries];
  });
}
