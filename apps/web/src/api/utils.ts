import type {
  NarrativeImageCategory,
  StoryNarrativeAssetReference,
  StoryMediaReference,
} from "./types";

type AssetReferenceHolder = { asset: { category: string; id: string } };

function uniqueAssetReferences<T extends AssetReferenceHolder>(references: T[]): T[] {
  const seen = new Set<string>();
  return references.filter((reference) => {
    const key = `${reference.asset.category}:${reference.asset.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** Keeps the first reference for each Narrative Image identity. */
export function uniqueStoryNarrativeAssetReferences(
  references: StoryNarrativeAssetReference[],
): StoryNarrativeAssetReference[] {
  return uniqueAssetReferences(references);
}

/** Keeps the first reference for each media kind and source identifier pair. */
export function uniqueStoryMediaReferences(
  references: StoryMediaReference[],
): StoryMediaReference[] {
  return uniqueAssetReferences(references);
}

/** Returns a stable Cascading Style Sheets (CSS) view-transition name for one image asset. */
export function assetTransitionName(category: NarrativeImageCategory, assetID: string): string {
  let hash = 2166136261;
  const value = `${category}:${assetID}`;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `asset-${(hash >>> 0).toString(36)}`;
}

/** Formats a byte count with binary units and locale-aware digits. */
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
