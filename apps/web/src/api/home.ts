import { cachedRequest } from "./client";
import { getArchiveCategories } from "./archives";
import { getGalleries } from "./galleries";
import { getMovements } from "./scores";
import type { ArchiveCategorySummary, GallerySummary, Locale, MovementSummary } from "./types";

export interface HomeCollections {
  movements: MovementSummary[];
  archives: ArchiveCategorySummary[];
  galleries: GallerySummary[];
}

/** Fetches every independent collection shown on the home page in parallel. */
export function getHomeCollections(locale: Locale): Promise<HomeCollections> {
  return cachedRequest(`home:${locale}`, () =>
    Promise.all([getMovements(locale), getArchiveCategories(locale), getGalleries(locale)]).then(
      ([movements, archives, galleries]) => ({ movements, archives, galleries }),
    ),
  );
}
