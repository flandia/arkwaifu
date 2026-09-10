import { cachedRequest, fetchJson, pathSegment } from "./client";
import type { Locale, SearchResult } from "./types";

/** Fetches up to 100 ranked metadata search results for one locale. */
export function getSearchResults(
  locale: Locale,
  query: string,
  signal?: AbortSignal,
): Promise<SearchResult[]> {
  return cachedRequest(
    `search:${locale}:${query}`,
    () => fetchJson(`/api/${locale}/search?q=${pathSegment(query)}`, signal),
    signal,
  );
}
