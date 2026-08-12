import { cachedRequest, fetchJson } from "./client";
import type { ArtSummary } from "./types";

export function getUnclassifiedArts(): Promise<ArtSummary[]> {
  return cachedRequest("unclassified-arts", () => fetchJson("/api/unclassified-arts"));
}
