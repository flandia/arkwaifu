import { cachedRequest, fetchJson, pathSegment } from "./client";
import type {
  Locale,
  MaterialAsset,
  NarrativeImageAsset,
  NarrativeImageCategory,
  NarrativeImageReverseReferences,
} from "./types";

/** Fetches one Narrative Image Asset by category and identifier. */
export function getNarrativeImageAsset(
  category: NarrativeImageCategory,
  assetID: string,
): Promise<NarrativeImageAsset> {
  return cachedRequest(`narrative-image:${category}:${assetID}`, () =>
    fetchJson(`/api/assets/narrative/${category}/${pathSegment(assetID)}`),
  );
}

/** Fetches localized Reverse References for one Narrative Image Asset. */
export function getNarrativeImageReverseReferences(
  locale: Locale,
  category: NarrativeImageCategory,
  assetID: string,
): Promise<NarrativeImageReverseReferences> {
  return cachedRequest(`narrative-image-references:${locale}:${category}:${assetID}`, () =>
    fetchJson(
      `/api/${locale}/assets/narrative/${category}/${pathSegment(assetID)}/reverse-references`,
    ),
  );
}

/** Fetches one category-qualified Material Asset. */
export function getMaterialAsset(
  category: NarrativeImageCategory,
  assetID: string,
): Promise<MaterialAsset> {
  return cachedRequest(`material:${category}:${assetID}`, () =>
    fetchJson(`/api/assets/material/${category}/${pathSegment(assetID)}`),
  );
}

/** Fetches one Narrative Image Asset and its ordered Materials. */
export function getNarrativeImageAssetWithMaterials(
  category: NarrativeImageCategory,
  assetID: string,
): Promise<[NarrativeImageAsset, MaterialAsset[]]> {
  return cachedRequest(`narrative-image-with-materials:${category}:${assetID}`, async () => {
    const asset = await getNarrativeImageAsset(category, assetID);
    const materials = await Promise.all(
      asset.materials.map((material) => getMaterialAsset(material.category, material.id)),
    );
    return [asset, materials];
  });
}
