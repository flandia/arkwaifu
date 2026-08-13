import { cachedRequest, fetchJson } from "./client";
import type { UnreferencedArt } from "./types";

/** Fetches artwork referenced by neither a story nor a gallery. */
export function getUnreferencedArts(): Promise<UnreferencedArt[]> {
  return cachedRequest("unreferenced-arts", () => fetchJson("/api/unreferenced-arts"));
}
