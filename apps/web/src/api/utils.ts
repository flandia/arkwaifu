import type { ArtCategory, ArtReference } from "./types";

export function uniqueArtReferences(references: ArtReference[]): ArtReference[] {
  const seen = new Set<string>();
  return references.filter((reference) => {
    const key = `${reference.category}:${reference.artID}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function artTransitionName(category: ArtCategory, artID: string): string {
  let hash = 2166136261;
  const value = `${category}:${artID}`;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `art-${(hash >>> 0).toString(36)}`;
}

export function formatBytes(bytes: number, locale = "en"): string {
  if (bytes < 1024) return `${new Intl.NumberFormat(locale).format(bytes)}\u00a0B`;
  const units = ["KiB", "MiB", "GiB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && value >= 1024; index += 1) {
    value /= 1024;
    unit = units[index];
  }
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(value)}\u00a0${unit}`;
}
