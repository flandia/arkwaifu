"""Parse localized galleries from older and current upstream schemas."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..domain import Gallery, GalleryEntry

_EXCEL_ROOT = Path("assets/torappu/dynamicassets/gamedata/excel")


def parse_galleries(root: Path) -> tuple[Gallery, ...]:
    """Parse the older archive layout and the current composite CG layout."""
    story_review = _read(root, "story_review_meta_table.json")
    retro = _read(root, "retro_table.json")
    replicate = _read(root, "replicate_table.json")
    roguelike = _read(root, "roguelike_topic_table.json")
    stage = _read(root, "stage_table.json", optional=True)
    activity = _read(root, "activity_table.json", optional=True)

    art_metadata: dict[str, GalleryEntry] = {}
    for raw in _values(_at(story_review, "actArchiveResData", "pics")):
        identifier = _text(_at(raw, "id")).lower()
        art_id = _text(_at(raw, "assetPath")).lower()
        if identifier and art_id:
            art_metadata[identifier] = GalleryEntry(
                id=identifier,
                position=0,
                name=_text(_at(raw, "desc")),
                description=_text(_at(raw, "picDescription")),
                art_id=art_id,
            )

    descriptions: dict[str, str] = {}
    for story_set in _values(_at(stage, "storylineStorySets")):
        gallery_id = _text(_at(story_set, "relevantActivityId")).lower()
        if gallery_id:
            descriptions[gallery_id] = _story_set_description(story_set)

    metadata: dict[str, Gallery] = {}
    for raw in _values(_at(retro, "retroActList")):
        for linked_id in _values(_at(raw, "linkedActId")):
            gallery_id = _text(linked_id).lower()
            if not gallery_id:
                continue
            description = _text(_at(raw, "detail")) or descriptions.get(gallery_id, "")
            metadata[gallery_id] = Gallery(
                id=gallery_id,
                name=_text(_at(raw, "name")),
                description=description,
                entries=(),
            )
    for raw in _values(_at(roguelike, "topics")):
        gallery_id = _text(_at(raw, "id")).lower()
        if gallery_id:
            metadata[gallery_id] = Gallery(
                id=gallery_id,
                name=_text(_at(raw, "name")),
                description=_text(_at(raw, "lineText")),
                entries=(),
            )

    galleries: dict[str, Gallery] = {}
    components = _mapping(_at(story_review, "actArchiveData", "components"))
    replicated = _mapping(replicate)
    for raw_id, component in components.items():
        if raw_id in replicated:
            continue
        gallery_id = raw_id.lower()
        gallery = metadata.get(gallery_id)
        if gallery is None:
            continue
        entries = []
        for raw in _values(_at(component, "pic", "pics")):
            entry = art_metadata.get(_text(_at(raw, "picId")).lower())
            if entry is not None:
                entries.append(replace(entry, position=_integer(_at(raw, "picSortId"))))
        galleries[gallery_id] = replace(gallery, entries=tuple(entries))

    _merge_current_cg_schema(stage, activity, replicated, metadata, galleries)
    return tuple(galleries[key] for key in sorted(galleries))


def _merge_current_cg_schema(
    stage: Any,
    activity: Any,
    replicated: dict[str, Any],
    metadata: dict[str, Gallery],
    galleries: dict[str, Gallery],
) -> None:
    """Merge current CG displays with archive metadata without duplicate art.

    Existing entries keep their order and gain missing labels. New displays
    are appended with stable unique entry identifiers.
    """

    used_entry_ids = {entry.id for gallery in galleries.values() for entry in gallery.entries}
    groups = _mapping(_at(stage, "cgGalleryGroups"))
    story_sets = _mapping(_at(stage, "storylineStorySets"))
    displays = _mapping(_at(stage, "cgGalleryDisplays"))

    for group_id in sorted(groups):
        group = groups[group_id]
        story_set = story_sets.get(group_id)
        gallery_id = _text(_at(story_set, "relevantActivityId")).lower()
        if not gallery_id or gallery_id in replicated:
            continue

        gallery = galleries.get(gallery_id) or metadata.get(gallery_id)
        if gallery is None:
            name = _activity_name(activity, gallery_id)
            if not name:
                continue
            gallery = Gallery(gallery_id, name, "", ())
        gallery = replace(
            gallery,
            name=gallery.name or _activity_name(activity, gallery_id),
            description=gallery.description or _story_set_description(story_set),
        )

        entries = list(gallery.entries)
        index_by_art_id = {entry.art_id: index for index, entry in enumerate(entries)}
        next_position = max((entry.position for entry in entries), default=0)
        for display_id_value in _values(_at(group, "displays")):
            display_id = _text(display_id_value)
            if not display_id:
                continue
            display = displays.get(display_id)
            name = _text(_at(display, "displayName"))
            description = _text(_at(display, "displayDesc"))
            for index, art_id_value in enumerate(_values(_at(display, "cgList")), start=1):
                art_id = _text(art_id_value).lower()
                if not art_id:
                    continue
                existing_index = index_by_art_id.get(art_id)
                if existing_index is not None:
                    existing = entries[existing_index]
                    entries[existing_index] = replace(
                        existing,
                        name=existing.name or name,
                        description=existing.description or description,
                    )
                    continue
                next_position += 1
                entry_id = _unique_id(f"{display_id.lower()}_{index}", used_entry_ids)
                entries.append(GalleryEntry(entry_id, next_position, name, description, art_id))
                index_by_art_id[art_id] = len(entries) - 1
        galleries[gallery_id] = replace(gallery, entries=tuple(entries))


def _read(root: Path, name: str, *, optional: bool = False) -> Any:
    path = root / _EXCEL_ROOT / name
    if optional and not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _at(value: Any, *path: str) -> Any:
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _values(value: Any) -> tuple[Any, ...]:
    if isinstance(value, dict):
        return tuple(value.values())
    if isinstance(value, list):
        return tuple(value)
    return ()


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _integer(value: Any) -> int:
    return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0


def _story_set_description(story_set: Any) -> str:
    for section in ("ssData", "mainlineData", "collectData"):
        description = _text(_at(story_set, section, "desc"))
        if description:
            return description
    return ""


def _activity_name(activity: Any, gallery_id: str) -> str:
    return _text(_at(activity, "basicInfo", gallery_id, "name"))


def _unique_id(base: str, used: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate
