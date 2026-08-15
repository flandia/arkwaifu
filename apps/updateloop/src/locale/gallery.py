"""Parse the game gallery hierarchy without flattening sibling artworks."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from ..domain import (
    ArtCategory,
    CompositePanel,
    CompositeType,
    GalleryArtwork,
    GalleryDisplay,
    GalleryGroup,
)

_EXCEL_ROOT = Path("assets/torappu/dynamicassets/gamedata/excel")
_COMPOSITE_TYPES = frozenset({"none", "vertical", "horizontal"})


def parse_galleries(
    root: Path,
    *,
    collection_names: Mapping[str, str] | None = None,
    legacy_collections: Mapping[str, str] | None = None,
) -> tuple[GalleryGroup, ...]:
    """Parse current galleries, then add only non-overlapping legacy galleries.

    ``cgGalleryGroups`` supplies the authoritative hierarchy and labels.
    Distinct older pictures are appended as singleton displays, including in
    collections which have a current group. Callers provide normalized
    ownership so legacy activity IDs resolve to the shared story leaf seam.
    """

    names = {key.lower(): value for key, value in (collection_names or {}).items()}
    ownership = {key.lower(): value.lower() for key, value in (legacy_collections or {}).items()}
    stage = _mapping(_read(root, "stage_table.json", optional=True))
    galleries = _merge_legacy(
        root,
        stage,
        names,
        ownership,
        _parse_current(stage, names),
    )
    return tuple(replace(gallery, position=position) for position, gallery in enumerate(galleries))


def _parse_current(
    stage: Mapping[str, Any],
    names: Mapping[str, str],
) -> tuple[GalleryGroup, ...]:
    raw_groups = _normalized_mapping(stage.get("cgGalleryGroups"))
    raw_displays = _normalized_mapping(stage.get("cgGalleryDisplays"))
    raw_cgs = _normalized_mapping(stage.get("cgGalleryCgs"))
    story_sets = _normalized_mapping(stage.get("storylineStorySets"))
    group_rank = _group_ranks(stage)
    ordered_groups = sorted(
        raw_groups.items(),
        key=lambda item: (
            *group_rank.get(item[0].lower(), (2**31 - 1, 2**31 - 1)),
            item[0].lower(),
        ),
    )

    galleries: list[GalleryGroup] = []
    for position, (raw_group_id, value) in enumerate(ordered_groups):
        raw_group = _required_object(value, f"gallery group {raw_group_id}")
        section_id = _declared_mapping_identifier(
            raw_group,
            "storySetId",
            raw_group_id,
            "gallery group",
        )
        collection_id = _movement_collection_id(section_id)
        story_set = _required_mapping_entry(story_sets, section_id, "gallery Story Set")
        rank = group_rank.get(section_id)
        if rank is not None:
            _, _, canonical_storyline_id, canonical_location_id = rank
            declared_storyline_id = _identifier(raw_group.get("storylineId"))
            declared_location_id = _identifier(raw_group.get("locationId"))
            if declared_storyline_id not in {None, canonical_storyline_id}:
                raise ValueError(
                    "gallery group Movement does not match canonical placement: "
                    f"section_id={section_id} expected={canonical_storyline_id} "
                    f"actual={declared_storyline_id}"
                )
            if declared_location_id not in {None, canonical_location_id}:
                raise ValueError(
                    "gallery group location does not match canonical placement: "
                    f"section_id={section_id} expected={canonical_location_id} "
                    f"actual={declared_location_id}"
                )
        raw_display_ids = _strings(raw_group.get("displays"))
        if not raw_display_ids:
            raise ValueError(f"gallery group has no displays: {raw_group_id}")
        normalized_display_ids = tuple(display_id.lower() for display_id in raw_display_ids)
        if len(normalized_display_ids) != len(set(normalized_display_ids)):
            raise ValueError(f"gallery group references duplicate display: {raw_group_id}")
        displays = tuple(
            _display(
                raw_display_id,
                display_position,
                section_id,
                raw_displays,
                raw_cgs,
            )
            for display_position, raw_display_id in enumerate(raw_display_ids)
        )
        galleries.append(
            GalleryGroup(
                id=raw_group_id.lower(),
                collection_id=collection_id,
                position=position,
                name=names.get(collection_id, ""),
                description=_story_set_description(story_set),
                location_id=_identifier(raw_group.get("locationId")),
                displays=displays,
            )
        )
    return tuple(galleries)


def _display(
    raw_display_id: str,
    position: int,
    section_id: str,
    displays: Mapping[str, Any],
    cgs: Mapping[str, Any],
) -> GalleryDisplay:
    raw = _required_mapping_entry(displays, raw_display_id, "gallery display")
    display_id = _declared_mapping_identifier(
        raw,
        "displayId",
        raw_display_id,
        "gallery display",
    )
    declared_section = _identifier(raw.get("storySetId"))
    if declared_section is not None and declared_section != section_id:
        raise ValueError(
            "gallery display belongs to a different Story Set: "
            f"display_id={display_id} expected={section_id} actual={declared_section}"
        )
    category = _gallery_art_category(raw.get("cgSource"))
    raw_cg_ids = _strings(raw.get("cgList"))
    normalized_cg_ids = tuple(cg_id.lower() for cg_id in raw_cg_ids)
    if len(normalized_cg_ids) != len(set(normalized_cg_ids)):
        raise ValueError(f"gallery display references duplicate artwork: {display_id}")
    artworks = tuple(
        _artwork(cg_id, artwork_position, section_id, category, cgs)
        for artwork_position, cg_id in enumerate(raw_cg_ids)
    )
    if not artworks:
        raise ValueError(f"gallery display has no artworks: {display_id}")
    return GalleryDisplay(
        id=display_id,
        position=position,
        name=_text(raw.get("displayName")),
        description=_text(raw.get("displayDesc")),
        related_story_id=_identifier(raw.get("relatedStoryId")),
        related_stage_id=_identifier(raw.get("relatedStageId")),
        artworks=artworks,
    )


def _artwork(
    raw_cg_id: str,
    position: int,
    section_id: str,
    category: ArtCategory,
    cgs: Mapping[str, Any],
) -> GalleryArtwork:
    raw = _required_mapping_entry(cgs, raw_cg_id, "gallery artwork")
    cg_id = _declared_mapping_identifier(
        raw,
        "cgId",
        raw_cg_id,
        "gallery artwork",
    )
    declared_section = _identifier(raw.get("storySetId"))
    if declared_section is not None and declared_section != section_id:
        raise ValueError(
            "gallery artwork belongs to a different Story Set: "
            f"cg_id={cg_id} expected={section_id} actual={declared_section}"
        )
    composite_type = _text(raw.get("compositeType")).lower()
    if composite_type not in _COMPOSITE_TYPES:
        raise ValueError(f"unknown gallery composite type: {composite_type!r}")
    raw_panels = _mappings(raw.get("compositeList"))
    panels = ()
    art_id = cg_id
    if composite_type == "none":
        if raw_panels:
            raise ValueError(f"non-composite gallery artwork has panels: {cg_id}")
    else:
        panels = tuple(
            CompositePanel(
                id=_required_panel_identifier(
                    panel,
                    "cgId",
                    f"gallery composite {cg_id}",
                ),
                position=panel_position,
                width=_positive_integer(panel, "width", f"gallery composite {cg_id}"),
                height=_positive_integer(panel, "height", f"gallery composite {cg_id}"),
            )
            for panel_position, panel in enumerate(raw_panels)
        )
        if not panels:
            raise ValueError(f"gallery composite has no panels: {cg_id}")
        panel_ids = tuple(panel.id for panel in panels)
        if len(panel_ids) != len(set(panel_ids)):
            raise ValueError(f"gallery composite has duplicate panel: {cg_id}")
        art_id = "/".join(panel.id for panel in panels)
    return GalleryArtwork(
        position=position,
        cg_id=cg_id,
        art_id=art_id,
        category=category,
        composite_type=cast(CompositeType, composite_type),
        panels=panels,
    )


def _merge_legacy(
    root: Path,
    stage: Mapping[str, Any],
    names: Mapping[str, str],
    ownership: Mapping[str, str],
    current: tuple[GalleryGroup, ...],
) -> tuple[GalleryGroup, ...]:
    review_meta = _mapping(_read(root, "story_review_meta_table.json", optional=True))
    retro = _mapping(_read(root, "retro_table.json", optional=True))
    roguelike = _mapping(_read(root, "roguelike_topic_table.json", optional=True))
    replicate = _mapping(_read(root, "replicate_table.json", optional=True))
    components = _mapping(_at(review_meta, "actArchiveData", "components"))
    picture_rows = _mapping(_at(review_meta, "actArchiveResData", "pics"))
    pictures: dict[str, dict[str, Any]] = {}
    for raw_identifier, raw_value in picture_rows.items():
        value = _mapping(raw_value)
        identifier = (_text(value.get("id")) or raw_identifier).lower()
        if identifier:
            pictures[identifier] = value
    retro_names: dict[str, str] = {}
    retro_details: dict[str, str] = {}
    for raw in _mappings(_at(retro, "retroActList")):
        for activity_id in _strings(raw.get("linkedActId")):
            retro_names[activity_id.lower()] = _text(raw.get("name"))
            retro_details[activity_id.lower()] = _text(raw.get("detail"))
    topic_names: dict[str, str] = {}
    topic_details: dict[str, str] = {}
    for raw_topic_id, raw_topic in _normalized_mapping(roguelike.get("topics")).items():
        topic = _mapping(raw_topic)
        topic_id = (_text(topic.get("id")) or raw_topic_id).lower()
        topic_names[topic_id] = _text(topic.get("name"))
        topic_details[topic_id] = _text(topic.get("lineText"))

    story_sets = _normalized_mapping(stage.get("storylineStorySets"))
    section_by_activity = {
        relevant: _movement_collection_id((_text(value.get("storySetId")) or raw_id).lower())
        for raw_id, raw_value in story_sets.items()
        if (value := _mapping(raw_value))
        and (relevant := _text(value.get("relevantActivityId")).lower())
    }
    result = list(current)
    by_collection = {gallery.collection_id: index for index, gallery in enumerate(result)}
    for activity_id in sorted(components):
        normalized_activity = activity_id.lower()
        if activity_id in replicate or normalized_activity in replicate:
            continue
        collection_id = ownership.get(normalized_activity) or section_by_activity.get(
            normalized_activity
        )
        if collection_id is None:
            continue
        raw_component = _mapping(components[activity_id])
        gallery_index = by_collection.get(collection_id)
        if gallery_index is None:
            section_id = collection_id.removeprefix("movement_section:")
            story_set = _mapping(story_sets.get(section_id))
            gallery = GalleryGroup(
                id=normalized_activity,
                collection_id=collection_id,
                position=len(result),
                name=names.get(collection_id)
                or retro_names.get(normalized_activity)
                or topic_names.get(normalized_activity, ""),
                description=retro_details.get(normalized_activity)
                or topic_details.get(normalized_activity)
                or _story_set_description(story_set),
                location_id=None,
                displays=(),
            )
            gallery_index = len(result)
            by_collection[collection_id] = gallery_index
            result.append(gallery)
        gallery = result[gallery_index]
        displays = list(gallery.displays)
        existing_arts = {
            (artwork.category, artwork.art_id)
            for display in displays
            for artwork in display.artworks
        }
        used_display_ids = {display.id for display in displays}
        ordered_refs = sorted(
            _mappings(_at(raw_component, "pic", "pics")),
            key=lambda ref: (_integer(ref.get("picSortId")), _text(ref.get("picId")).lower()),
        )
        for ref in ordered_refs:
            picture_id = _identifier(ref.get("picId"))
            picture = pictures.get(picture_id or "")
            if picture is None:
                continue
            art_id = _identifier(picture.get("assetPath"))
            if art_id is None:
                continue
            identity = ("image", art_id)
            if identity in existing_arts:
                continue
            display_id = _unique_id(f"{picture_id or art_id}_legacy", used_display_ids)
            displays.append(
                GalleryDisplay(
                    id=display_id,
                    position=len(displays),
                    name=_text(picture.get("desc")),
                    description=_text(picture.get("picDescription")),
                    related_story_id=None,
                    related_stage_id=None,
                    artworks=(
                        GalleryArtwork(
                            position=0,
                            cg_id=picture_id or art_id,
                            art_id=art_id,
                            category="image",
                            composite_type="none",
                            panels=(),
                        ),
                    ),
                )
            )
            existing_arts.add(identity)
        result[gallery_index] = replace(gallery, displays=tuple(displays))
    return tuple(result)


def _group_ranks(stage: Mapping[str, Any]) -> dict[str, tuple[int, int, str, str]]:
    ranks: dict[str, tuple[int, int, str, str]] = {}
    raw_storylines = _normalized_mapping(stage.get("storylines"))
    ordered_storylines = sorted(
        raw_storylines.items(),
        key=lambda item: (_integer(_at(item[1], "sortId")), item[0].lower()),
    )
    for movement_position, (raw_storyline_id, raw_value) in enumerate(ordered_storylines):
        movement = _mapping(raw_value)
        storyline_id = (_text(movement.get("storylineId")) or raw_storyline_id).lower()
        locations = sorted(
            _mapping(movement.get("locations")).items(),
            key=lambda item: (_integer(_at(item[1], "sortId")), item[0].lower()),
        )
        for location_position, (raw_location_id, raw_location) in enumerate(locations):
            location = _mapping(raw_location)
            if _text(location.get("locationType")).upper() != "STORY_SET":
                continue
            section_id = _identifier(location.get("relevantStorySetId"))
            if section_id is not None:
                location_id = (_text(location.get("locationId")) or raw_location_id).lower()
                if section_id in ranks:
                    raise ValueError(
                        f"Story Set has multiple canonical gallery placements: {section_id}"
                    )
                ranks[section_id] = (
                    movement_position,
                    location_position,
                    storyline_id,
                    location_id,
                )
    return ranks


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


def _normalized_mapping(value: Any) -> dict[str, Any]:
    return {key.lower(): item for key, item in _mapping(value).items() if isinstance(key, str)}


def _mappings(value: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(value, dict):
        return tuple(item for item in value.values() if isinstance(item, dict))
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, dict))
    return ()


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        values = value.values()
    elif isinstance(value, list):
        values = value
    else:
        return ()
    return tuple(item for item in values if isinstance(item, str) and item)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _identifier(value: Any) -> str | None:
    text = _text(value)
    return text.lower() if text else None


def _integer(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _positive_integer(value: Mapping[str, Any], field: str, context: str) -> int:
    integer = _integer(value.get(field))
    if integer <= 0:
        raise ValueError(f"{context} has invalid {field}: {value.get(field)!r}")
    return integer


def _required_identifier(value: Mapping[str, Any], field: str, context: str) -> str:
    identifier = _identifier(value.get(field))
    if identifier is None:
        raise ValueError(f"{context} has invalid {field}: {value.get(field)!r}")
    return identifier


def _required_object(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{context} is not an object")
    return value


def _required_mapping_entry(
    values: Mapping[str, Any],
    raw_identifier: str,
    context: str,
) -> Mapping[str, Any]:
    identifier = raw_identifier.lower()
    if identifier not in values:
        raise ValueError(f"{context} is not declared: {identifier}")
    return _required_object(values[identifier], f"{context} {identifier}")


def _declared_mapping_identifier(
    value: Mapping[str, Any],
    field: str,
    mapping_key: str,
    context: str,
) -> str:
    declared = _required_identifier(value, field, context)
    normalized_key = mapping_key.lower()
    if declared != normalized_key:
        raise ValueError(
            f"{context} mapping key does not match {field}: "
            f"key={normalized_key} declared={declared}"
        )
    return declared


def _required_panel_identifier(
    value: Mapping[str, Any],
    field: str,
    context: str,
) -> str:
    identifier = _required_identifier(value, field, context)
    if "/" in identifier:
        raise ValueError(f"{context} panel ID contains reserved '/': {identifier!r}")
    return identifier


def _story_set_description(story_set: Mapping[str, Any]) -> str:
    for section in ("ssData", "mainlineData", "collectData"):
        description = _text(_at(story_set, section, "desc"))
        if description:
            return description
    return ""


def _gallery_art_category(value: Any) -> ArtCategory:
    source = _text(value).upper()
    if source == "BACKGROUND":
        return "background"
    if source == "IMAGE":
        return "image"
    raise ValueError(f"unknown gallery CG source: {value!r}")


def _movement_collection_id(section_id: str) -> str:
    return f"movement_section:{section_id}"


def _unique_id(base: str, used: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate
