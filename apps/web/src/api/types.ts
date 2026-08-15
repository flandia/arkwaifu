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

/** Dimensions, size, and direct object-storage URL for an image. */
export interface ImageMetadata {
  byteSize: number;
  width: number;
  height: number;
  contentUrl: string;
}

/** Dimensions and playback metadata for one retained Score video. */
export interface VideoMetadata {
  byteSize: number;
  width: number;
  height: number;
  frameRate: number;
  frameCount: number;
  contentUrl: string;
}

/** One declared Score image; image is null when the referenced asset is unavailable. */
export interface ScoreImage {
  id: string;
  image: ImageMetadata | null;
}

/** One declared Score video; video is null when the referenced asset is unavailable. */
export interface ScoreVideo {
  id: string;
  video: VideoMetadata | null;
}

/** A category-qualified source used by one composed artwork. */
export interface SourceArtReference {
  category: ArtCategory;
  id: string;
}

/** Complete metadata for one composed artwork. */
export interface ArtDetail {
  id: string;
  category: ArtCategory;
  thumbnailContentUrl: string;
  image: ImageMetadata;
  sourceArts: SourceArtReference[];
}

/** Compact metadata for artwork referenced by neither a story nor a gallery. */
export interface UnreferencedArt {
  id: string;
  category: ArtCategory;
  thumbnailContentUrl: string;
}

/** One retained source image used by a character or CG composition. */
export interface SourceArt {
  id: string;
  category: ArtCategory;
  kind: "character" | "composite_panel";
  characterID: string | null;
  role: "body" | "face" | "whole_body" | null;
  variant: string | null;
  image: ImageMetadata;
}

/** Related character artwork that shares the selected artwork's base identifier. */
export interface ArtSibling {
  artID: string;
  names: string[];
  thumbnailContentUrl: string;
}

export type ArchiveKind =
  | "events"
  | "operator-record"
  | "integrated-strategies"
  | "reclamation-algorithm"
  | "others";

/** Stable public ownership for stories, galleries, and artwork occurrences. */
export type StoryParent =
  | {
      kind: "score";
      movementID: string;
      movementName: string;
      sectionID: string;
      sectionName: string;
    }
  | {
      kind: "archive";
      archiveKind: ArchiveKind;
      groupID: string;
      groupName: string;
    };

/** A story occurrence of the selected artwork. */
export interface ArtOccurrence {
  parent: StoryParent;
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
  thumbnailContentUrl: string | null;
}

interface StoryMetadata {
  id: string;
  tag: "before" | "after" | "interlude";
  tagText: string;
  code: string;
  name: string;
  info: string;
}

/** One story prepared for an owning Score section or Archive group. */
export interface StorySummary extends StoryMetadata {
  previewArtReferences: StoryArtReference[];
  representativeArtReference: StoryArtReference | null;
}

/** One story with its owning hierarchy and complete artwork list. */
export interface StoryDetail extends StoryMetadata {
  parent: StoryParent;
  artReferences: StoryArtReference[];
}

export type ScoreSectionType = "main_theme" | "side_story" | "vignette";

/** One localized section in a Score Movement. */
export interface ScoreSectionSummary {
  id: string;
  name: string;
  description: string;
  type: ScoreSectionType;
  position: number;
  sortByYear: number;
  sortWithinYear: number;
  keyVisual: ScoreImage | null;
  titleImage: ScoreImage | null;
  background: ScoreImage | null;
  decoration: ScoreImage | null;
  retroBackground: ScoreImage | null;
  storyCount: number;
}

/** One section with its stories and aggregate artwork. */
export interface ScoreSectionDetail extends ScoreSectionSummary {
  activeBackgroundVideo: ScoreVideo | null;
  stories: StorySummary[];
  artReferences: StoryArtReference[];
  gallery: GalleryDetail | null;
}

export interface ScoreSplit {
  kind: "split";
  id: string;
  position: number;
  subName: string;
  icon: ScoreImage | null;
  video: ScoreVideo | null;
}

export interface ScoreSectionItem {
  kind: "section";
  position: number;
  section: ScoreSectionSummary;
}

/** One top-level Arknights Movement from the upstream `storylines` catalog. */
export interface MovementSummary {
  id: string;
  name: string;
  type: "continue" | "discrete";
  position: number;
  sectionCount: number;
  startTime: number;
  icon: ScoreImage | null;
  logo: ScoreImage | null;
  background: ScoreImage | null;
  backgroundVideo: ScoreVideo | null;
}

export interface MovementDetail extends MovementSummary {
  items: Array<ScoreSplit | ScoreSectionItem>;
}

export interface ArchiveKindSummary {
  kind: ArchiveKind;
  groupCount: number;
}

/** One non-Score story group owned by an Archive kind. */
export interface ArchiveGroupSummary {
  id: string;
  name: string;
  kind: ArchiveKind;
  type:
    | "side_story"
    | "vignette"
    | "operator_record"
    | "integrated_strategies"
    | "reclamation_algorithm"
    | "others";
  representativeArtReference: StoryArtReference | null;
  previewArtReferences: StoryArtReference[];
}

export interface ArchiveGroupDetail extends ArchiveGroupSummary {
  stories: StorySummary[];
  artReferences: StoryArtReference[];
  gallery: GalleryDetail | null;
}

interface GalleryMetadata {
  id: string;
  name: string;
  description: string;
  parent: StoryParent;
}

/** One gallery prepared for the global index. */
export interface GallerySummary extends GalleryMetadata {
  previewThumbnailContentUrls: string[];
}

/** One ordered logical artwork in a gallery display. */
export interface GalleryDisplayArtwork {
  position: number;
  cgID: string;
  artID: string;
  category: ArtCategory;
  thumbnailContentUrl: string | null;
}

/** One gallery display and its ordered sibling artworks. */
export interface GalleryDisplay {
  id: string;
  position: number;
  name: string;
  description: string;
  relatedStoryID: string | null;
  relatedStageID: string | null;
  artworks: GalleryDisplayArtwork[];
}

/** One gallery with its complete display hierarchy. */
export interface GalleryDetail extends GalleryMetadata {
  displays: GalleryDisplay[];
}
