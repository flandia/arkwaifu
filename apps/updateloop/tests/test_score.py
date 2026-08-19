from __future__ import annotations

import json
from pathlib import Path

import pytest

from arkwaifu_updateloop.locale.score import parse_score


def _write_excel(root: Path, name: str, value: object) -> None:
    path = root / "assets/torappu/dynamicassets/gamedata/excel" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_score_parser_preserves_every_declared_visual_and_video_link(tmp_path: Path):
    _write_excel(tmp_path, "activity_table.json", {"zoneToActivity": {}})
    _write_excel(
        tmp_path,
        "stage_table.json",
        {
            "stages": {},
            "storylines": {
                "StoryLine_UR": {
                    "storylineId": "StoryLine_UR",
                    "storylineType": "CONTINUE",
                    "sortId": 4,
                    "storylineName": "People, Us",
                    "storylineIconId": "StoryLine_Abbr_UR",
                    "storylineLogoId": "StoryLine_UR",
                    "backgroundId": "BG_MainLine_3",
                    "hasVideoToPlay": True,
                    "startTs": 123,
                    "locations": {
                        "before": {
                            "locationId": "Before",
                            "locationType": "BEFORE",
                            "sortId": 5,
                            "startTime": 123,
                            "presentStageId": "before-stage",
                            "unlockStageId": "before-unlock",
                            "relevantStorySetId": "Set_Main_17",
                            "mainlineSplitData": None,
                        },
                        "section": {
                            "locationId": "Section",
                            "locationType": "STORY_SET",
                            "sortId": 20,
                            "startTime": 125,
                            "presentStageId": "main_16-01",
                            "unlockStageId": "main_15-04",
                            "relevantStorySetId": "Set_Main_17",
                            "mainlineSplitData": None,
                        },
                        "mainline_3_split": {
                            "locationId": "mainline_3_split",
                            "locationType": "MAINLINE_SPLIT",
                            "sortId": 10,
                            "startTime": 124,
                            "presentStageId": None,
                            "unlockStageId": None,
                            "relevantStorySetId": None,
                            "mainlineSplitData": {
                                "iconId": "Act_3",
                                "subName": "NEXUS POINT OF FUTURE",
                            },
                        },
                        "after": {
                            "locationId": "After",
                            "locationType": "AFTER",
                            "sortId": 30,
                            "startTime": 126,
                            "presentStageId": "after-stage",
                            "unlockStageId": "after-unlock",
                            "relevantStorySetId": "Set_Main_17",
                            "mainlineSplitData": None,
                        },
                    },
                }
            },
            "storylineStorySets": {
                "Set_Main_17": {
                    "storySetId": "Set_Main_17",
                    "storySetType": "MAINLINE",
                    "sortByYear": 2,
                    "sortWithinYear": 7,
                    "kvImageId": "KV_Critical_Phase_Transition",
                    "titleImageId": "Title_Critical_Phase_Transition",
                    "haveVideoToPlay": True,
                    "backgroundId": "BG_MainLine_3",
                    "mainlineData": {
                        "zoneId": "main_17",
                        "decoImageId": "Deco_Critical_Phase_Transition",
                        "backgroundId": "StoryBG_Critical_Phase_Transition",
                        "desc": "Description",
                    },
                }
            },
        },
    )

    movements, sections = parse_score(
        tmp_path,
        {"main_17": "Critical Phase Transition"},
    )

    (movement,) = movements
    assert (
        movement.id,
        movement.movement_type,
        movement.name,
        movement.icon_asset_id,
        movement.logo_asset_id,
        movement.background_asset_id,
        movement.has_video,
        movement.start_time,
    ) == (
        "storyline_ur",
        "continue",
        "People, Us",
        "StoryLine_Abbr_UR",
        "StoryLine_UR",
        "BG_MainLine_3",
        True,
        123,
    )
    assert [location.id for location in movement.locations] == [
        "before",
        "mainline_3_split",
        "section",
        "after",
    ]
    before, split, location, after = movement.locations
    assert (before.location_type, before.section_id) == ("before", "set_main_17")
    assert (
        split.position,
        split.location_type,
        split.divider_icon_asset_id,
        split.divider_sub_name,
        split.video_id,
        split.section_id,
    ) == (
        1,
        "divider",
        "Act_3",
        "NEXUS POINT OF FUTURE",
        "bg_mainline_3",
        None,
    )
    assert (location.position, location.section_id, location.video_id) == (
        2,
        "set_main_17",
        None,
    )
    assert (after.location_type, after.section_id) == ("after", "set_main_17")

    (section,) = sections
    assert (
        section.id,
        section.collection_id,
        section.section_type,
        section.name,
        section.review_group_id,
        section.key_visual_asset_id,
        section.title_asset_id,
        section.background_asset_id,
        section.decoration_asset_id,
        section.retro_background_asset_id,
        section.description,
        section.has_video,
    ) == (
        "set_main_17",
        "section:set_main_17",
        "main_theme",
        "Critical Phase Transition",
        "main_17",
        "KV_Critical_Phase_Transition",
        "Title_Critical_Phase_Transition",
        "BG_MainLine_3",
        "Deco_Critical_Phase_Transition",
        "StoryBG_Critical_Phase_Transition",
        "Description",
        True,
    )


def test_score_review_mapping_uses_each_deterministic_metadata_path(tmp_path: Path):
    _write_excel(
        tmp_path,
        "activity_table.json",
        {"zoneToActivity": {"hidden_zone": "ACT_INVERSE"}},
    )
    _write_excel(
        tmp_path,
        "stage_table.json",
        {
            "storylines": {
                "movement": {
                    "storylineId": "movement",
                    "storylineType": "DISCRETE",
                    "locations": {
                        section_id: {
                            "locationId": section_id,
                            "locationType": "STORY_SET",
                            "sortId": position,
                            "relevantStorySetId": section_id,
                        }
                        for position, section_id in enumerate(
                            ("direct_activity", "direct_zone", "inverse")
                        )
                    },
                }
            },
            "stages": {
                "inverse_stage": {
                    "stageId": "main_12-01",
                    "zoneId": "hidden_zone",
                }
            },
            "storylineStorySets": {
                "direct_activity": {
                    "storySetId": "direct_activity",
                    "storySetType": "SS",
                    "relevantActivityId": "ACT_EVENT",
                    "ssData": {},
                },
                "direct_zone": {
                    "storySetId": "direct_zone",
                    "storySetType": "MAINLINE",
                    "mainlineData": {"zoneId": "MAIN_5"},
                },
                "inverse": {
                    "storySetId": "inverse",
                    "storySetType": "MAINLINE",
                    "relevantActivityId": "ACT_INVERSE",
                    "mainlineData": {},
                },
            },
        },
    )

    _, sections = parse_score(
        tmp_path,
        {
            "act_event": "Event",
            "main_5": "Episode 5",
            "main_12": "Episode 12",
        },
    )

    assert {section.id: section.review_group_id for section in sections} == {
        "direct_activity": "act_event",
        "direct_zone": "main_5",
        "inverse": "main_12",
    }


def test_score_review_mapping_rejects_an_ambiguous_inverse(tmp_path: Path):
    _write_excel(
        tmp_path,
        "activity_table.json",
        {
            "zoneToActivity": {
                "zone_12": "act_inverse",
                "zone_13": "act_inverse",
            }
        },
    )
    _write_excel(
        tmp_path,
        "stage_table.json",
        {
            "storylines": {},
            "stages": {
                "stage_12": {"stageId": "main_12-01", "zoneId": "zone_12"},
                "stage_13": {"stageId": "main_13-01", "zoneId": "zone_13"},
            },
            "storylineStorySets": {
                "ambiguous": {
                    "storySetId": "ambiguous",
                    "storySetType": "MAINLINE",
                    "relevantActivityId": "act_inverse",
                    "mainlineData": {},
                }
            },
        },
    )

    with pytest.raises(ValueError, match="multiple main-story review groups"):
        parse_score(
            tmp_path,
            {"main_12": "Episode 12", "main_13": "Episode 13"},
        )


@pytest.mark.parametrize("case", ["missing", "duplicate", "dangling"])
def test_score_parser_rejects_an_invalid_canonical_placement_graph(
    tmp_path: Path,
    case: str,
):
    locations: dict[str, object] = {}
    if case != "missing":
        locations["canonical"] = {
            "locationId": "canonical",
            "locationType": "STORY_SET",
            "relevantStorySetId": "section" if case != "dangling" else "unknown",
        }
    if case == "duplicate":
        locations["duplicate"] = {
            "locationId": "duplicate",
            "locationType": "STORY_SET",
            "relevantStorySetId": "section",
        }
    _write_excel(tmp_path, "activity_table.json", {"zoneToActivity": {}})
    _write_excel(
        tmp_path,
        "stage_table.json",
        {
            "stages": {},
            "storylines": {
                "movement": {
                    "storylineId": "movement",
                    "storylineType": "DISCRETE",
                    "locations": locations,
                }
            },
            "storylineStorySets": {
                "section": {
                    "storySetId": "section",
                    "storySetType": "SS",
                    "relevantActivityId": "activity",
                    "ssData": {},
                }
            },
        },
    )

    message = "unknown Section" if case == "dangling" else "exactly one canonical"
    with pytest.raises(ValueError, match=message):
        parse_score(tmp_path, {"activity": "Event"})


@pytest.mark.parametrize("case", ["storyline", "story_set", "location"])
def test_score_mapping_keys_must_match_declared_ids(tmp_path: Path, case: str):
    movement_id = "movement" if case != "storyline" else "different"
    section_id = "section" if case != "story_set" else "different"
    location_id = "location" if case != "location" else "different"
    _write_excel(tmp_path, "activity_table.json", {"zoneToActivity": {}})
    _write_excel(
        tmp_path,
        "stage_table.json",
        {
            "stages": {},
            "storylines": {
                "movement": {
                    "storylineId": movement_id,
                    "storylineType": "DISCRETE",
                    "locations": {
                        "location": {
                            "locationId": location_id,
                            "locationType": "STORY_SET",
                            "relevantStorySetId": "section",
                        }
                    },
                }
            },
            "storylineStorySets": {
                "section": {
                    "storySetId": section_id,
                    "storySetType": "SS",
                    "relevantActivityId": "activity",
                    "ssData": {},
                }
            },
        },
    )

    with pytest.raises(ValueError, match="mapping key does not match"):
        parse_score(tmp_path, {"activity": "Event"})
