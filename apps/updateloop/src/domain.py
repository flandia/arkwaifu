"""Domain records shared by the updater's parsing, processing, and publication modules."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image

ArtCategory = Literal["image", "background", "item", "character"]
SourceRole = Literal["body", "face", "whole_body"]
LocaleUnit = Literal["CN", "EN", "JP", "KR", "TW"]
StoryGroupType = Literal["main_story", "major_event", "minor_event", "other"]
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
class SourceArtRecord:
    """Represent one retained body, face, or whole-body image of a character."""

    id: str
    character_id: str
    role: SourceRole
    variant: str
    image: PngImage


@dataclass(frozen=True, slots=True)
class ArtRecord:
    """Represent one final picture or character composition served to users."""

    id: str
    category: ArtCategory
    image: PngImage
    source_art_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArtManifest:
    """Contain art produced for one upstream version.

    An incremental manifest may contain only resources changed since the active
    version. Publication overlays those records on the existing database.
    """

    upstream_version: str
    arts: tuple[ArtRecord, ...]
    source_arts: tuple[SourceArtRecord, ...]


@dataclass(frozen=True, slots=True)
class StoryArtReference:
    """Describe one picture or character referenced by a story directive."""

    art_id: str
    kind: Literal["picture", "character"]
    category: ArtCategory
    title: str | None = None
    subtitle: str | None = None
    names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoryRecord:
    """Represent one localized story and its ordered art references."""

    id: str
    group_id: str
    tag: StoryTag
    tag_text: str
    code: str
    name: str
    info: str
    art_references: tuple[StoryArtReference, ...]


@dataclass(frozen=True, slots=True)
class StoryGroupRecord:
    """Represent one ordered group of localized stories."""

    id: str
    name: str
    group_type: StoryGroupType
    stories: tuple[StoryRecord, ...]


@dataclass(frozen=True, slots=True)
class GalleryEntry:
    """Represent one ordered art entry in a gallery."""

    id: str
    position: int
    name: str
    description: str
    art_id: str


@dataclass(frozen=True, slots=True)
class Gallery:
    """Represent one localized gallery and all of its entries."""

    id: str
    name: str
    description: str
    entries: tuple[GalleryEntry, ...]


@dataclass(frozen=True, slots=True)
class LocaleManifest:
    """Contain the complete story and gallery dataset for one server version."""

    unit: LocaleUnit
    upstream_version: str
    story_groups: tuple[StoryGroupRecord, ...]
    galleries: tuple[Gallery, ...]
