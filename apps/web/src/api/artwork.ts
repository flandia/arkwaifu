import { ApiError, cachedRequest, fetchJson, pathSegment } from "./client";
import type { ArtCategory, ArtContext, ArtDetail, Locale, SourceArt } from "./types";

/** Fetches one composed artwork by category and identifier. */
export function getArt(category: ArtCategory, artID: string): Promise<ArtDetail> {
  return cachedRequest(`art:${category}:${artID}`, () =>
    fetchJson(`/api/arts/${category}/${pathSegment(artID)}`),
  );
}

/** Fetches localized names, story occurrences, and sibling artwork. */
export function getArtContext(
  locale: Locale,
  category: ArtCategory,
  artID: string,
): Promise<ArtContext> {
  return cachedRequest(`art-context:${locale}:${category}:${artID}`, () =>
    fetchJson(`/api/${locale}/arts/${category}/${pathSegment(artID)}/context`),
  );
}

/** Fetches one source layer by its source-art identifier. */
export function getSourceArt(sourceID: string): Promise<SourceArt> {
  return cachedRequest(`source:${sourceID}`, () =>
    fetchJson(`/api/source-arts/${pathSegment(sourceID)}`),
  );
}

/** Finds categories for a category-less route from the previous web app. */
export function getLegacyArtCategories(artID: string): Promise<ArtCategory[]> {
  return cachedRequest(`legacy-art:${artID}`, async () => {
    const categories: ArtCategory[] = ["image", "background", "item", "character"];
    const results = await Promise.allSettled(categories.map((category) => getArt(category, artID)));
    const matches = categories.filter((_, index) => results[index]?.status === "fulfilled");
    if (matches.length) return matches;

    const serviceError = results.find(
      (result): result is PromiseRejectedResult =>
        result.status === "rejected" &&
        result.reason instanceof ApiError &&
        result.reason.status !== 404,
    );
    if (serviceError) throw serviceError.reason;
    return [];
  });
}

/** Fetches a composed artwork and each source layer it references. */
export function getArtWithSources(
  category: ArtCategory,
  artID: string,
): Promise<[ArtDetail, SourceArt[]]> {
  return cachedRequest(`art-with-sources:${category}:${artID}`, async () => {
    const art = await getArt(category, artID);
    const sources = await Promise.all(art.sourceArtIDs.map(getSourceArt));
    return [art, sources];
  });
}
