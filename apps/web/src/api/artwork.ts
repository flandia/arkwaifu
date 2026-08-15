import { cachedRequest, fetchJson, pathSegment } from "./client";
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

/** Fetches one category-qualified retained source image. */
export function getSourceArt(category: ArtCategory, sourceID: string): Promise<SourceArt> {
  return cachedRequest(`source:${category}:${sourceID}`, () =>
    fetchJson(`/api/source-arts/${category}/${pathSegment(sourceID)}`),
  );
}

/** Fetches a composed artwork and each source layer it references. */
export function getArtWithSources(
  category: ArtCategory,
  artID: string,
): Promise<[ArtDetail, SourceArt[]]> {
  return cachedRequest(`art-with-sources:${category}:${artID}`, async () => {
    const art = await getArt(category, artID);
    const sources = await Promise.all(
      art.sourceArts.map((source) => getSourceArt(source.category, source.id)),
    );
    return [art, sources];
  });
}
