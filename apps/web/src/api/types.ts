/** Display names for every archive locale exposed by the service. */
export const localeNames = {
  CN: "简体中文",
  EN: "English",
  JP: "日本語",
  KR: "한국어",
  TW: "繁體中文",
} as const;

/** A locale with story and gallery metadata. */
export type Locale = keyof typeof localeNames;

/** A storage and routing category for composed artwork. */
export type ArtCategory = "image" | "background" | "item" | "character";

/** A navigation category for story groups. */
export type StoryGroupType =
  | "main_story"
  | "major_event"
  | "minor_event"
  | "operator_record"
  | "integrated_strategies"
  | "reclamation_algorithm"
  | "others";

/** Dimensions, size, and direct object-storage uniform resource locator (URL) for an image. */
export interface ImageMetadata {
  byteSize: number;
  width: number;
  height: number;
  contentUrl: string;
}

/** Complete metadata for one composed artwork. */
export interface ArtDetail {
  id: string;
  category: ArtCategory;
  thumbnailContentUrl: string;
  image: ImageMetadata;
  sourceArtIDs: string[];
}

/** Compact metadata for artwork referenced by neither a story nor a gallery. */
export interface UnreferencedArt {
  id: string;
  category: ArtCategory;
  thumbnailContentUrl: string;
}

/** One original image layer used to create composed character artwork. */
export interface SourceArt {
  id: string;
  characterID: string;
  role: "body" | "face" | "whole_body";
  variant: string;
  image: ImageMetadata;
}

/** Related character artwork that shares the selected artwork’s base identifier. */
export interface ArtSibling {
  artID: string;
  names: string[];
  thumbnailContentUrl: string;
}

/** A story occurrence of the selected artwork. */
export interface ArtOccurrence {
  groupID: string;
  groupName: string;
  groupType: StoryGroupType;
  storyID: string;
  storyName: string;
  storyCode: string;
  storyTagText: string;
}

/** Localized names, related artwork, and story occurrences for one artwork. */
export interface ArtContext {
  names: string[];
  siblings: ArtSibling[];
  occurrences: ArtOccurrence[];
}

/** A story artwork reference whose artwork may not be available yet. */
export interface StoryArtReference {
  artID: string;
  kind: "picture" | "character";
  category: ArtCategory;
  title: string | null;
  subtitle: string | null;
  names: string[];
  /** Always present. A null value means the referenced artwork is unavailable. */
  thumbnailContentUrl: string | null;
}

interface StoryMetadata {
  id: string;
  groupID: string;
  tag: "before" | "after" | "interlude";
  tagText: string;
  code: string;
  name: string;
  info: string;
}

/** One story with its complete ordered artwork-reference list. */
export interface StoryDetail extends StoryMetadata {
  artReferences: StoryArtReference[];
}

/** One story prepared for a group listing. */
export interface StorySummary extends StoryMetadata {
  /** Preserved for response compatibility. Story summaries always return an empty list. */
  artReferences: [];
  previewArtReferences: StoryArtReference[];
  /** Always present. A null value means no preview artwork is available. */
  representativeArtReference: StoryArtReference | null;
}

/** One story group prepared for an index listing. */
export interface StoryGroupSummary {
  id: string;
  name: string;
  type: StoryGroupType;
  previewArtReferences: StoryArtReference[];
  /** Always present. A null value means no preview artwork is available. */
  representativeArtReference: StoryArtReference | null;
}

/** One story group with the artwork referenced by all of its stories. */
export interface StoryGroupDetail extends StoryGroupSummary {
  artReferences: StoryArtReference[];
}

interface GalleryMetadata {
  id: string;
  name: string;
  description: string;
}

/** One gallery prepared for an index listing. */
export interface GallerySummary extends GalleryMetadata {
  previewThumbnailContentUrls: string[];
}

/** One ordered gallery entry and its optional artwork thumbnail. */
export interface GalleryEntry {
  id: string;
  position: number;
  name: string;
  description: string;
  artID: string;
  category: ArtCategory;
  /** Always present. A null value means the referenced artwork is unavailable. */
  thumbnailContentUrl: string | null;
}

/** One gallery with its complete ordered entry list. */
export interface GalleryDetail extends GalleryMetadata {
  entries: GalleryEntry[];
}
