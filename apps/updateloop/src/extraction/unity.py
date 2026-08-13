"""Extract the Unity objects used by the art processor.

Texture, sprite, and character-hub objects are written into the normalized
``assets/torappu/dynamicassets`` tree. Concurrent production extraction uses
a disposable process for each bundle so UnityPy's decoded objects do not
accumulate across a full update; ``workers=1`` runs in the caller.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path, PurePosixPath

import UnityPy
from PIL import Image
from UnityPy.classes import GameObject, MonoBehaviour, Object, Sprite, Texture2D

from ..local_path import resolve_local_path
from .lz4ak import patch_unitypy

EXTRACTOR_TASKS_PER_WORKER = 1


class ExtractionError(RuntimeError):
    """Report every bundle that failed during one extraction operation."""

    def __init__(self, failures: list[tuple[Path, str]]) -> None:
        """Create one error that reports every failed bundle."""
        self.failures = failures
        detail = "; ".join(f"{path}: {message}" for path, message in failures)
        super().__init__(f"failed to extract {len(failures)} bundle(s): {detail}")


def normalize_container_path(container: str | PurePosixPath) -> PurePosixPath:
    """Map Arknights' short bundle paths to the tree used by the art processor."""

    normalized = PurePosixPath(str(container).replace("\\", "/"))
    if normalized.parts and normalized.parts[0].lower() == "dyn":
        return PurePosixPath("assets", "torappu", "dynamicassets", *normalized.parts[1:])
    return normalized


def mono_behaviour_name(obj: MonoBehaviour, type_tree=None) -> str:
    """Get a useful class name even when UnityPy cannot resolve MonoScript.

    Some character bundles reference a shared MonoScript CAB that they do not include. The sprite hub's serialized type-tree shape still identifies the names required by the art scanner.
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
    MonoBehaviours become hub JSON, while GameObjects provide the object set
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
    for container_name, reader in environment.container.items():
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
