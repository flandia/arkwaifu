"""Parse the localized Score hierarchy from ``stage_table.json``."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from ..domain import (
    Movement,
    MovementLocation,
    MovementLocationType,
    MovementSection,
    MovementSectionType,
    MovementType,
)

_DATA_ROOT = Path("assets/torappu/dynamicassets/gamedata")
_INCOMPLETE_UPSTREAM_LOGGER = logging.getLogger("arkwaifu_updateloop.incomplete_upstream")
_SECTION_TYPES: dict[str, MovementSectionType] = {
    "MAINLINE": "main_theme",
    "SS": "side_story",
    "COLLECT": "vignette",
}
_LOCATION_TYPES: dict[str, MovementLocationType] = {
    "BEFORE": "before",
    "AFTER": "after",
    "MAINLINE_SPLIT": "mainline_split",
    "STORY_SET": "story_set",
}
_MOVEMENT_TYPES = frozenset({"continue", "discrete"})
_MAINLINE_SPLIT = re.compile(r"^mainline_(\d+)_split$", re.IGNORECASE)


def parse_score(
    root: Path,
    review_names: Mapping[str, str],
) -> tuple[tuple[Movement, ...], tuple[MovementSection, ...]]:
    """Return every Movement, location, and Story Set in one locale snapshot."""

    stage = _mapping(_read_json(root / _DATA_ROOT / "excel/stage_table.json"))
    activity = _mapping(_read_json(root / _DATA_ROOT / "excel/activity_table.json"))
    sections = _parse_sections(stage, activity, review_names)
    movements = _parse_movements(stage)
    _validate_placement_graph(movements, sections)
    return movements, sections


def _validate_placement_graph(
    movements: tuple[Movement, ...],
    sections: tuple[MovementSection, ...],
) -> None:
    """Require every Section to have one canonical, internally valid placement."""

    section_ids = {section.id for section in sections}
    canonical_counts = dict.fromkeys(section_ids, 0)
    for movement in movements:
        for location in movement.locations:
            if location.section_id is None:
                if location.location_type in {"story_set", "before", "after"}:
                    raise ValueError(
                        "Movement placement has no Movement Section: "
                        f"movement_id={movement.id} location_id={location.id}"
                    )
                continue
            if location.section_id not in section_ids:
                raise ValueError(
                    "Movement placement references an unknown Movement Section: "
                    f"movement_id={movement.id} location_id={location.id} "
                    f"section_id={location.section_id}"
                )
            if location.location_type == "story_set":
                canonical_counts[location.section_id] += 1

    missing = sorted(section_id for section_id, count in canonical_counts.items() if count == 0)
    duplicates = sorted(section_id for section_id, count in canonical_counts.items() if count > 1)
    if missing or duplicates:
        raise ValueError(
            "Movement Sections must have exactly one canonical STORY_SET placement: "
            f"missing={missing} duplicates={duplicates}"
        )


def _parse_movements(stage: Mapping[str, Any]) -> tuple[Movement, ...]:
    raw_movements = _mapping(stage.get("storylines"))
    ordered = sorted(
        raw_movements.items(),
        key=lambda item: (_integer(_at(item[1], "sortId")), item[0].lower()),
    )
    movements: list[Movement] = []
    for position, (raw_id, value) in enumerate(ordered):
        raw = _mapping(value)
        movement_id = _mapping_identifier(
            raw_id,
            raw.get("storylineId"),
            context="Movement",
        )
        movement_type = _text(raw.get("storylineType")).lower()
        if movement_type not in _MOVEMENT_TYPES:
            raise ValueError(f"unknown Movement type: {movement_type!r}")
        has_video = _boolean(raw.get("hasVideoToPlay"))
        ordered_locations = sorted(
            _mapping(raw.get("locations")).items(),
            key=lambda item: (_integer(_at(item[1], "sortId")), item[0].lower()),
        )
        locations = tuple(
            _location(movement_id, has_video, index, location_id, location)
            for index, (location_id, location) in enumerate(ordered_locations)
        )
        movements.append(
            Movement(
                id=movement_id,
                position=position,
                movement_type=cast(MovementType, movement_type),
                name=_text(raw.get("storylineName")),
                icon_asset_id=_identifier(raw.get("storylineIconId")),
                logo_asset_id=_identifier(raw.get("storylineLogoId")),
                background_asset_id=_identifier(raw.get("backgroundId")),
                has_video=has_video,
                start_time=_integer(raw.get("startTs")),
                locations=locations,
            )
        )
    return tuple(movements)


def _location(
    movement_id: str,
    movement_has_video: bool,
    position: int,
    raw_id: str,
    value: Any,
) -> MovementLocation:
    raw = _mapping(value)
    location_id = _mapping_identifier(
        raw_id,
        raw.get("locationId"),
        context=f"Movement location in {movement_id}",
    )
    raw_type = _text(raw.get("locationType"))
    try:
        location_type = _LOCATION_TYPES[raw_type]
    except KeyError as error:
        raise ValueError(f"unknown Movement location type: {raw_type!r}") from error
    split = _mapping(raw.get("mainlineSplitData"))
    split_match = _MAINLINE_SPLIT.fullmatch(location_id)
    video_id = None
    if movement_has_video and split_match is not None:
        video_id = f"bg_mainline_{int(split_match.group(1))}"
    section_id = _identifier(raw.get("relevantStorySetId"))
    if location_type == "mainline_split":
        section_id = None
    return MovementLocation(
        id=location_id,
        position=position,
        location_type=location_type,
        sort_id=_integer(raw.get("sortId")),
        start_time=_integer(raw.get("startTime")),
        present_stage_id=_optional_text(raw.get("presentStageId")),
        unlock_stage_id=_optional_text(raw.get("unlockStageId")),
        section_id=section_id,
        split_icon_asset_id=_identifier(split.get("iconId")),
        split_sub_name=_text(split.get("subName")) if location_type == "mainline_split" else None,
        video_id=video_id,
    )


def _parse_sections(
    stage: Mapping[str, Any],
    activity: Mapping[str, Any],
    review_names: Mapping[str, str],
) -> tuple[MovementSection, ...]:
    raw_sections = _mapping(stage.get("storylineStorySets"))
    normalized_review_names = {key.lower(): value for key, value in review_names.items()}
    zone_to_activity = {
        zone_id.lower(): activity_id.lower()
        for zone_id, activity_id in _mapping(activity.get("zoneToActivity")).items()
        if isinstance(zone_id, str) and isinstance(activity_id, str)
    }
    stages = _mapping(stage.get("stages"))

    sections = []
    for raw_id, value in raw_sections.items():
        raw = _mapping(value)
        section_id = _mapping_identifier(
            raw_id,
            raw.get("storySetId"),
            context="Movement Section",
        )
        raw_type = _text(raw.get("storySetType"))
        try:
            section_type = _SECTION_TYPES[raw_type]
        except KeyError as error:
            raise ValueError(f"unknown Movement Section type: {raw_type!r}") from error

        mainline = _mapping(raw.get("mainlineData"))
        side_story = _mapping(raw.get("ssData"))
        vignette = _mapping(raw.get("collectData"))
        detail = mainline or side_story or vignette
        review_group_id = _review_group_id(
            raw,
            mainline,
            normalized_review_names,
            zone_to_activity,
            stages,
        )
        name = normalized_review_names.get(review_group_id or "", "")
        if review_group_id is None:
            _INCOMPLETE_UPSTREAM_LOGGER.warning(
                "Movement Section has no matching review group; continuing with an empty collection "
                "section_id=%s",
                section_id,
            )
        sections.append(
            MovementSection(
                id=section_id,
                collection_id=f"movement_section:{section_id}",
                section_type=section_type,
                name=name,
                review_group_id=review_group_id,
                sort_by_year=_integer(raw.get("sortByYear")),
                sort_within_year=_integer(raw.get("sortWithinYear")),
                key_visual_asset_id=_identifier(raw.get("kvImageId")),
                title_asset_id=_identifier(raw.get("titleImageId")),
                background_asset_id=_identifier(raw.get("backgroundId")),
                decoration_asset_id=_identifier(mainline.get("decoImageId")),
                retro_background_asset_id=_identifier(detail.get("backgroundId")),
                description=_text(detail.get("desc")),
                has_video=_boolean(raw.get("haveVideoToPlay")),
                stories=(),
            )
        )
    return tuple(sections)


def _review_group_id(
    section: Mapping[str, Any],
    mainline: Mapping[str, Any],
    review_names: Mapping[str, str],
    zone_to_activity: Mapping[str, str],
    stages: Mapping[str, Any],
) -> str | None:
    relevant_activity_id = _identifier(section.get("relevantActivityId"))
    candidates = (relevant_activity_id, _identifier(mainline.get("zoneId")))
    for candidate in candidates:
        if candidate in review_names:
            return candidate

    if relevant_activity_id is None:
        return None
    activity_zones = {
        zone_id
        for zone_id, activity_id in zone_to_activity.items()
        if activity_id == relevant_activity_id
    }
    mainline_groups: set[str] = set()
    for raw_stage_id, value in stages.items():
        raw_stage = _mapping(value)
        if _identifier(raw_stage.get("zoneId")) not in activity_zones:
            continue
        stage_id = (_text(raw_stage.get("stageId")) or raw_stage_id).lower()
        match = re.match(r"^main_(\d+)", stage_id)
        if match is None:
            continue
        group_id = f"main_{int(match.group(1))}"
        if group_id in review_names:
            mainline_groups.add(group_id)
    if len(mainline_groups) == 1:
        return next(iter(mainline_groups))
    if len(mainline_groups) > 1:
        section_id = _identifier(section.get("storySetId")) or "<unknown>"
        raise ValueError(
            "Movement Section activity maps to multiple main-story review groups: "
            f"section_id={section_id} activity_id={relevant_activity_id} "
            f"groups={sorted(mainline_groups)}"
        )
    return None


def _read_json(path: Path) -> Any:
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


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _identifier(value: Any) -> str | None:
    text = _optional_text(value)
    return text.lower() if text is not None else None


def _mapping_identifier(raw_id: str, declared: Any, *, context: str) -> str:
    """Require a mapping key and its optional declared identifier to agree."""

    mapping_id = raw_id.lower()
    declared_id = _identifier(declared)
    if declared_id is not None and declared_id != mapping_id:
        raise ValueError(
            f"{context} mapping key does not match declared identifier: "
            f"key={mapping_id} declared={declared_id}"
        )
    return declared_id or mapping_id


def _integer(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _boolean(value: Any) -> bool:
    return value if isinstance(value, bool) else False
