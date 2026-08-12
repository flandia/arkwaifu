export const localeNames = {
  CN: "简体中文",
  EN: "English",
  JP: "日本語",
  KR: "한국어",
  TW: "繁體中文",
} as const;

export type Locale = keyof typeof localeNames;
export type ArtCategory = "image" | "background" | "item" | "character";
export type StoryGroupType =
  | "main_story"
  | "major_event"
  | "minor_event"
  | "operator_record"
  | "integrated_strategies"
  | "reclamation_algorithm"
  | "others";

export interface ImageMetadata {
  byteSize: number;
  width: number;
  height: number;
  contentUrl: string;
}

export interface Art {
  id: string;
  category: ArtCategory;
  thumbnailContentUrl?: string;
  image: ImageMetadata;
  sourceArtIDs: string[];
}

export interface ArtSummary {
  id: string;
  category: ArtCategory;
  thumbnailContentUrl: string;
}

export interface SourceArt {
  id: string;
  characterID: string;
  role: "body" | "face" | "whole_body";
  variant: string;
  image: ImageMetadata;
}

export interface ArtSibling {
  artID: string;
  names: string[];
  thumbnailContentUrl: string;
}

export interface ArtOccurrence {
  groupID: string;
  groupName: string;
  groupType: StoryGroupType;
  storyID: string;
  storyName: string;
  storyCode: string;
  storyTagText: string;
}

export interface ArtContext {
  names: string[];
  siblings: ArtSibling[];
  occurrences: ArtOccurrence[];
}

export interface ArtReference {
  artID: string;
  kind: "picture" | "character";
  category: ArtCategory;
  title: string | null;
  subtitle: string | null;
  names: string[];
  thumbnailContentUrl?: string | null;
}

export interface Story {
  id: string;
  groupID: string;
  tag: "before" | "after" | "interlude";
  tagText: string;
  code: string;
  name: string;
  info: string;
  artReferences: ArtReference[];
  previewArtReferences?: ArtReference[];
  representativeArtReference?: ArtReference | null;
}

export interface StoryGroup {
  id: string;
  name: string;
  type: StoryGroupType;
  previewArtReferences?: ArtReference[];
  representativeArtReference: ArtReference | null;
}

export interface StoryGroupDetail extends StoryGroup {
  artReferences: ArtReference[];
}

interface GalleryMetadata {
  id: string;
  name: string;
  description: string;
}

export interface GallerySummary extends GalleryMetadata {
  previewThumbnailContentUrls: string[];
}

export interface GalleryEntry {
  id: string;
  position: number;
  name: string;
  description: string;
  artID: string;
  category: ArtCategory;
  thumbnailContentUrl?: string | null;
}

export interface Gallery extends GalleryMetadata {
  entries: GalleryEntry[];
}
