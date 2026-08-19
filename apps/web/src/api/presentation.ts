import { cachedRequest, fetchJson, pathSegment } from "./client";
import type {
  Locale,
  PresentationAssetCategory,
  PresentationAssetDetail,
  PresentationAssetSummary,
} from "./types";

export function getPresentationAssets(locale: Locale): Promise<PresentationAssetSummary[]> {
  return cachedRequest(`presentation-assets:${locale}`, () =>
    fetchJson(`/api/${locale}/assets/presentation`),
  );
}

export function getPresentationAsset(
  locale: Locale,
  category: PresentationAssetCategory,
  assetID: string,
): Promise<PresentationAssetDetail> {
  return cachedRequest(`presentation-asset:${locale}:${category}:${assetID}`, () =>
    fetchJson(`/api/${locale}/assets/presentation/${category}/${pathSegment(assetID)}`),
  );
}
