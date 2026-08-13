/**
 * Internal API-client surface for web routes and feature components.
 *
 * This barrel exposes archive requests, their response models, and shared response utilities. Transport and cache implementation details stay private to this directory.
 */
export {
  getArt,
  getArtContext,
  getArtWithSources,
  getLegacyArtCategories,
  getSourceArt,
} from "./artwork";
export { ApiError, clearApiCache } from "./client";
export { getGalleries, getGallery } from "./galleries";
export { getHomeCollections } from "./home";
export {
  getStoryGroup,
  getStoryGroupWithStories,
  getStoriesByGroup,
  getStory,
  getStoryGroups,
  getStoryGroupsByType,
} from "./stories";
export { getUnreferencedArts } from "./unreferenced";
export {
  localeNames,
  type ArtCategory,
  type ArtContext,
  type ArtDetail,
  type ArtOccurrence,
  type StoryArtReference,
  type ArtSibling,
  type UnreferencedArt,
  type GalleryDetail,
  type GalleryEntry,
  type GallerySummary,
  type ImageMetadata,
  type Locale,
  type SourceArt,
  type StoryDetail,
  type StoryGroupDetail,
  type StoryGroupSummary,
  type StoryGroupType,
  type StorySummary,
} from "./types";
export { artTransitionName, formatBytes, uniqueStoryArtReferences } from "./utils";
