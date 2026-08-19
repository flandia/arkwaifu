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

export type AssetNamespace = "narrative" | "material" | "presentation";
export type AssetFormat = "image" | "video" | "audio";
export type NarrativeImageCategory = "illustration" | "background" | "item" | "character";
export type NarrativeMediaCategory = "audio" | "video";
export type PresentationImageCategory =
  | "icon"
  | "logo"
  | "background"
  | "key-visual"
  | "title"
  | "decoration"
  | "retro-background"
  | "divider";
export type PresentationAssetCategory = PresentationImageCategory | "video";

export interface AssetReference {
  namespace: AssetNamespace;
  category: string;
  id: string;
}

/** Dimensions, size, and direct object-storage URL for an image. */
export interface ImageMetadata {
  mime: "image/png";
  size: number;
  width: number;
  height: number;
  url: string;
}

/** Dimensions and playback metadata for one retained Score video. */
export interface VideoMetadata {
  mime: string;
  size: number;
  width: number;
  height: number;
  frameRate: number;
  frameCount: number;
  url: string;
}

/** One declared Score image; image is null when the referenced asset is unavailable. */
export interface ScoreImage {
  namespace: "presentation";
  category: PresentationImageCategory;
  id: string;
  image: ImageMetadata | null;
}

/** One declared Score video; video is null when the referenced asset is unavailable. */
export interface ScoreVideo {
  namespace: "presentation";
  category: "video";
  id: string;
  video: VideoMetadata | null;
}

/** A category-qualified Material Asset used by one Narrative Image Asset. */
export type MaterialReference = AssetReference & {
  namespace: "material";
  category: NarrativeImageCategory;
};

export interface NarrativeAssetBase {
  namespace: "narrative";
  category: NarrativeImageCategory | NarrativeMediaCategory;
  id: string;
  format: AssetFormat;
  mime: string;
  size: number;
  url: string;
}

/** Complete metadata for one Narrative Image Asset. */
export interface NarrativeImageAsset extends NarrativeAssetBase {
  category: NarrativeImageCategory;
  format: "image";
  mime: "image/png";
  size: number;
  url: string;
  width: number;
  height: number;
  previewUrl: string;
  materials: MaterialReference[];
}

/** Compact metadata for a Narrative Image Asset referenced by neither a story nor a gallery. */
export interface OrphanNarrativeImageAsset {
  namespace: "narrative";
  id: string;
  category: NarrativeImageCategory;
  format: "image";
  mime: "image/png";
  size: number;
  url: string;
  width: number;
  height: number;
  previewUrl: string;
}

/** Compact metadata for a Narrative Media Asset referenced by no story collection. */
export interface OrphanNarrativeMediaAsset {
  namespace: "narrative";
  id: string;
  category: NarrativeMediaCategory;
  format: NarrativeMediaCategory;
  mime: string;
  size: number;
  url: string;
}

/** Every story resource absent from the story, collection, and gallery indexes. */
export type OrphanNarrativeAsset = OrphanNarrativeImageAsset | OrphanNarrativeMediaAsset;
export type OrphanNarrativeAssets = OrphanNarrativeAsset[];

/** One retained Material Asset used by a character or Gallery Reference. */
export interface MaterialAsset {
  namespace: "material";
  id: string;
  category: NarrativeImageCategory;
  format: "image";
  mime: "image/png";
  size: number;
  url: string;
  width: number;
  height: number;
  materialType: "character" | "panel";
  characterID: string | null;
  role: "body" | "face" | "whole_body" | null;
  variant: string | null;
  reverseReferences: NarrativeImageReference[];
}

/** A category-qualified Narrative Asset Reference. */
export type NarrativeAssetReference = AssetReference & {
  namespace: "narrative";
  category: NarrativeImageCategory | NarrativeMediaCategory;
};
export type NarrativeImageReference = NarrativeAssetReference & {
  category: NarrativeImageCategory;
};
export type NarrativeMediaReference = NarrativeAssetReference & {
  category: NarrativeMediaCategory;
};

/** A related Narrative Image Asset sharing the selected asset's base identifier. */
export interface RelatedNarrativeImageAsset {
  assetID: string;
  names: string[];
  previewUrl: string;
}

export type ArchiveCategory =
  | "events"
  | "operator-record"
  | "integrated-strategies"
  | "reclamation-algorithm"
  | "others";

/** Stable public ownership for stories, galleries, and asset occurrences. */
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
      archiveCategory: ArchiveCategory;
      groupID: string;
      groupName: string;
    };

/** A Story that directly references one selected resource. */
export interface StoryOccurrence {
  parent: StoryParent;
  storyID: string;
  storyName: string;
  storyCode: string;
  storyTagText: string;
}

export type NarrativeImageOccurrence = StoryOccurrence;
export type NarrativeMediaOccurrence = StoryOccurrence;

/** A Gallery Group that directly contains the selected Artwork. */
export interface NarrativeAssetGalleryReference {
  galleryID: string;
  galleryName: string;
  galleryDescription: string;
  groupID: string;
  groupName: string;
  groupDescription: string;
  cgID: string;
}

/** Localized names, related artwork, and story occurrences for one artwork. */
export interface NarrativeImageReverseReferences {
  names: string[];
  characterVariants: RelatedNarrativeImageAsset[];
  textures: RelatedNarrativeImageAsset[];
  occurrences: NarrativeImageOccurrence[];
  galleries: NarrativeAssetGalleryReference[];
}

/** A Story Reference whose Narrative Image Asset may not be available yet. */
export interface StoryNarrativeAssetReference {
  asset: NarrativeImageReference;
  kind: "picture" | "character";
  isAnimeKV?: true;
  title?: string;
  subtitle?: string;
  names?: string[];
  previewUrl?: string;
}

/** One story sound, music track, or video reference. */
export interface StoryMediaReference {
  asset: NarrativeMediaReference;
  usage?: "sound" | "music";
  mime?: string;
  size?: number;
  url?: string;
}

/** One independently addressable video archive resource. */
export interface NarrativeVideoAsset extends NarrativeAssetBase {
  category: "video";
  format: "video";
  mime: string;
  size: number;
  duration: number | null;
  sampleRate: null;
  width: number;
  height: number;
  frameRate: number | null;
  frameCount: number | null;
  url: string;
}

/** One independently addressable audio archive resource. */
export interface NarrativeAudioAsset extends NarrativeAssetBase {
  category: "audio";
  format: "audio";
  mime: string;
  size: number;
  duration: number | null;
  sampleRate: number | null;
  width: null;
  height: null;
  frameRate: null;
  frameCount: null;
  url: string;
}

/** One independently addressable audio or video archive resource. */
export type NarrativeMediaAsset = NarrativeVideoAsset | NarrativeAudioAsset;

/** The six-category Narrative Asset discriminated union. */
export type NarrativeAsset = NarrativeImageAsset | NarrativeVideoAsset | NarrativeAudioAsset;

/** Locale-specific reverse references for one audio or video resource. */
export interface MediaReverseReferences {
  occurrences: NarrativeMediaOccurrence[];
  collections: StoryParent[];
}

interface StoryMetadata {
  id: string;
  tag: "before" | "after" | "interlude";
  tagText: string;
  code: string;
  name: string;
  info: string;
}

/** One story prepared for an owning Section or Archive Group. */
export interface StorySummary extends StoryMetadata {
  previewAssetReferences: StoryNarrativeAssetReference[];
  representativeAssetReference: StoryNarrativeAssetReference | null;
}

/** One story with its owning hierarchy and complete Narrative Image Asset list. */
export interface StoryDetail extends StoryMetadata {
  parent: StoryParent;
  text: string;
  media: StoryMediaReference[];
  imageReferences: StoryNarrativeAssetReference[];
}

export type SectionType = "main_theme" | "side_story" | "vignette";

/** One localized section in a Score Movement. */
export interface SectionSummary {
  id: string;
  name: string;
  description: string;
  type: SectionType;
  position: number;
  sortByYear: number;
  sortWithinYear: number;
  keyVisual: ScoreImage | null;
  titleImage: ScoreImage | null;
  background: ScoreImage | null;
  decoration: ScoreImage | null;
  retroBackground: ScoreImage | null;
  storyCount: number;
  openingMedia: StoryMediaReference[];
}

/** One section with its stories and aggregate media and artwork. */
export interface SectionDetail extends SectionSummary {
  activeBackgroundVideo: ScoreVideo | null;
  stories: StorySummary[];
  media: StoryMediaReference[];
  imageReferences: StoryNarrativeAssetReference[];
  gallery: GalleryDetail | null;
}

export interface MovementDivider {
  kind: "divider";
  id: string;
  position: number;
  subName: string;
  icon: ScoreImage | null;
  video: ScoreVideo | null;
}

export interface SectionItem {
  kind: "section";
  position: number;
  section: SectionSummary;
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
  items: Array<MovementDivider | SectionItem>;
}

export interface ArchiveCategorySummary {
  archiveCategory: ArchiveCategory;
  groupCount: number;
}

/** One non-Score Story Group owned by an Archive Category. */
export interface ArchiveGroupSummary {
  id: string;
  name: string;
  archiveCategory: ArchiveCategory;
  type:
    | "side_story"
    | "vignette"
    | "operator_record"
    | "integrated_strategies"
    | "reclamation_algorithm"
    | "others";
  representativeAssetReference: StoryNarrativeAssetReference | null;
  previewAssetReferences: StoryNarrativeAssetReference[];
}

export interface ArchiveGroupDetail extends ArchiveGroupSummary {
  stories: StorySummary[];
  media: StoryMediaReference[];
  imageReferences: StoryNarrativeAssetReference[];
  openingMedia: StoryMediaReference[];
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
  previewUrls: string[];
}

/** One ordered Gallery Reference in a Gallery Group. */
export interface GalleryReference {
  cgID: string;
  asset: NarrativeImageReference;
  previewUrl: string | null;
}

/** One Gallery Group and its ordered Gallery References. */
export interface GalleryGroup {
  id: string;
  position: number;
  name: string;
  description: string;
  relatedStoryID: string | null;
  relatedStageID: string | null;
  references: GalleryReference[];
}

/** One Gallery with its complete Gallery Group hierarchy. */
export interface GalleryDetail extends GalleryMetadata {
  groups: GalleryGroup[];
}

export type SearchResultKind =
  | "story"
  | "movement"
  | "section"
  | "archive_group"
  | "gallery"
  | "narrative_asset";

/** One ranked result from the locale-scoped metadata search. */
export interface SearchResult {
  kind: SearchResultKind;
  id: string;
  category: NarrativeImageCategory | null;
  title: string;
  subtitle: string | null;
  previewUrl: string | null;
  parent: StoryParent | null;
}

export interface PresentationAssetSummary extends AssetReference {
  namespace: "presentation";
  category: PresentationAssetCategory;
  format: "image" | "video";
  mime: string;
  size: number;
  width: number | null;
  height: number | null;
  duration: number | null;
  referenceCount: number;
  previewUrl: string | null;
}

export interface PresentationReverseReference {
  ownerType: "movement" | "section" | "movement-divider";
  ownerID: string;
  movementID: string;
  role:
    | "icon"
    | "logo"
    | "background"
    | "key-visual"
    | "title"
    | "decoration"
    | "retro-background"
    | "video";
  name: string;
}

export interface PresentationAssetDetail extends Omit<PresentationAssetSummary, "previewUrl"> {
  url: string;
  frameRate: number | null;
  frameCount: number | null;
  reverseReferences: PresentationReverseReference[];
}
