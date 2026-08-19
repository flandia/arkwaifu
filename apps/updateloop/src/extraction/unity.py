"""Extract the Unity objects used by the artwork processor.

Texture, sprite, and character-hub objects are written into the normalized
``assets/torappu/dynamicassets`` tree. Concurrent production extraction uses
a disposable process for each bundle so UnityPy's decoded objects do not
accumulate across a full update; ``workers=1`` runs in the caller.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path, PurePosixPath

import UnityPy
from PIL import Image
from UnityPy.classes import (
    AudioClip,
    GameObject,
    MonoBehaviour,
    Object,
    Sprite,
    Texture2D,
    VideoClip,
)
from UnityPy.helpers.ResourceReader import get_resource_data

from ..local_path import resolve_local_path
from .lz4ak import patch_unitypy

EXTRACTOR_TASKS_PER_WORKER = 1

_AUDIO_SUFFIXES = {".flac", ".m4a", ".mp3", ".ogg", ".wav"}


def _common_audio_suffix(content: bytes) -> str | None:
    """Return a common audio suffix detected from the source bytes."""

    if content[:4] == b"OggS":
        return ".ogg"
    if content[:4] == b"RIFF":
        return ".wav"
    if content[:4] == b"fLaC":
        return ".flac"
    if content[:3] == b"ID3" or (
        len(content) >= 4
        and content[0] == 0xFF
        and content[1] & 0xE0 == 0xE0
        and content[1] & 0x06 != 0
        and content[2] & 0xF0 not in {0x00, 0xF0}
        and content[2] & 0x0C != 0x0C
    ):
        return ".mp3"
    if len(content) >= 8 and content[4:8] == b"ftyp":
        return ".m4a"
    return None


def _audio_clip_source(obj: AudioClip) -> bytes | None:
    """Read an AudioClip's original bytes before UnityPy decodes them."""

    audio_data = getattr(obj, "m_AudioData", None)
    if audio_data:
        return bytes(audio_data)

    resource = getattr(obj, "m_Resource", None)
    reader = obj.object_reader
    source = getattr(resource, "m_Source", None)
    offset = getattr(resource, "m_Offset", None)
    size = getattr(resource, "m_Size", None)
    if (
        reader is None
        or not isinstance(source, str)
        or not source
        or not isinstance(offset, int)
        or offset < 0
        or not isinstance(size, int)
        or size <= 0
    ):
        return None
    return get_resource_data(source, reader.assets_file, offset, size)


class ExtractionError(RuntimeError):
    """Report every bundle that failed during one extraction operation."""

    def __init__(self, failures: list[tuple[Path, str]]) -> None:
        """Create one error that reports every failed bundle."""
        self.failures = failures
        detail = "; ".join(f"{path}: {message}" for path, message in failures)
        super().__init__(f"failed to extract {len(failures)} bundle(s): {detail}")


def normalize_container_path(container: str | PurePosixPath) -> PurePosixPath:
    """Map Arknights' short bundle paths to the tree used by the artwork processor."""

    normalized = PurePosixPath(str(container).replace("\\", "/"))
    if normalized.parts and normalized.parts[0].lower() == "dyn":
        return PurePosixPath("assets", "torappu", "dynamicassets", *normalized.parts[1:])
    return normalized


def mono_behaviour_name(obj: MonoBehaviour, type_tree=None) -> str:
    """Get a useful class name even when UnityPy cannot resolve MonoScript.

    Some character bundles reference a shared MonoScript CAB that they do not include. The sprite hub's serialized type-tree shape still identifies the names required by the artwork scanner.
    """

    try:
        script = obj.m_Script.read()
    except FileNotFoundError:
        script = None

    script_name = getattr(script, "m_Name", "") if script is not None else ""
    if script_name:
        return script_name
    if type_tree is None:
        type_tree = obj.object_reader.read_typetree()
    if "spriteGroups" in type_tree:
        return "AVGCharacterSpriteHubGroup"
    if "sprites" in type_tree:
        return "AVGCharacterSpriteHub"
    return f"MonoBehaviour_{obj.object_reader.path_id}"


def _safe_destination(root: Path, relative: PurePosixPath) -> Path:
    """Resolve one container path while keeping it below the extraction root."""

    return resolve_local_path(root, relative, context="Unity container path")


def _uncontained_bundle_directory(source: Path) -> PurePosixPath:
    """Return the normalized bundle directory for an object without a container."""

    parts = PurePosixPath(str(source).replace("\\", "/")).parts
    roots = {"arts", "audio", "avg", "raw", "spritepack"}
    root_index = next(
        (index for index, part in enumerate(parts) if part.lower() in roots),
        None,
    )
    if root_index is None:
        return PurePosixPath("assets", "torappu", "dynamicassets", source.stem)
    return PurePosixPath(
        "assets",
        "torappu",
        "dynamicassets",
        *parts[root_index:-1],
        source.stem,
    )


def _export(
    obj: Object,
    destination: Path,
    fallback_directory: PurePosixPath,
    path_ids: dict[int, str],
    type_tree_ids: dict[int, str],
    *,
    honor_container: bool = True,
    expand_game_object: bool = True,
) -> None:
    """Export one supported Unity object and record its path IDs.

    Texture2D and Sprite objects become PNG files and type-tree JSON. Character
    MonoBehaviours become hub JSON, while AudioClip and VideoClip objects become
    playable media plus sidecar metadata. GameObjects provide the object set
    that must be visited when their children have no useful container paths.
    """

    raw_container = obj.object_reader.container
    container = (
        normalize_container_path(raw_container) if honor_container and raw_container else None
    )
    object_name = getattr(obj, "m_Name", "")
    object_type = obj.object_reader.type.name
    path_id = obj.object_reader.path_id

    if isinstance(obj, (Texture2D, Sprite)):
        relative = container or fallback_directory / f"{object_name}.png"
        relative = PurePosixPath(os.path.normpath(str(relative)).replace("\\", "/"))
        image_path = _safe_destination(destination, relative)
        tree_path = image_path.with_suffix(f".{object_type}.json")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        path_ids[path_id] = image_path.name
        type_tree_ids[path_id] = tree_path.name

        # Sometimes a Sprite and Texture2D have the same name. Texture2D is
        # preferred because it is usually the original image.
        if not (image_path.exists() and isinstance(obj, Sprite)):
            obj.image.save(image_path, format="PNG")
        tree_path.write_text(
            json.dumps(
                obj.object_reader.read_typetree(),
                ensure_ascii=False,
                indent=2,
                default=lambda _value: "<non-serializable>",
            ),
            encoding="utf-8",
        )
        return

    if isinstance(obj, MonoBehaviour):
        if any(part.lower() == "animatedkv" for part in fallback_directory.parts):
            # Anime KV is treated as a media container. Spine data, particle
            # controllers, and other MonoBehaviours are not archive products.
            return
        type_tree = obj.object_reader.read_typetree()
        object_name = mono_behaviour_name(obj, type_tree)
        relative = container or fallback_directory / f"{object_name}.json"
        relative = PurePosixPath(os.path.normpath(str(relative)).replace("\\", "/"))
        output_path = _safe_destination(destination, relative)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        path_ids[path_id] = output_path.name
        output_path.write_text(
            json.dumps(
                type_tree, ensure_ascii=False, indent=2, default=lambda _value: "<non-serializable>"
            ),
            encoding="utf-8",
        )
        return

    if isinstance(obj, AudioClip):
        source_content = _audio_clip_source(obj)
        source_suffix = _common_audio_suffix(source_content) if source_content else None
        if source_content and source_suffix is not None:
            source_name = PurePosixPath(str(object_name).replace("\\", "/")).stem
            if not source_name:
                source_name = f"audio-{path_id}"
            raw_samples = {f"{source_name}{source_suffix}": source_content}
        else:
            # UnityPy decodes raw/FMOD data to PCM WAV when no common source
            # container can be retained. This is the only conversion fallback.
            raw_samples = obj.samples
        if not isinstance(raw_samples, dict) or not raw_samples:
            raise ValueError(f"AudioClip {object_name!r} has no decoded samples")
        type_tree = obj.object_reader.read_typetree()
        duration = type_tree.get("m_Length") if isinstance(type_tree, dict) else None
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
            duration = None
        sample_rate = type_tree.get("m_Frequency") if isinstance(type_tree, dict) else None
        if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
            sample_rate = None
        output_directory = fallback_directory
        for raw_name, content in raw_samples.items():
            if not isinstance(raw_name, str) or not isinstance(content, bytes) or not content:
                raise ValueError(f"AudioClip {object_name!r} returned an invalid sample")
            name = PurePosixPath(raw_name.replace("\\", "/")).name
            if not name:
                raise ValueError(f"AudioClip {object_name!r} returned an empty sample name")
            suffix = PurePosixPath(name).suffix.lower()
            detected_suffix = _common_audio_suffix(content)
            if detected_suffix is not None:
                suffix = detected_suffix
            elif suffix not in _AUDIO_SUFFIXES:
                raise ValueError(
                    f"AudioClip {object_name!r} returned unsupported sample format: {raw_name!r}"
                )
            output_name = PurePosixPath(name).with_suffix(suffix).name
            output_path = _safe_destination(destination, output_directory / output_name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)
            output_path.with_suffix(output_path.suffix + ".audio.json").write_text(
                json.dumps(
                    {"duration": duration, "sample_rate": sample_rate}, separators=(",", ":")
                ),
                encoding="utf-8",
            )
            path_ids[path_id] = output_path.name
        return

    if isinstance(obj, VideoClip):
        reader = obj.object_reader
        assets_file = reader.assets_file if reader is not None else None
        resource = getattr(obj, "m_ExternalResources", None)
        source = getattr(resource, "m_Source", None)
        offset = getattr(resource, "m_Offset", None)
        size = getattr(resource, "m_Size", None)
        if (
            assets_file is None
            or not isinstance(source, str)
            or not source
            or not isinstance(offset, int)
            or offset < 0
            or not isinstance(size, int)
            or size <= 0
        ):
            raise ValueError(f"VideoClip {object_name!r} has no readable external resource")
        content = get_resource_data(source, assets_file, offset, size)
        if not isinstance(content, bytes) or not content:
            raise ValueError(f"VideoClip {object_name!r} returned an empty stream")

        # The external resource is already a complete video container. Keep
        # its bytes exactly as supplied; re-encoding would violate the
        # lossless-first policy. MP4/WebM are browser-native, while MOV/M4V
        # remain available when that is the format the client supplied.
        original_path = getattr(obj, "m_OriginalPath", "")
        suffix = PurePosixPath(str(original_path).replace("\\", "/")).suffix.lower()
        content_types = {
            ".m4v": "video/x-m4v",
            ".mov": "video/quicktime",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
        }
        content_type = content_types.get(suffix)
        if content_type is None:
            if content[:4] == b"\x1a\x45\xdf\xa3":
                suffix, content_type = ".webm", "video/webm"
            elif content[4:8] == b"ftyp":
                suffix, content_type = ".mp4", "video/mp4"
            else:
                raise ValueError(
                    f"VideoClip {object_name!r} has unsupported format: {original_path!r}"
                )

        width = getattr(obj, "Width", None)
        height = getattr(obj, "Height", None)
        frame_count = getattr(obj, "m_FrameCount", None)
        frame_rate = getattr(obj, "m_FrameRate", None)
        if (
            not isinstance(width, int)
            or width <= 0
            or not isinstance(height, int)
            or height <= 0
            or not isinstance(frame_count, int)
            or frame_count <= 0
            or not isinstance(frame_rate, (int, float))
            or isinstance(frame_rate, bool)
            or frame_rate <= 0
        ):
            raise ValueError(f"VideoClip {object_name!r} has invalid stream metadata")
        frame_rate_fraction = Fraction(str(frame_rate)).limit_denominator(100_000)
        name = PurePosixPath(str(object_name).replace("\\", "/")).name
        if not name:
            name = PurePosixPath(str(original_path).replace("\\", "/")).stem
        if not name:
            name = f"video-{path_id}"
        name = PurePosixPath(name).stem
        output_directory = fallback_directory
        output_path = _safe_destination(destination, output_directory / f"{name}{suffix}")
        if output_path.exists():
            output_path = _safe_destination(
                destination,
                output_directory / f"{name}-{abs(path_id)}{suffix}",
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        output_path.with_suffix(output_path.suffix + ".video.json").write_text(
            json.dumps(
                {
                    "content_type": content_type,
                    "width": width,
                    "height": height,
                    "frame_rate_numerator": frame_rate_fraction.numerator,
                    "frame_rate_denominator": frame_rate_fraction.denominator,
                    "frame_count": frame_count,
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        path_ids[path_id] = output_path.name
        return

    if isinstance(obj, GameObject) and expand_game_object:
        child_directory = fallback_directory.parent / object_name
        for reader in obj.assets_file.objects.values():
            if reader is not obj.object_reader:
                _export(
                    reader.read(),
                    destination,
                    child_directory,
                    path_ids,
                    type_tree_ids,
                    honor_container=False,
                    expand_game_object=False,
                )


def _extract_one(source: Path, destination: Path) -> None:
    """Extract one Unity bundle into the shared normalized destination."""

    patch_unitypy()
    # Initialize Pillow in each worker to preload its supported formats.
    Image.preinit()
    Image.init()
    environment = UnityPy.load(str(source))
    containers = environment.container
    contained_readers = {id(reader) for reader in containers.values()}
    for container_name, reader in containers.items():
        container = normalize_container_path(container_name)
        obj = reader.read()
        fallback = container.parent / obj.m_Name
        path_ids: dict[int, str] = {}
        type_tree_ids: dict[int, str] = {}
        _export(obj, destination, fallback, path_ids, type_tree_ids)
        if path_ids:
            directory = _safe_destination(destination, container.parent)
            directory.mkdir(parents=True, exist_ok=True)
            path_id_summary = _safe_destination(
                destination, container.parent / f"{obj.m_Name}.json"
            )
            type_tree_summary = _safe_destination(
                destination, container.parent / f"{obj.m_Name}.typetree.json"
            )
            path_id_summary.write_text(
                json.dumps(path_ids, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            type_tree_summary.write_text(
                json.dumps(type_tree_ids, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    # Unity normally puts Anime KV resources below the prefab container. A few
    # bundles instead expose media as top-level objects; scan those objects too
    # so the bundle boundary, rather than the container table, defines what we
    # archive. Unsupported Unity object types remain intentionally ignored.
    bundle_directory = _uncontained_bundle_directory(source)
    supported_types = (Texture2D, Sprite, AudioClip, VideoClip)
    for reader in getattr(environment, "objects", ()):
        if id(reader) in contained_readers or getattr(reader, "container", None):
            continue
        obj = reader.read()
        if not isinstance(obj, supported_types):
            continue
        _export(
            obj,
            destination,
            bundle_directory,
            {},
            {},
            honor_container=False,
            expand_game_object=False,
        )


def extract_assets(sources: list[Path], destination: Path, workers: int | None = None) -> None:
    """Extract all bundle files and report their failures together.

    Set ``workers=1`` to extract in the calling process. Other values use a process pool, and each child handles one bundle before replacement.
    """

    files = sorted(
        file
        for source in sources
        for file in ([source] if source.is_file() else source.rglob("*"))
        if file.is_file()
    )
    destination.mkdir(parents=True, exist_ok=True)
    if not files:
        raise ExtractionError([(Path("<input>"), "no bundle files found")])

    failures: list[tuple[Path, str]] = []
    if workers == 1:
        for file in files:
            try:
                _extract_one(file, destination)
            except Exception as error:  # noqa: BLE001 - bundle errors are aggregated
                failures.append((file, repr(error)))
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            max_tasks_per_child=EXTRACTOR_TASKS_PER_WORKER,
        ) as executor:
            futures = {executor.submit(_extract_one, file, destination): file for file in files}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as error:  # noqa: BLE001 - worker errors are aggregated
                    failures.append((futures[future], repr(error)))
    if failures:
        raise ExtractionError(sorted(failures, key=lambda item: str(item[0])))
