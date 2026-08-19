"""Domain records shared by the updater's parsing, processing, and publication modules."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image

ArtworkCategory = Literal["illustration", "background", "item", "character"]
SourceRole = Literal["body", "face", "whole_body"]
SourceLayerKind = Literal["character", "panel"]
StoryMediaKind = Literal["sound", "music", "video"]
MediaAssetKind = Literal["audio", "video"]
ScoreAssetKind = Literal[
    "icon",
    "logo",
    "background",
    "key-visual",
    "title",
    "decoration",
    "retro-background",
    "divider",
]
LocaleUnit = Literal["CN", "EN", "JP", "KR", "TW"]
MovementType = Literal["continue", "discrete"]
SectionType = Literal["main_theme", "side_story", "vignette"]
MovementLocationType = Literal["before", "after", "divider", "story_set"]
ArchiveCategory = Literal[
    "events",
    "operator_record",
    "integrated_strategies",
    "reclamation_algorithm",
    "others",
]
ArtworkLayout = Literal["none", "vertical", "horizontal"]
StoryTag = Literal["before", "after", "interlude"]


def _png_dimensions(source: BytesIO | Path) -> tuple[int, int]:
    """Decode one PNG and return its positive dimensions."""

    try:
        with Image.open(source) as image:
            if image.format != "PNG":
                raise ValueError(f"expected PNG data, got {image.format!r}")
            image.load()
            width, height = image.size
    except (OSError, TypeError) as error:
        raise ValueError("invalid PNG data") from error
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid PNG dimensions: {width}x{height}")
    return width, height


@dataclass(frozen=True, slots=True)
class PngArtifact:
    """Represent a PNG whose encoded content is kept in memory."""

    content: bytes
    width: int
    height: int

    @classmethod
    def from_bytes(cls, content: bytes) -> PngArtifact:
        """Decode PNG bytes and retain their validated dimensions."""

        if not isinstance(content, bytes):
            raise TypeError("PNG content must be bytes")
        width, height = _png_dimensions(BytesIO(content))
        return cls(
            content=content,
            width=width,
            height=height,
        )

    @classmethod
    def from_image(cls, image: Image.Image) -> PngArtifact:
        """Encode one image as deterministic RGBA PNG data."""

        rgba = image.convert("RGBA")
        output = BytesIO()
        rgba.save(output, format="PNG", optimize=False, compress_level=9)
        return cls(
            content=output.getvalue(),
            width=rgba.width,
            height=rgba.height,
        )

    @property
    def byte_size(self) -> int:
        """Return the encoded PNG size."""

        return len(self.content)

    @property
    def path(self) -> None:
        """Return no path for an artifact whose stable representation is in memory."""
        return None


@dataclass(frozen=True, slots=True)
class FilePngArtifact:
    """Represent a validated PNG backed by a stable file and loaded only on demand."""

    path: Path
    width: int
    height: int
    byte_size: int

    @classmethod
    def from_path(cls, path: Path) -> FilePngArtifact:
        """Resolve and decode a PNG file, retaining only its path and metadata."""

        stable_path = path.resolve(strict=True)
        if not stable_path.is_file():
            raise ValueError(f"PNG path is not a file: {stable_path}")
        width, height = _png_dimensions(stable_path)
        byte_size = stable_path.stat().st_size
        if byte_size <= 0:
            raise ValueError(f"invalid PNG byte size: {byte_size}")
        return cls(
            path=stable_path,
            width=width,
            height=height,
            byte_size=byte_size,
        )

    @property
    def content(self) -> bytes:
        """Read content without retaining it on the artifact."""
        return self.path.read_bytes()


PngImage = PngArtifact | FilePngArtifact


@dataclass(frozen=True, slots=True)
class FileVideoArtifact:
    """Represent one validated video backed by a stable file."""

    path: Path
    width: int
    height: int
    byte_size: int
    frame_rate_numerator: int
    frame_rate_denominator: int
    frame_count: int
    content_type: str = "video/webm"

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        width: int,
        height: int,
        frame_rate_numerator: int,
        frame_rate_denominator: int,
        frame_count: int,
        content_type: str = "video/webm",
    ) -> FileVideoArtifact:
        """Resolve a video file and retain its validated stream metadata."""

        stable_path = path.resolve(strict=True)
        if not stable_path.is_file():
            raise ValueError(f"video path is not a file: {stable_path}")
        byte_size = stable_path.stat().st_size
        values = {
            "byte size": byte_size,
            "width": width,
            "height": height,
            "frame-rate numerator": frame_rate_numerator,
            "frame-rate denominator": frame_rate_denominator,
            "frame count": frame_count,
        }
        for name, value in values.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"invalid video {name}: {value!r}")
        if not isinstance(content_type, str) or not content_type.startswith("video/"):
            raise ValueError(f"invalid video content type: {content_type!r}")
        return cls(
            path=stable_path,
            width=width,
            height=height,
            byte_size=byte_size,
            frame_rate_numerator=frame_rate_numerator,
            frame_rate_denominator=frame_rate_denominator,
            frame_count=frame_count,
            content_type=content_type,
        )

    @property
    def content(self) -> bytes:
        """Read the video without retaining it on the artifact."""

        return self.path.read_bytes()


@dataclass(frozen=True, slots=True)
class FileAudioArtifact:
    """Represent one playable audio file backed by a stable file."""

    path: Path
    content_type: str
    byte_size: int
    duration: float | None = None
    sample_rate: int | None = None

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        content_type: str,
        duration: float | None = None,
        sample_rate: int | None = None,
    ) -> FileAudioArtifact:
        """Resolve one audio file and retain only its stable metadata."""

        stable_path = path.resolve(strict=True)
        if not stable_path.is_file():
            raise ValueError(f"audio path is not a file: {stable_path}")
        byte_size = stable_path.stat().st_size
        if byte_size <= 0:
            raise ValueError(f"invalid audio byte size: {byte_size}")
        if not isinstance(content_type, str) or not content_type:
            raise ValueError(f"invalid audio content type: {content_type!r}")
        if duration is not None and (
            not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0
        ):
            raise ValueError(f"invalid audio duration: {duration!r}")
        if sample_rate is not None and (
            not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0
        ):
            raise ValueError(f"invalid audio sample rate: {sample_rate!r}")
        return cls(
            path=stable_path,
            content_type=content_type,
            byte_size=byte_size,
            duration=float(duration) if duration is not None else None,
            sample_rate=sample_rate,
        )

    @property
    def content(self) -> bytes:
        """Read the audio without retaining it on the artifact."""

        return self.path.read_bytes()


@dataclass(frozen=True, slots=True)
class SourceLayerReference:
    """Identify one category-qualified source layer in artwork order."""

    category: ArtworkCategory
    id: str


@dataclass(frozen=True, slots=True)
class SourceLayerRecord:
    """Represent one retained character layer or gallery panel.

    ``res_version`` is the version which contributed this record. ``None``
    means the enclosing manifest's version; complete-history merges set it
    explicitly so a historical winner keeps its original object prefix.
    """

    id: str
    category: ArtworkCategory
    kind: SourceLayerKind
    image: PngImage
    character_id: str | None = None
    role: SourceRole | None = None
    variant: str | None = None
    res_version: str | None = None


@dataclass(frozen=True, slots=True)
class ArtworkRecord:
    """Represent one category-qualified final artwork and its versioned object.

    ``res_version`` follows the same origin rule as on ``SourceLayerRecord``.
    """

    id: str
    category: ArtworkCategory
    image: PngImage
    source_layer_references: tuple[SourceLayerReference, ...] = ()
    res_version: str | None = None


@dataclass(frozen=True, slots=True)
class ScoreAssetRecord:
    """Represent one localized-UI-independent Score PNG from the CN client."""

    id: str
    kind: ScoreAssetKind
    image: PngImage
    res_version: str | None = None


@dataclass(frozen=True, slots=True)
class ScoreVideoRecord:
    """Represent one muted Score background video from the CN client."""

    id: str
    video: FileVideoArtifact
    res_version: str | None = None


@dataclass(frozen=True, slots=True)
class ArtworkManifest:
    """Contain artwork produced for one upstream version.

    An incremental manifest may contain only resources changed since the active
    version. Publication overlays those records on the existing database.
    """

    upstream_version: str
    artworks: tuple[ArtworkRecord, ...]
    source_layers: tuple[SourceLayerRecord, ...]
    score_assets: tuple[ScoreAssetRecord, ...] = ()
    score_videos: tuple[ScoreVideoRecord, ...] = ()
    media: tuple[MediaRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class MediaRecord:
    """Represent one story media asset extracted from the Windows client."""

    id: str
    kind: MediaAssetKind
    artifact: FileAudioArtifact | FileVideoArtifact
    res_version: str | None = None


@dataclass(frozen=True, slots=True)
class StoryArtworkReference:
    """Describe one picture or character referenced by a story directive."""

    asset_id: str
    kind: Literal["picture", "character"]
    category: ArtworkCategory
    title: str | None = None
    subtitle: str | None = None
    names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoryMediaReference:
    """Describe one ordered sound, music, or video story reference."""

    asset_id: str
    kind: StoryMediaKind


@dataclass(frozen=True, slots=True)
class StoryRecord:
    """Represent one localized story and its ordered artwork references."""

    id: str
    collection_id: str
    tag: StoryTag
    tag_text: str
    code: str
    name: str
    info: str
    artwork_references: tuple[StoryArtworkReference, ...]
    text: str = ""
    media_references: tuple[StoryMediaReference, ...] = ()


@dataclass(frozen=True, slots=True)
class MovementLocation:
    """Represent one node in a Movement's complete location graph."""

    id: str
    position: int
    location_type: MovementLocationType
    sort_id: int
    start_time: int
    present_stage_id: str | None
    unlock_stage_id: str | None
    section_id: str | None
    divider_icon_asset_id: str | None
    divider_sub_name: str | None
    video_id: str | None


@dataclass(frozen=True, slots=True)
class Movement:
    """Represent one localized Arknights Movement from upstream ``storylines``."""

    id: str
    position: int
    movement_type: MovementType
    name: str
    icon_asset_id: str | None
    logo_asset_id: str | None
    background_asset_id: str | None
    has_video: bool
    start_time: int
    locations: tuple[MovementLocation, ...]


@dataclass(frozen=True, slots=True)
class Section:
    """Represent one Story Set and its one-to-one review-group stories."""

    id: str
    collection_id: str
    section_type: SectionType
    name: str
    review_group_id: str | None
    sort_by_year: int
    sort_within_year: int
    key_visual_asset_id: str | None
    title_asset_id: str | None
    background_asset_id: str | None
    decoration_asset_id: str | None
    retro_background_asset_id: str | None
    description: str
    has_video: bool
    stories: tuple[StoryRecord, ...]


@dataclass(frozen=True, slots=True)
class ArchiveGroup:
    """Represent one non-Score collection in the public Archives."""

    id: str
    collection_id: str
    position: int
    name: str
    archive_category: ArchiveCategory
    story_type: Literal["side_story", "vignette"] | None
    stories: tuple[StoryRecord, ...]


@dataclass(frozen=True, slots=True)
class ArtworkPanel:
    """Represent one ordered source panel in an upstream artwork layout."""

    id: str
    position: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class GalleryArtwork:
    """Represent one ordered artwork inside a Gallery Group."""

    position: int
    cg_id: str
    asset_id: str
    category: ArtworkCategory
    layout: ArtworkLayout
    panels: tuple[ArtworkPanel, ...]


@dataclass(frozen=True, slots=True)
class GalleryGroup:
    """Represent artworks sharing one Gallery Group."""

    id: str
    position: int
    name: str
    description: str
    related_story_id: str | None
    related_stage_id: str | None
    artworks: tuple[GalleryArtwork, ...]


@dataclass(frozen=True, slots=True)
class Gallery:
    """Represent one collection-owned gallery and its ordered groups."""

    id: str
    collection_id: str
    position: int
    name: str
    description: str
    location_id: str | None
    groups: tuple[GalleryGroup, ...]


@dataclass(frozen=True, slots=True)
class LocaleManifest:
    """Contain one locale's complete Score, Archive, story, and gallery data."""

    unit: LocaleUnit
    upstream_version: str
    movements: tuple[Movement, ...]
    sections: tuple[Section, ...]
    archive_groups: tuple[ArchiveGroup, ...]
    galleries: tuple[Gallery, ...]
