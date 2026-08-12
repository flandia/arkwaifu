"""Process extracted art into the records stored by Arkwaifu.

The term ``process`` here refers to merging color and alpha channels, merging
the face variations onto their corresponding character bodies (合并差分), and
encoding the resulting images as PNG.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PIL import Image

from ..domain import (
    ArtCategory,
    ArtManifest,
    ArtRecord,
    FilePngArtifact,
    PngArtifact,
    PngImage,
    SourceArtRecord,
    SourceRole,
)

_AVG_ROOT = Path("assets/torappu/dynamicassets/avg")
_LOGGER = logging.getLogger(__name__)
_PICTURE_CATEGORIES = {
    "images": "image",
    "backgrounds": "background",
    "items": "item",
}
_ART_CATEGORIES = frozenset({"image", "background", "item", "character"})
_SOURCE_ROLES = frozenset({"body", "face", "whole_body"})
_IMAGE_PATH_FIELD = "image_path"


@dataclass(frozen=True, slots=True)
class _Sprite:
    """Describe one sprite and the metadata needed to render it."""

    filename: str | None
    alpha_filename: str | None
    whole_body: bool
    pixels_to_units: float


@dataclass(frozen=True, slots=True)
class _Body:
    """Describe one body variation and its corresponding face variations."""

    sprite: _Sprite | None
    faces: tuple[_Sprite, ...]
    face_rectangle: tuple[int, int, int, int]


def _rounded(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path}: {error}") from error


def _logical_image(directory: Path, sprite: _Sprite) -> Image.Image | None:
    """Decode a sprite and merge its separate alpha texture, when present."""

    if not sprite.filename:
        return None
    color_path = directory / sprite.filename
    if not color_path.is_file():
        raise ValueError(f"missing color sprite: {color_path}")
    with Image.open(color_path) as opened:
        color = opened.convert("RGBA")

    if not sprite.alpha_filename:
        return color
    alpha_path = directory / sprite.alpha_filename
    if not alpha_path.is_file():
        raise ValueError(f"missing alpha sprite: {alpha_path}")
    with Image.open(alpha_path) as opened:
        alpha = opened.convert("L")
    if alpha.size != color.size:
        alpha = alpha.resize(color.size, Image.Resampling.LANCZOS)
    color.putalpha(alpha)
    return color


def _resize_for_units(image: Image.Image, pixels_to_units: float) -> Image.Image:
    """Scale a Unity image from units to pixels by dividing its dimensions."""

    if pixels_to_units <= 0:
        raise ValueError(f"pixels-to-units must be positive, got {pixels_to_units}")
    if pixels_to_units == 1.0:
        return image.copy()
    width = _rounded(image.width / pixels_to_units)
    height = _rounded(image.height / pixels_to_units)
    if width <= 0 or height <= 0:
        raise ValueError(f"pixels-to-units produced invalid dimensions: {width}x{height}")
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _sprite_from_raw(raw: dict, path_ids: dict[int, str], pixels: dict[int, float]) -> _Sprite:
    sprite_id = int(raw.get("sprite", {}).get("m_PathID", 0))
    alpha_id = int(raw.get("alphaTex", {}).get("m_PathID", 0))
    return _Sprite(
        filename=path_ids.get(sprite_id),
        alpha_filename=path_ids.get(alpha_id),
        whole_body=bool(raw.get("isWholeBody", 0)),
        pixels_to_units=pixels.get(sprite_id, 100.0) / 100.0,
    )


def _scan_character(directory: Path) -> tuple[_Body, ...]:
    """Scan one extracted character sprite hub into body variations."""

    group_path = directory / "AVGCharacterSpriteHubGroup.json"
    hub_path = directory / "AVGCharacterSpriteHub.json"
    if group_path.is_file() == hub_path.is_file():
        raise ValueError(f"character {directory.name} must contain exactly one sprite hub")

    hub_document = _read_json(group_path if group_path.is_file() else hub_path)
    hubs = hub_document.get("spriteGroups", []) if group_path.is_file() else [hub_document]
    path_ids = {
        int(key): value
        for key, value in _read_json(directory.parent / f"{directory.name}.json").items()
    }
    tree_names = {
        int(key): value
        for key, value in _read_json(directory.parent / f"{directory.name}.typetree.json").items()
    }
    pixels: dict[int, float] = {}
    for path_id, filename in tree_names.items():
        tree = _read_json(directory / filename)
        pixels[path_id] = float(tree.get("m_PixelsToUnits", 100.0))

    result: list[_Body] = []
    for hub in hubs:
        raw_sprites = list(hub.get("sprites", []))
        face_position = hub.get("FacePos", hub.get("facePos", {}))
        face_size = hub.get("FaceSize", hub.get("faceSize", {}))
        x = float(face_position.get("x", -1))
        y = float(face_position.get("y", -1))
        width = float(face_size.get("x", 0))
        height = float(face_size.get("y", 0))
        rectangle = (_rounded(x), _rounded(y), _rounded(x + width), _rounded(y + height))
        sprites = [_sprite_from_raw(sprite, path_ids, pixels) for sprite in raw_sprites]
        if x >= 0 and y >= 0:
            # A valid face position means the last variation is the body.
            # Otherwise, every variation contains the whole body.
            if not sprites:
                raise ValueError(f"character {directory.name} has a body hub without sprites")
            body = sprites.pop()
            result.append(_Body(sprite=body, faces=tuple(sprites), face_rectangle=rectangle))
        else:
            whole_bodies = tuple(
                _Sprite(
                    filename=sprite.filename,
                    alpha_filename=sprite.alpha_filename,
                    whole_body=True,
                    pixels_to_units=sprite.pixels_to_units,
                )
                for sprite in sprites
            )
            result.append(_Body(sprite=None, faces=whole_bodies, face_rectangle=rectangle))
    return tuple(result)


def _picture_records(extracted_root: Path) -> list[ArtRecord]:
    """Read picture arts, which need no processing beyond PNG validation."""

    records: list[ArtRecord] = []
    for subdirectory, category in _PICTURE_CATEGORIES.items():
        directory = extracted_root / _AVG_ROOT / subdirectory
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.png")):
            art_id = path.stem.lower()
            records.append(
                ArtRecord(
                    id=art_id, category=category, image=PngArtifact.from_bytes(path.read_bytes())
                )
            )
    return records


def _character_records(extracted_root: Path) -> tuple[list[ArtRecord], list[SourceArtRecord]]:
    """Process character sources and compose every available variation.

    The operation consists of decoding the color and alpha images, merging the
    alpha channels, and then merging each face onto its corresponding body.
    Face variations that require a missing body image are skipped; upstream
    data can contain such references even though there is nothing useful to
    compose. Whole-body variations remain independently renderable.
    """

    character_root = extracted_root / _AVG_ROOT / "characters"
    arts: list[ArtRecord] = []
    sources: dict[str, SourceArtRecord] = {}
    if not character_root.is_dir():
        return arts, []

    for directory in sorted(path for path in character_root.iterdir() if path.is_dir()):
        character_id = directory.stem.lower()
        for body_index, body in enumerate(_scan_character(directory), start=1):
            body_image = _logical_image(directory, body.sprite) if body.sprite else None
            body_source_id: str | None = None
            resized_body: Image.Image | None = None
            if body.sprite and body_image is not None:
                body_source_id = f"{character_id}:body:{body_index}"
                sources[body_source_id] = SourceArtRecord(
                    id=body_source_id,
                    character_id=character_id,
                    role="body",
                    variant=str(body_index),
                    image=PngArtifact.from_image(body_image),
                )
                resized_body = _resize_for_units(body_image, body.sprite.pixels_to_units)

            for face_index, face in enumerate(body.faces, start=1):
                face_image = _logical_image(directory, face)
                if face_image is None:
                    continue
                role = "whole_body" if face.whole_body else "face"
                source_id = f"{character_id}:{role}:{body_index}:{face_index}"
                sources[source_id] = SourceArtRecord(
                    id=source_id,
                    character_id=character_id,
                    role=role,
                    variant=f"{body_index}:{face_index}",
                    image=PngArtifact.from_image(face_image),
                )
                resized_face = _resize_for_units(face_image, face.pixels_to_units)

                if face.whole_body:
                    output = resized_face
                    source_ids = (source_id,)
                else:
                    if resized_body is None or body_source_id is None:
                        continue
                    left, top, right, bottom = body.face_rectangle
                    if (
                        left < 0
                        or top < 0
                        or right > resized_body.width
                        or bottom > resized_body.height
                    ):
                        raise ValueError(
                            f"face rectangle {body.face_rectangle} is outside "
                            f"{character_id} body {resized_body.size}"
                        )
                    resized_face = resized_face.resize(
                        (right - left, bottom - top), Image.Resampling.LANCZOS
                    )
                    output = resized_body.copy()
                    output.alpha_composite(resized_face, (left, top))
                    source_ids = (body_source_id, source_id)

                arts.append(
                    ArtRecord(
                        id=f"{character_id}#{face_index}${body_index}",
                        category="character",
                        image=PngArtifact.from_image(output),
                        source_art_ids=source_ids,
                    )
                )
    return arts, list(sources.values())


def _deduplicate_arts(records: tuple[ArtRecord, ...]) -> tuple[ArtRecord, ...]:
    """Keep the final record for each category-qualified art identity."""

    by_identity: dict[tuple[str, str], ArtRecord] = {}
    for record in records:
        identity = (record.category, record.id)
        previous = by_identity.get(identity)
        if previous is not None:
            _LOGGER.warning(
                "duplicate art identity; keeping later bundle category=%s art_id=%s",
                record.category,
                record.id,
            )
        by_identity[identity] = record
    return tuple(by_identity.values())


def build_art_manifest(extracted_root: Path, upstream_version: str) -> ArtManifest:
    """Scan and process one extracted art delta into a manifest."""
    pictures = _picture_records(extracted_root)
    characters, sources = _character_records(extracted_root)
    return ArtManifest(
        upstream_version=upstream_version,
        arts=tuple(
            sorted(
                _deduplicate_arts((*pictures, *characters)),
                key=lambda record: (record.category, record.id),
            )
        ),
        source_arts=tuple(sorted(sources, key=lambda record: record.id)),
    )


def merge_art_manifests(
    manifests: Sequence[ArtManifest],
    upstream_version: str,
) -> ArtManifest:
    """Merge independently processed bundles by category-qualified identity."""
    if not isinstance(upstream_version, str) or not upstream_version:
        raise ValueError("upstream version cannot be empty")
    for manifest in manifests:
        if not isinstance(manifest, ArtManifest):
            raise TypeError(f"invalid art manifest: {manifest!r}")
        if manifest.upstream_version != upstream_version:
            raise ValueError("cannot merge art manifests from different upstream versions")

    arts = tuple(art for manifest in manifests for art in manifest.arts)
    sources: dict[str, SourceArtRecord] = {}
    for manifest in manifests:
        for source in manifest.source_arts:
            sources[source.id] = source
    return ArtManifest(
        upstream_version=upstream_version,
        arts=tuple(sorted(_deduplicate_arts(arts), key=lambda art: (art.category, art.id))),
        source_arts=tuple(sorted(sources.values(), key=lambda source: source.id)),
    )


def write_art_manifest(manifest: ArtManifest, destination: Path) -> None:
    """Persist one cache manifest and its ordinal PNG files.

    Ordinal names keep the cache layout independent from upstream identifiers;
    ``manifest.json`` is the only index and is written after all images. A
    rendered cache entry belongs to exactly one upstream version, so record
    origins inherit ``upstream_version`` instead of being repeated per record.
    """
    processed = destination / "processed"
    processed.mkdir(parents=True, exist_ok=True)

    next_image_index = 0

    def persist_image(artifact: PngImage) -> str:
        nonlocal next_image_index
        relative = _cached_image_path(next_image_index)
        next_image_index += 1
        output = destination / Path(relative)
        if artifact.path is None:
            output.write_bytes(artifact.content)
        elif artifact.path != output.resolve():
            shutil.copyfile(artifact.path, output)
        return relative

    payload = {
        "upstream_version": manifest.upstream_version,
        "arts": [
            {
                "id": art.id,
                "category": art.category,
                _IMAGE_PATH_FIELD: persist_image(art.image),
                "source_art_ids": list(art.source_art_ids),
            }
            for art in manifest.arts
        ],
        "source_arts": [
            {
                "id": source.id,
                "character_id": source.character_id,
                "role": source.role,
                "variant": source.variant,
                _IMAGE_PATH_FIELD: persist_image(source.image),
            }
            for source in manifest.source_arts
        ],
    }
    (destination / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _required_field(record: dict[str, object], name: str, context: str) -> object:
    if name not in record:
        raise ValueError(f"cached {context} is missing {name!r}")
    return record[name]


def _required_string(record: dict[str, object], name: str, context: str) -> str:
    value = _required_field(record, name, context)
    if not isinstance(value, str) or not value:
        raise ValueError(f"cached {context} has an invalid {name}: {value!r}")
    return value


def _required_records(payload: dict[str, object], name: str, source: Path) -> list[object]:
    value = _required_field(payload, name, "art manifest")
    if not isinstance(value, list):
        raise TypeError(f"cached art manifest has an invalid {name}: {source}")
    return value


def _cached_image_path(index: int) -> str:
    return f"processed/{index:08d}.png"


def _cached_identifier(record: dict[str, object], name: str, context: str) -> str:
    value = _required_string(record, name, context)
    if value != value.lower():
        raise ValueError(f"cached {context} has an invalid {name}: {value!r}")
    return value


def _read_art_manifest(source: Path) -> ArtManifest:
    """Read one rendered cache entry without translating malformed data."""

    payload = _read_json(source / "manifest.json")
    if not isinstance(payload, dict):
        raise TypeError(f"cached art manifest is not an object: {source}")

    version = _required_string(payload, "upstream_version", "art manifest")
    raw_arts = _required_records(payload, "arts", source)
    raw_sources = _required_records(payload, "source_arts", source)
    next_image_index = 0

    def artifact(record: dict[str, object], context: str) -> FilePngArtifact:
        nonlocal next_image_index
        expected = _cached_image_path(next_image_index)
        next_image_index += 1
        relative = _required_string(record, _IMAGE_PATH_FIELD, context)
        if relative != expected:
            raise ValueError(
                f"cached {context} has an invalid {_IMAGE_PATH_FIELD}: "
                f"{relative!r}, expected {expected!r}"
            )
        path = source / Path(expected)
        try:
            return FilePngArtifact.from_path(path)
        except (OSError, TypeError, ValueError) as error:
            raise ValueError(f"cannot read cached art image {path}: {error}") from error

    arts: list[ArtRecord] = []
    for index, value in enumerate(raw_arts):
        context = f"art record {index}"
        if not isinstance(value, dict):
            raise TypeError(f"cached {context} is not an object: {value!r}")
        category = _required_string(value, "category", context)
        if category not in _ART_CATEGORIES:
            raise ValueError(f"cached {context} has an invalid category: {category!r}")
        raw_source_ids = _required_field(value, "source_art_ids", context)
        if not isinstance(raw_source_ids, list) or not all(
            isinstance(source_id, str) and source_id for source_id in raw_source_ids
        ):
            raise ValueError(f"cached {context} has invalid source-art references")
        arts.append(
            ArtRecord(
                id=_cached_identifier(value, "id", context),
                category=cast(ArtCategory, category),
                image=artifact(value, context),
                source_art_ids=tuple(raw_source_ids),
            )
        )

    sources: list[SourceArtRecord] = []
    for index, value in enumerate(raw_sources):
        context = f"source-art record {index}"
        if not isinstance(value, dict):
            raise TypeError(f"cached {context} is not an object: {value!r}")
        role = _required_string(value, "role", context)
        if role not in _SOURCE_ROLES:
            raise ValueError(f"cached {context} has an invalid role: {role!r}")
        sources.append(
            SourceArtRecord(
                id=_cached_identifier(value, "id", context),
                character_id=_cached_identifier(value, "character_id", context),
                role=cast(SourceRole, role),
                variant=_required_string(value, "variant", context),
                image=artifact(value, context),
            )
        )

    manifest = ArtManifest(version, tuple(arts), tuple(sources))
    _validate_cached_relationships(manifest)
    return manifest


def _validate_cached_relationships(manifest: ArtManifest) -> None:
    """Check relationships owned by the cache format rather than upstream data."""

    art_ids = [(art.category, art.id) for art in manifest.arts]
    source_ids = [source.id for source in manifest.source_arts]
    if len(art_ids) != len(set(art_ids)):
        raise ValueError("cached art identities are not unique")
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("cached source-art identifiers are not unique")

    available_sources = set(source_ids)
    for art in manifest.arts:
        if not isinstance(art.source_art_ids, tuple) or len(art.source_art_ids) != len(
            set(art.source_art_ids)
        ):
            raise ValueError(f"cached art {art.id} repeats a source-art reference")
        for source_id in art.source_art_ids:
            if source_id != source_id.lower():
                raise ValueError(f"cached art {art.id} has an invalid source-art reference")
        missing = set(art.source_art_ids) - available_sources
        if missing:
            raise ValueError(f"cached art {art.id} references missing sources: {sorted(missing)}")


def read_art_manifest(source: Path) -> ArtManifest:
    """Load a cached manifest and decode every referenced PNG.

    This validates the updater's cache format and source-art relationships. It
    deliberately does not impose additional assumptions on the upstream schema.
    """
    try:
        return _read_art_manifest(source)
    except ValueError:
        raise
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"cached art manifest is malformed: {source}: {error}") from error
