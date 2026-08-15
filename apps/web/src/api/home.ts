import { cachedRequest } from "./client";
import { getArchiveKinds } from "./archives";
import { getGalleries } from "./galleries";
import { getMovements } from "./scores";
import type { ArchiveKindSummary, GallerySummary, Locale, MovementSummary } from "./types";

export interface HomeCollections {
  movements: MovementSummary[];
  archives: ArchiveKindSummary[];
  galleries: GallerySummary[];
}

/** Fetches every independent collection shown on the home page in parallel. */
export function getHomeCollections(locale: Locale): Promise<HomeCollections> {
  return cachedRequest(`home:${locale}`, () =>
    Promise.all([getMovements(locale), getArchiveKinds(locale), getGalleries(locale)]).then(
      ([movements, archives, galleries]) => ({ movements, archives, galleries }),
    ),
  );
}
