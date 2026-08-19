import { cachedRequest, fetchJson } from "./client";
import type { Locale, OrphanNarrativeAssets } from "./types";

/** Fetches all six categories of Orphan Narrative Assets. */
export function getOrphanNarrativeAssets(locale: Locale): Promise<OrphanNarrativeAssets> {
  return cachedRequest(`orphan-narrative-assets:${locale}`, () =>
    fetchJson(`/api/${locale}/orphans`),
  );
}
