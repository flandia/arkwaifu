"""Process extracted artwork into the records stored by Arkwaifu.

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
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from PIL import Image

from ..domain import (
    ArtworkCategory,
    ArtworkManifest,
    ArtworkRecord,
    FileAudioArtifact,
    FilePngArtifact,
    FileVideoArtifact,
    GalleryArtwork,
    MediaRecord,
    PngArtifact,
    PngImage,
    ScoreAssetKind,
    ScoreAssetRecord,
    ScoreVideoRecord,
    SourceLayerRecord,
    SourceLayerReference,
    SourceRole,
)

_AVG_ROOT = Path("assets/torappu/dynamicassets/avg")
_AUDIO_ROOT = Path("assets/torappu/dynamicassets/audio")
_MIXSTORY_ROOT = Path("assets/torappu/dynamicassets/arts/ui/mixstory")
_LOGGER = logging.getLogger(__name__)
_PICTURE_CATEGORIES = {
    "images": "illustration",
    "backgrounds": "background",
    "items": "item",
}
_ARTWORK_CATEGORIES = frozenset({"illustration", "background", "item", "character"})
_SOURCE_ROLES = frozenset({"body", "face", "whole_body"})
_SOURCE_KINDS = frozenset({"character", "panel"})
_SCORE_ASSET_DIRECTORIES = {
    "abbrs": "icon",
    "logos": "logo",
    "backgrounds": "background",
    "kvs": "key-visual",
    "titles": "title",
    "decos": "decoration",
    "retrobkgs": "retro-background",
    "splits": "divider",
}
_SCORE_ASSET_KINDS = frozenset(_SCORE_ASSET_DIRECTORIES.values())
_IMAGE_PATH_FIELD = "image_path"
_VIDEO_PATH_FIELD = "video_path"
_MEDIA_PATH_FIELD = "media_path"
_VIDEO_CONTENT_TYPES = {
    ".m4v": "video/x-m4v",
    ".mov": "video/quicktime",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


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


def _picture_records(extracted_root: Path) -> list[ArtworkRecord]:
    """Read picture artworks, which need no processing beyond PNG validation."""

    records: list[ArtworkRecord] = []
    for subdirectory, category in _PICTURE_CATEGORIES.items():
        directory = extracted_root / _AVG_ROOT / subdirectory
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.png")):
            asset_id = path.stem
            records.append(
                ArtworkRecord(
                    id=asset_id,
                    category=category,
                    image=PngArtifact.from_bytes(path.read_bytes()),
                )
            )
    return records


def _animated_records(extracted_root: Path) -> list[ArtworkRecord]:
    """Create a poster and one image record for every Anime KV PNG."""

    root = extracted_root / _AVG_ROOT / "animatedkv"
    records: list[ArtworkRecord] = []
    if not root.is_dir():
        return records
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        candidates = sorted(directory.rglob("*.png"))
        if not candidates:
            continue
        ranked: list[tuple[int, int, str, Path]] = []
        for path in candidates:
            artifact = PngArtifact.from_bytes(path.read_bytes())
            ranked.append((artifact.width * artifact.height, artifact.byte_size, str(path), path))
        _area, _size, _path, selected = max(ranked)
        bundle_id = directory.name
        records.append(
            ArtworkRecord(
                id=bundle_id,
                category="background",
                image=PngArtifact.from_bytes(selected.read_bytes()),
            )
        )
        for path in candidates:
            relative_id = path.relative_to(directory).with_suffix("").as_posix()
            records.append(
                ArtworkRecord(
                    id=f"{bundle_id}/{relative_id}",
                    category="illustration",
                    image=PngArtifact.from_bytes(path.read_bytes()),
                )
            )
    return records


def _audio_records_under(root: Path, *, namespace: str | None) -> list[MediaRecord]:
    """Read playable AudioClip exports from one normalized extraction root."""

    records: list[MediaRecord] = []
    if not root.is_dir():
        return records
    content_types = {
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
    }
    seen_ids: dict[str, Path] = {}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        content_type = content_types.get(path.suffix.lower())
        if content_type is None:
            continue
        duration: float | None = None
        sample_rate: int | None = None
        sidecar = path.with_suffix(path.suffix + ".audio.json")
        if sidecar.is_file():
            payload = _read_json(sidecar)
            raw_duration = payload.get("duration") if isinstance(payload, dict) else None
            if isinstance(raw_duration, (int, float)) and not isinstance(raw_duration, bool):
                duration = float(raw_duration) if raw_duration > 0 else None
            raw_sample_rate = payload.get("sample_rate") if isinstance(payload, dict) else None
            if (
                isinstance(raw_sample_rate, int)
                and not isinstance(raw_sample_rate, bool)
                and raw_sample_rate > 0
            ):
                sample_rate = raw_sample_rate
        artifact = FileAudioArtifact.from_path(
            path,
            content_type=content_type,
            duration=duration,
            sample_rate=sample_rate,
        )
        relative = path.relative_to(root).with_suffix("")
        if namespace is None:
            voice_index = next(
                (index for index, part in enumerate(relative.parts) if part.casefold() == "voice"),
                None,
            )
            if voice_index is None:
                asset_id = path.stem
            else:
                voice_parts = relative.parts[voice_index + 1 :]
                if (
                    len(voice_parts) >= 2
                    and voice_parts[-1].casefold() == voice_parts[-2].casefold()
                ):
                    voice_parts = voice_parts[:-1]
                asset_id = "/".join(voice_parts) or path.stem
        else:
            asset_id = f"{namespace}/{relative.as_posix()}"
        previous = seen_ids.get(asset_id)
        if previous is not None:
            raise ValueError(f"duplicate audio asset ID {asset_id!r}: {previous} and {path}")
        seen_ids[asset_id] = path
        records.append(MediaRecord(id=asset_id, kind="audio", artifact=artifact))
    return records


def _audio_records(extracted_root: Path) -> list[MediaRecord]:
    """Read global sounds and namespaced AudioClips embedded in Anime KV bundles."""

    records = _audio_records_under(extracted_root / _AUDIO_ROOT, namespace=None)
    root = extracted_root / _AVG_ROOT / "animatedkv"
    if root.is_dir():
        for directory in sorted(path for path in root.iterdir() if path.is_dir()):
            records.extend(_audio_records_under(directory, namespace=directory.name))
    return records


def _video_records(extracted_root: Path) -> list[MediaRecord]:
    """Read VideoClip exports embedded in Anime KV bundles."""

    root = extracted_root / _AVG_ROOT / "animatedkv"
    records: list[MediaRecord] = []
    if not root.is_dir():
        return records
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        namespace = directory.name
        for path in sorted(candidate for candidate in directory.rglob("*") if candidate.is_file()):
            content_type = _VIDEO_CONTENT_TYPES.get(path.suffix.lower())
            if content_type is None:
                continue
            sidecar = path.with_suffix(path.suffix + ".video.json")
            if not sidecar.is_file():
                raise ValueError(f"missing VideoClip metadata: {sidecar}")
            payload = _read_json(sidecar)
            if not isinstance(payload, dict):
                raise TypeError(f"invalid VideoClip metadata: {sidecar}")
            declared_content_type = payload.get("content_type", content_type)
            if declared_content_type != content_type:
                raise ValueError(
                    f"VideoClip metadata content type does not match {path}: "
                    f"{declared_content_type!r} != {content_type!r}"
                )
            values: list[int] = []
            for name in (
                "width",
                "height",
                "frame_rate_numerator",
                "frame_rate_denominator",
                "frame_count",
            ):
                value = payload.get(name)
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    raise ValueError(f"VideoClip metadata has invalid {name}: {value!r}")
                values.append(value)
            artifact = FileVideoArtifact.from_path(
                path,
                content_type=content_type,
                width=values[0],
                height=values[1],
                frame_rate_numerator=values[2],
                frame_rate_denominator=values[3],
                frame_count=values[4],
            )
            asset_id = f"{namespace}/{path.relative_to(directory).with_suffix('').as_posix()}"
            records.append(MediaRecord(id=asset_id, kind="video", artifact=artifact))
    return records


def _score_asset_records(extracted_root: Path) -> list[ScoreAssetRecord]:
    """Read every dedicated Score sprite exported from the CN Windows client."""

    root = extracted_root / _MIXSTORY_ROOT
    records: list[ScoreAssetRecord] = []
    for directory_name, raw_kind in _SCORE_ASSET_DIRECTORIES.items():
        directory = root / directory_name
        if not directory.is_dir():
            continue
        kind = cast(ScoreAssetKind, raw_kind)
        for path in sorted(directory.glob("*.png")):
            records.append(
                ScoreAssetRecord(
                    id=path.stem,
                    kind=kind,
                    image=PngArtifact.from_bytes(path.read_bytes()),
                )
            )
    return records


def add_gallery_artworks(
    manifest: ArtworkManifest,
    recipes: Sequence[GalleryArtwork],
) -> ArtworkManifest:
    """Stitch recipes whose complete ordered panel set is present in one resource.

    The client metadata describes each panel's logical layout dimensions. Windows
    bundle textures may differ from those dimensions, so resize only the copy used
    by the final artwork and retain the native panel artifact below.
    """

    artworks = {(artwork.category, artwork.id): artwork for artwork in manifest.artworks}
    sources = {(source.category, source.id): source for source in manifest.source_layers}
    for recipe in recipes:
        if recipe.layout == "none":
            continue
        panels = [artworks.get((recipe.category, panel.id)) for panel in recipe.panels]
        if any(panel is None for panel in panels):
            continue
        present_panels = [panel for panel in panels if panel is not None]
        opened: list[Image.Image] = []
        canvas: Image.Image | None = None
        try:
            for record, panel in zip(present_panels, recipe.panels, strict=True):
                with Image.open(BytesIO(record.image.content)) as image:
                    layout_image = image.convert("RGBA")
                layout_size = (panel.width, panel.height)
                if layout_image.size != layout_size:
                    resized = layout_image.resize(layout_size, Image.Resampling.LANCZOS)
                    layout_image.close()
                    layout_image = resized
                opened.append(layout_image)
            if recipe.layout == "vertical":
                canvas = Image.new(
                    "RGBA",
                    (max(image.width for image in opened), sum(image.height for image in opened)),
                )
                offset = 0
                for image in opened:
                    canvas.alpha_composite(image, (0, offset))
                    offset += image.height
            else:
                canvas = Image.new(
                    "RGBA",
                    (sum(image.width for image in opened), max(image.height for image in opened)),
                )
                offset = 0
                for image in opened:
                    canvas.alpha_composite(image, (offset, 0))
                    offset += image.width
            for record in present_panels:
                sources[(record.category, record.id)] = SourceLayerRecord(
                    id=record.id,
                    category=record.category,
                    kind="panel",
                    image=record.image,
                )
            artworks[(recipe.category, recipe.asset_id)] = ArtworkRecord(
                id=recipe.asset_id,
                category=recipe.category,
                image=PngArtifact.from_image(canvas),
                source_layer_references=tuple(
                    SourceLayerReference(recipe.category, panel.id) for panel in recipe.panels
                ),
            )
        finally:
            if canvas is not None:
                canvas.close()
            for image in opened:
                image.close()
    return ArtworkManifest(
        upstream_version=manifest.upstream_version,
        artworks=tuple(
            sorted(artworks.values(), key=lambda artwork: (artwork.category, artwork.id))
        ),
        source_layers=tuple(
            sorted(sources.values(), key=lambda source: (source.category, source.id))
        ),
        score_assets=manifest.score_assets,
        score_videos=manifest.score_videos,
        media=manifest.media,
    )


def _character_records(extracted_root: Path) -> tuple[list[ArtworkRecord], list[SourceLayerRecord]]:
    """Process character sources and compose every available variation.

    The operation consists of decoding the color and alpha images, merging the
    alpha channels, and then merging each face onto its corresponding body.
    Face variations that require a missing body image are skipped; upstream
    data can contain such references even though there is nothing useful to
    compose. Whole-body variations remain independently renderable.
    """

    character_root = extracted_root / _AVG_ROOT / "characters"
    artworks: list[ArtworkRecord] = []
    sources: dict[str, SourceLayerRecord] = {}
    if not character_root.is_dir():
        return artworks, []

    for directory in sorted(path for path in character_root.iterdir() if path.is_dir()):
        character_id = directory.stem
        for body_index, body in enumerate(_scan_character(directory), start=1):
            body_image = _logical_image(directory, body.sprite) if body.sprite else None
            body_source_id: str | None = None
            resized_body: Image.Image | None = None
            if body.sprite and body_image is not None:
                body_source_id = f"{character_id}:body:{body_index}"
                sources[body_source_id] = SourceLayerRecord(
                    id=body_source_id,
                    category="character",
                    kind="character",
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
                sources[source_id] = SourceLayerRecord(
                    id=source_id,
                    category="character",
                    kind="character",
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

                artworks.append(
                    ArtworkRecord(
                        id=f"{character_id}#{face_index}${body_index}",
                        category="character",
                        image=PngArtifact.from_image(output),
                        source_layer_references=tuple(
                            SourceLayerReference("character", source_id) for source_id in source_ids
                        ),
                    )
                )
    return artworks, list(sources.values())


def _deduplicate_artworks(records: tuple[ArtworkRecord, ...]) -> tuple[ArtworkRecord, ...]:
    """Keep the final record for each category-qualified artwork identity."""

    by_identity: dict[tuple[str, str], ArtworkRecord] = {}
    for record in records:
        identity = (record.category, record.id)
        previous = by_identity.get(identity)
        if previous is not None:
            _LOGGER.warning(
                "duplicate artwork identity; keeping later bundle category=%s asset_id=%s",
                record.category,
                record.id,
            )
        by_identity[identity] = record
    return tuple(by_identity.values())


def build_artwork_manifest(extracted_root: Path, upstream_version: str) -> ArtworkManifest:
    """Scan and process one extracted artwork delta into a manifest."""
    pictures = [*_picture_records(extracted_root), *_animated_records(extracted_root)]
    characters, sources = _character_records(extracted_root)
    return ArtworkManifest(
        upstream_version=upstream_version,
        artworks=tuple(
            sorted(
                _deduplicate_artworks((*pictures, *characters)),
                key=lambda record: (record.category, record.id),
            )
        ),
        source_layers=tuple(sorted(sources, key=lambda record: record.id)),
        score_assets=tuple(
            sorted(
                _score_asset_records(extracted_root),
                key=lambda record: (record.kind, record.id),
            )
        ),
        media=tuple(
            sorted(
                [*_audio_records(extracted_root), *_video_records(extracted_root)],
                key=lambda record: (record.kind, record.id),
            )
        ),
    )


def merge_artwork_manifests(
    manifests: Sequence[ArtworkManifest],
    upstream_version: str,
) -> ArtworkManifest:
    """Merge independently processed bundles by category-qualified identity."""
    if not isinstance(upstream_version, str) or not upstream_version:
        raise ValueError("upstream version cannot be empty")
    for manifest in manifests:
        if not isinstance(manifest, ArtworkManifest):
            raise TypeError(f"invalid artwork manifest: {manifest!r}")
        if manifest.upstream_version != upstream_version:
            raise ValueError("cannot merge artwork manifests from different upstream versions")

    artworks = tuple(artwork for manifest in manifests for artwork in manifest.artworks)
    sources: dict[tuple[str, str], SourceLayerRecord] = {}
    score_assets: dict[tuple[str, str], ScoreAssetRecord] = {}
    score_videos: dict[str, ScoreVideoRecord] = {}
    media: dict[tuple[str, str], MediaRecord] = {}
    for manifest in manifests:
        for source in manifest.source_layers:
            sources[(source.category, source.id)] = source
        for asset in manifest.score_assets:
            score_assets[(asset.kind, asset.id)] = asset
        for video in manifest.score_videos:
            score_videos[video.id] = video
        for record in manifest.media:
            media[(record.kind, record.id)] = record
    return ArtworkManifest(
        upstream_version=upstream_version,
        artworks=tuple(
            sorted(
                _deduplicate_artworks(artworks), key=lambda artwork: (artwork.category, artwork.id)
            )
        ),
        source_layers=tuple(
            sorted(sources.values(), key=lambda source: (source.category, source.id))
        ),
        score_assets=tuple(sorted(score_assets.values(), key=lambda asset: (asset.kind, asset.id))),
        score_videos=tuple(sorted(score_videos.values(), key=lambda video: video.id)),
        media=tuple(sorted(media.values(), key=lambda record: (record.kind, record.id))),
    )


def write_artwork_manifest(manifest: ArtworkManifest, destination: Path) -> None:
    """Persist one cache manifest and its ordinal PNG files.

    Ordinal names keep the cache layout independent from upstream identifiers. The function writes ``manifest.json`` after every image. Each cache entry belongs to one upstream version, so records inherit the manifest's ``upstream_version``.
    """
    processed = destination / "processed"
    processed.mkdir(parents=True, exist_ok=True)

    next_image_index = 0
    next_video_index = 0
    next_media_index = 0

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

    def persist_video(artifact: FileVideoArtifact) -> str:
        nonlocal next_video_index
        relative = _cached_video_path(next_video_index)
        next_video_index += 1
        output = destination / Path(relative)
        if artifact.path != output.resolve():
            shutil.copyfile(artifact.path, output)
        return relative

    def persist_media(artifact: FileAudioArtifact | FileVideoArtifact) -> str:
        nonlocal next_media_index
        suffix = artifact.path.suffix.lower()
        relative = _cached_media_path(next_media_index, suffix)
        next_media_index += 1
        output = destination / Path(relative)
        if artifact.path != output.resolve():
            shutil.copyfile(artifact.path, output)
        return relative

    payload = {
        "upstream_version": manifest.upstream_version,
        "artworks": [
            {
                "id": artwork.id,
                "category": artwork.category,
                _IMAGE_PATH_FIELD: persist_image(artwork.image),
                "source_layer_references": [
                    {"category": source.category, "id": source.id}
                    for source in artwork.source_layer_references
                ],
            }
            for artwork in manifest.artworks
        ],
        "source_layers": [
            {
                "id": source.id,
                "category": source.category,
                "kind": source.kind,
                "character_id": source.character_id,
                "role": source.role,
                "variant": source.variant,
                _IMAGE_PATH_FIELD: persist_image(source.image),
            }
            for source in manifest.source_layers
        ],
        "score_assets": [
            {
                "id": asset.id,
                "kind": asset.kind,
                _IMAGE_PATH_FIELD: persist_image(asset.image),
            }
            for asset in manifest.score_assets
        ],
        "score_videos": [
            {
                "id": video.id,
                _VIDEO_PATH_FIELD: persist_video(video.video),
                "width": video.video.width,
                "height": video.video.height,
                "frame_rate_numerator": video.video.frame_rate_numerator,
                "frame_rate_denominator": video.video.frame_rate_denominator,
                "frame_count": video.video.frame_count,
            }
            for video in manifest.score_videos
        ],
        "media": [
            {
                "id": media.id,
                "kind": media.kind,
                _MEDIA_PATH_FIELD: persist_media(media.artifact),
                "content_type": media.artifact.content_type,
                "duration": media.artifact.duration
                if isinstance(media.artifact, FileAudioArtifact)
                else None,
                "sample_rate": media.artifact.sample_rate
                if isinstance(media.artifact, FileAudioArtifact)
                else None,
                "width": media.artifact.width
                if isinstance(media.artifact, FileVideoArtifact)
                else None,
                "height": media.artifact.height
                if isinstance(media.artifact, FileVideoArtifact)
                else None,
                "frame_rate_numerator": media.artifact.frame_rate_numerator
                if isinstance(media.artifact, FileVideoArtifact)
                else None,
                "frame_rate_denominator": media.artifact.frame_rate_denominator
                if isinstance(media.artifact, FileVideoArtifact)
                else None,
                "frame_count": media.artifact.frame_count
                if isinstance(media.artifact, FileVideoArtifact)
                else None,
            }
            for media in manifest.media
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
    value = _required_field(payload, name, "artwork manifest")
    if not isinstance(value, list):
        raise TypeError(f"cached artwork manifest has an invalid {name}: {source}")
    return value


def _cached_image_path(index: int) -> str:
    return f"processed/{index:08d}.png"


def _cached_video_path(index: int) -> str:
    return f"processed/{index:08d}.webm"


def _cached_media_path(index: int, suffix: str) -> str:
    if suffix not in {
        ".flac",
        ".m4a",
        ".m4v",
        ".mov",
        ".mp3",
        ".mp4",
        ".ogg",
        ".wav",
        ".webm",
    }:
        raise ValueError(f"unsupported cached media suffix: {suffix!r}")
    return f"processed/media-{index:08d}{suffix}"


def _cached_identifier(record: dict[str, object], name: str, context: str) -> str:
    value = _required_string(record, name, context)
    return value


def _positive_integer(record: dict[str, object], name: str, context: str) -> int:
    value = _required_field(record, name, context)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"cached {context} has an invalid {name}: {value!r}")
    return value


def _read_artwork_manifest(source: Path) -> ArtworkManifest:
    """Read one rendered cache entry without translating malformed data."""

    payload = _read_json(source / "manifest.json")
    if not isinstance(payload, dict):
        raise TypeError(f"cached artwork manifest is not an object: {source}")

    version = _required_string(payload, "upstream_version", "artwork manifest")
    raw_artworks = _required_records(payload, "artworks", source)
    raw_sources = _required_records(payload, "source_layers", source)
    raw_score_assets = _required_records(payload, "score_assets", source)
    raw_score_videos = _required_records(payload, "score_videos", source)
    raw_media = payload.get("media", [])
    if not isinstance(raw_media, list):
        raise TypeError(f"cached artwork manifest has an invalid media: {source}")
    next_image_index = 0
    next_video_index = 0
    next_media_index = 0

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
            raise ValueError(f"cannot read cached artwork image {path}: {error}") from error

    def video_artifact(record: dict[str, object], context: str) -> FileVideoArtifact:
        nonlocal next_video_index
        expected = _cached_video_path(next_video_index)
        next_video_index += 1
        relative = _required_string(record, _VIDEO_PATH_FIELD, context)
        if relative != expected:
            raise ValueError(
                f"cached {context} has an invalid {_VIDEO_PATH_FIELD}: "
                f"{relative!r}, expected {expected!r}"
            )
        try:
            return FileVideoArtifact.from_path(
                source / Path(expected),
                width=_positive_integer(record, "width", context),
                height=_positive_integer(record, "height", context),
                frame_rate_numerator=_positive_integer(record, "frame_rate_numerator", context),
                frame_rate_denominator=_positive_integer(record, "frame_rate_denominator", context),
                frame_count=_positive_integer(record, "frame_count", context),
            )
        except (OSError, TypeError, ValueError) as error:
            raise ValueError(f"cannot read cached Score video: {error}") from error

    def media_artifact(
        record: dict[str, object], context: str
    ) -> FileAudioArtifact | FileVideoArtifact:
        nonlocal next_media_index
        relative = _required_string(record, _MEDIA_PATH_FIELD, context)
        suffix = Path(relative).suffix.lower()
        expected = _cached_media_path(next_media_index, suffix)
        next_media_index += 1
        if relative != expected:
            raise ValueError(
                f"cached {context} has an invalid {_MEDIA_PATH_FIELD}: "
                f"{relative!r}, expected {expected!r}"
            )
        path = source / Path(expected)
        kind = _required_string(record, "kind", context)
        try:
            if kind == "audio":
                content_type = _required_string(record, "content_type", context)
                duration = record.get("duration")
                if duration is not None and (
                    not isinstance(duration, (int, float)) or isinstance(duration, bool)
                ):
                    raise ValueError(f"cached {context} has an invalid duration: {duration!r}")
                sample_rate = record.get("sample_rate")
                if sample_rate is not None and (
                    not isinstance(sample_rate, int)
                    or isinstance(sample_rate, bool)
                    or sample_rate <= 0
                ):
                    raise ValueError(
                        f"cached {context} has an invalid sample rate: {sample_rate!r}"
                    )
                return FileAudioArtifact.from_path(
                    path,
                    content_type=content_type,
                    duration=duration,
                    sample_rate=sample_rate,
                )
            if kind == "video":
                content_type = _required_string(record, "content_type", context)
                return FileVideoArtifact.from_path(
                    path,
                    content_type=content_type,
                    width=_positive_integer(record, "width", context),
                    height=_positive_integer(record, "height", context),
                    frame_rate_numerator=_positive_integer(record, "frame_rate_numerator", context),
                    frame_rate_denominator=_positive_integer(
                        record, "frame_rate_denominator", context
                    ),
                    frame_count=_positive_integer(record, "frame_count", context),
                )
            raise ValueError(f"cached {context} has an invalid kind: {kind!r}")
        except (OSError, TypeError, ValueError) as error:
            raise ValueError(f"cannot read cached media {path}: {error}") from error

    artworks: list[ArtworkRecord] = []
    for index, value in enumerate(raw_artworks):
        context = f"artwork record {index}"
        if not isinstance(value, dict):
            raise TypeError(f"cached {context} is not an object: {value!r}")
        category = _required_string(value, "category", context)
        if category not in _ARTWORK_CATEGORIES:
            raise ValueError(f"cached {context} has an invalid category: {category!r}")
        raw_references = _required_field(value, "source_layer_references", context)
        if not isinstance(raw_references, list) or not all(
            isinstance(reference, dict) for reference in raw_references
        ):
            raise ValueError(f"cached {context} has invalid source-layer references")
        references = []
        for reference_index, raw_reference in enumerate(raw_references):
            reference_context = f"{context} source reference {reference_index}"
            raw_category = _required_string(raw_reference, "category", reference_context)
            if raw_category not in _ARTWORK_CATEGORIES:
                raise ValueError(
                    f"cached {reference_context} has an invalid category: {raw_category!r}"
                )
            references.append(
                SourceLayerReference(
                    cast(ArtworkCategory, raw_category),
                    _cached_identifier(raw_reference, "id", reference_context),
                )
            )
        artworks.append(
            ArtworkRecord(
                id=_cached_identifier(value, "id", context),
                category=cast(ArtworkCategory, category),
                image=artifact(value, context),
                source_layer_references=tuple(references),
            )
        )

    sources: list[SourceLayerRecord] = []
    for index, value in enumerate(raw_sources):
        context = f"source-layer record {index}"
        if not isinstance(value, dict):
            raise TypeError(f"cached {context} is not an object: {value!r}")
        category = _required_string(value, "category", context)
        if category not in _ARTWORK_CATEGORIES:
            raise ValueError(f"cached {context} has an invalid category: {category!r}")
        kind = _required_string(value, "kind", context)
        if kind not in _SOURCE_KINDS:
            raise ValueError(f"cached {context} has an invalid kind: {kind!r}")
        character_id = value.get("character_id")
        role = value.get("role")
        variant = value.get("variant")
        if kind == "character":
            if not isinstance(character_id, str) or not character_id:
                raise ValueError(f"cached {context} has an invalid character_id")
            if role not in _SOURCE_ROLES:
                raise ValueError(f"cached {context} has an invalid role: {role!r}")
            if not isinstance(variant, str) or not variant:
                raise ValueError(f"cached {context} has an invalid variant")
        elif any(value is not None for value in (character_id, role, variant)):
            raise ValueError(f"cached {context} panel has character metadata")
        sources.append(
            SourceLayerRecord(
                id=_cached_identifier(value, "id", context),
                category=cast(ArtworkCategory, category),
                kind=cast(Any, kind),
                image=artifact(value, context),
                character_id=cast(str | None, character_id),
                role=cast(SourceRole | None, role),
                variant=cast(str | None, variant),
            )
        )

    score_assets: list[ScoreAssetRecord] = []
    for index, value in enumerate(raw_score_assets):
        context = f"Score asset record {index}"
        if not isinstance(value, dict):
            raise TypeError(f"cached {context} is not an object: {value!r}")
        kind = _required_string(value, "kind", context)
        if kind not in _SCORE_ASSET_KINDS:
            raise ValueError(f"cached {context} has an invalid kind: {kind!r}")
        score_assets.append(
            ScoreAssetRecord(
                id=_cached_identifier(value, "id", context),
                kind=cast(ScoreAssetKind, kind),
                image=artifact(value, context),
            )
        )

    score_videos: list[ScoreVideoRecord] = []
    for index, value in enumerate(raw_score_videos):
        context = f"Score video record {index}"
        if not isinstance(value, dict):
            raise TypeError(f"cached {context} is not an object: {value!r}")
        score_videos.append(
            ScoreVideoRecord(
                id=_cached_identifier(value, "id", context),
                video=video_artifact(value, context),
            )
        )

    media: list[MediaRecord] = []
    for index, value in enumerate(raw_media):
        context = f"media record {index}"
        if not isinstance(value, dict):
            raise TypeError(f"cached {context} is not an object: {value!r}")
        kind = _required_string(value, "kind", context)
        if kind not in {"audio", "video"}:
            raise ValueError(f"cached {context} has an invalid kind: {kind!r}")
        media.append(
            MediaRecord(
                id=_cached_identifier(value, "id", context),
                kind=cast(Any, kind),
                artifact=media_artifact(value, context),
            )
        )

    manifest = ArtworkManifest(
        upstream_version=version,
        artworks=tuple(artworks),
        source_layers=tuple(sources),
        score_assets=tuple(score_assets),
        score_videos=tuple(score_videos),
        media=tuple(media),
    )
    _validate_cached_relationships(manifest)
    return manifest


def _validate_cached_relationships(manifest: ArtworkManifest) -> None:
    """Check relationships owned by the cache format rather than upstream data."""

    artwork_ids = [(artwork.category, artwork.id) for artwork in manifest.artworks]
    source_ids = [(source.category, source.id) for source in manifest.source_layers]
    score_asset_ids = [(asset.kind, asset.id) for asset in manifest.score_assets]
    score_video_ids = [video.id for video in manifest.score_videos]
    media_ids = [(media.kind, media.id) for media in manifest.media]
    if len(artwork_ids) != len(set(artwork_ids)):
        raise ValueError("cached artwork identities are not unique")
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("cached source-layer identifiers are not unique")
    if len(score_asset_ids) != len(set(score_asset_ids)):
        raise ValueError("cached Score asset identifiers are not unique")
    if len(score_video_ids) != len(set(score_video_ids)):
        raise ValueError("cached Score video identifiers are not unique")
    if len(media_ids) != len(set(media_ids)):
        raise ValueError("cached media identifiers are not unique")

    available_sources = set(source_ids)
    for artwork in manifest.artworks:
        if not isinstance(artwork.source_layer_references, tuple) or len(
            artwork.source_layer_references
        ) != len(set(artwork.source_layer_references)):
            raise ValueError(f"cached artwork {artwork.id} repeats a source-layer reference")
        missing = {
            (reference.category, reference.id) for reference in artwork.source_layer_references
        } - available_sources
        if missing:
            raise ValueError(
                f"cached artwork {artwork.id} references missing sources: {sorted(missing)}"
            )


def read_artwork_manifest(source: Path) -> ArtworkManifest:
    """Load a cached manifest and decode every referenced PNG.

    The function validates the updater's cache format and source-layer relationships without imposing extra assumptions on the upstream schema.
    """
    try:
        return _read_artwork_manifest(source)
    except ValueError:
        raise
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"cached artwork manifest is malformed: {source}: {error}") from error
