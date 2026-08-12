import { ApiError, cachedRequest, fetchJson, pathSegment } from "./client";
import type { ArtCategory, ArtContext, ArtDetail, Locale, SourceArt } from "./types";

export function getArt(category: ArtCategory, artID: string): Promise<ArtDetail> {
  return cachedRequest(`art:${category}:${artID}`, () =>
    fetchJson(`/api/arts/${category}/${pathSegment(artID)}`),
  );
}

export function getArtContext(
  locale: Locale,
  category: ArtCategory,
  artID: string,
): Promise<ArtContext> {
  return cachedRequest(`art-context:${locale}:${category}:${artID}`, () =>
    fetchJson(`/api/${locale}/arts/${category}/${pathSegment(artID)}/context`),
  );
}

export function getSourceArt(sourceID: string): Promise<SourceArt> {
  return cachedRequest(`source:${sourceID}`, () =>
    fetchJson(`/api/source-arts/${pathSegment(sourceID)}`),
  );
}

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

export function getArtData(
  category: ArtCategory,
  artID: string,
): Promise<[ArtDetail, SourceArt[]]> {
  return cachedRequest(`art-page:${category}:${artID}`, async () => {
    const art = await getArt(category, artID);
    const sources = await Promise.all(art.sourceArtIDs.map(getSourceArt));
    return [art, sources];
  });
}
