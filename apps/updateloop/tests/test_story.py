from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from arkwaifu_updateloop.locale import (
    normalize_character_id,
    parse_directives,
    parse_story_data,
)
from arkwaifu_updateloop.locale import story as story_module


def _write_json(root: Path, relative: str, value: object) -> None:
    path = root / "assets/torappu/dynamicassets/gamedata" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _write_story(root: Path, relative: str, value: str) -> None:
    path = root / "assets/torappu/dynamicassets/gamedata/story" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_empty_story_catalogs(root: Path) -> None:
    _write_json(root, "excel/roguelike_topic_table.json", {"topics": {}, "details": {}})
    _write_json(root, "excel/sandbox_perm_table.json", {"basicInfo": {}, "detail": {}})
    _write_json(root, "excel/stage_table.json", {})
    _write_json(root, "excel/activity_table.json", {})


def _archive_groups(root: Path):
    excel = root / "assets/torappu/dynamicassets/gamedata/excel"
    for name in ("stage_table.json", "activity_table.json"):
        if not (excel / name).exists():
            _write_json(root, f"excel/{name}", {})
    _movements, _sections, archives = parse_story_data(root)
    return archives


def test_directive_parameters_keep_quoted_commas():
    (directive,) = parse_directives('[image(image="event",label="one,two")]')

    assert directive.name == "image"
    assert directive.params == {"image": "event", "label": "one,two"}


def test_directive_allows_space_before_closing_bracket():
    (directive,) = parse_directives('[charslot(slot="r",name="char")  ]')

    assert directive.name == "charslot"
    assert directive.params == {"slot": "r", "name": "char"}


@pytest.mark.parametrize(
    "raw",
    ['[name="Closure",delay=0.1]', "[name='Closure',delay=0.1]"],
)
def test_speaker_directive_keeps_optional_parameters(raw: str):
    (directive,) = parse_directives(raw)

    assert directive.name == ""
    assert directive.params == {"name": "Closure", "delay": "0.1"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("char", "char#1$1"),
        ("char#2", "char#2$1"),
        ("char$3", "char#1$3"),
        (" char#2$3 ", "char#2$3"),
        ("char#01$1", "char#1$1"),
        ("char#1$01", "char#1$1"),
        ("char#3 $1", "char#3$1"),
        ("$ill_amiya_normal", ""),
        ("char_empty", ""),
    ],
)
def test_character_identifier_defaults(raw: str, expected: str):
    assert normalize_character_id(raw) == expected


def test_story_parser_preserves_order_metadata_and_character_names(tmp_path: Path):
    _write_empty_story_catalogs(tmp_path)
    _write_json(
        tmp_path,
        "excel/story_review_table.json",
        {
            "group": {
                "id": "GROUP",
                "name": "Main",
                "actType": "ACTIVITY_STORY",
                "infoUnlockDatas": [
                    {
                        "storyId": "STORY_1",
                        "storyCode": "1-1",
                        "storyName": "Opening",
                        "storyInfo": "info/opening",
                        "storyTxt": "text/opening",
                        "avgTag": "Before Operation",
                    }
                ],
            }
        },
    )
    _write_json(
        tmp_path,
        "excel/story_review_meta_table.json",
        {
            "actArchiveResData": {
                "pics": {
                    "event": {
                        "assetPath": "EVENT",
                        "desc": "Title",
                        "picDescription": "Subtitle",
                    }
                }
            }
        },
    )
    _write_story(tmp_path, "[uc]info/opening.txt", "Story info")
    _write_story(
        tmp_path,
        "text/opening.txt",
        '[background(image="BG_ROOM")] \n'
        '[image(image="EVENT")] \n'
        '[character(name="CHAR_TEST#2",focus="1")] \n'
        '[name="Amiya"] \n'
        '[charslot(slot="1",posfrom="0,0",posto="100,0")] \n'
        '[name="Doctor"] \n'
        '[charslot(name="left",posfrom="0,0",posto="-200,0")] \n'
        '[name="Kal\'tsit"] \n'
        '[character(name="CHAR_TEST#2",focus="1")] \n'
        '[name="Closure"] \n'
        '[charslot(slot="1",name="char_empty")] \n'
        '[name="Nobody"] \n'
        '[showitem(image="ITEM_ONE")] ',
    )

    (group,) = _archive_groups(tmp_path)
    (story,) = group.stories

    assert (group.id, group.archive_kind, group.story_type) == (
        "group",
        "events",
        "side_story",
    )
    assert (story.id, story.collection_id, story.tag) == (
        "story_1",
        "archive_group:group",
        "before",
    )
    assert story.info == "Story info"
    assert [reference.art_id for reference in story.art_references] == [
        "bg_room",
        "event",
        "item_one",
        "char_test#2$1",
    ]
    assert story.art_references[1].title == "Title"
    assert story.art_references[1].subtitle == "Subtitle"
    assert story.art_references[3].names == ("Amiya", "Doctor", "Kal'tsit", "Closure")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("storyTxt", "../outside"),
        ("storyTxt", "/outside"),
        ("storyTxt", "C:/outside"),
        ("storyTxt", "folder\\outside"),
        ("storyInfo", "safe/../../../outside"),
        ("storyInfo", "C:/outside"),
        ("storyInfo", "safe\\..\\..\\outside"),
    ],
)
def test_story_parser_rejects_unsafe_local_paths(tmp_path: Path, field: str, value: str):
    _write_empty_story_catalogs(tmp_path)
    story = {
        "storyId": "story",
        "storyTxt": "opening",
        "avgTag": "Before Operation",
        field: value,
    }
    _write_json(
        tmp_path,
        "excel/story_review_table.json",
        {
            "group": {
                "id": "group",
                "name": "Main",
                "actType": "MAIN_STORY",
                "infoUnlockDatas": [story],
            }
        },
    )
    _write_json(tmp_path, "excel/story_review_meta_table.json", {})

    with pytest.raises(ValueError, match=r"unsafe (story|game-data) path"):
        parse_story_data(tmp_path)


def test_unclaimed_main_story_review_group_is_an_invariant_failure(tmp_path: Path):
    _write_empty_story_catalogs(tmp_path)
    _write_json(
        tmp_path,
        "excel/story_review_table.json",
        {
            "main_0": {
                "id": "main_0",
                "name": "Unclaimed main story",
                "actType": "MAIN_STORY",
                "infoUnlockDatas": [
                    {
                        "storyId": "main_00-01",
                        "storyTxt": "main_00-01",
                        "avgTag": "Before Operation",
                    }
                ],
            }
        },
    )
    _write_json(tmp_path, "excel/story_review_meta_table.json", {})
    _write_story(tmp_path, "main_00-01.txt", '[name="Amiya"]')

    with pytest.raises(ValueError, match="main-story review group is not owned"):
        parse_story_data(tmp_path)


@pytest.mark.parametrize(
    "relative",
    ["../outside.txt", "/outside.txt", "C:/outside.txt", "folder\\outside.txt"],
)
def test_game_data_path_rejects_platform_specific_escape_forms(
    tmp_path: Path,
    relative: str,
):
    with pytest.raises(ValueError, match="unsafe game-data path"):
        story_module._game_data_path(tmp_path, relative)


def test_story_parser_resolves_character_variables(tmp_path: Path):
    _write_empty_story_catalogs(tmp_path)
    _write_json(
        tmp_path,
        "excel/story_review_table.json",
        {
            "group": {
                "id": "group",
                "name": "Tutorial",
                "actType": "ACTIVITY_STORY",
                "infoUnlockDatas": [
                    {
                        "storyId": "story",
                        "storyTxt": "tutorial",
                        "avgTag": "Before Operation",
                    }
                ],
            }
        },
    )
    _write_json(tmp_path, "excel/story_review_meta_table.json", {})
    _write_json(
        tmp_path,
        "story/story_variables.json",
        {"ill_amiya_normal": "char_002_amiya_1"},
    )
    _write_story(
        tmp_path,
        "tutorial.txt",
        '[character(name="$ill_amiya_normal")]\n[name="Amiya"]',
    )

    (group,) = _archive_groups(tmp_path)

    (reference,) = group.stories[0].art_references
    assert reference.art_id == "char_002_amiya_1#1$1"
    assert reference.names == ("Amiya",)


def test_missing_optional_info_is_empty(tmp_path: Path):
    _write_empty_story_catalogs(tmp_path)
    _write_json(
        tmp_path,
        "excel/story_review_table.json",
        {
            "group": {
                "id": "group",
                "name": "Event",
                "actType": "ACTIVITY_STORY",
                "infoUnlockDatas": [
                    {
                        "storyId": "story",
                        "storyTxt": "story",
                        "avgTag": "行动后",
                    }
                ],
            }
        },
    )
    _write_json(tmp_path, "excel/story_review_meta_table.json", {})
    _write_story(tmp_path, "story.txt", "")

    (group,) = _archive_groups(tmp_path)

    assert group.stories[0].info == ""
    assert group.stories[0].tag == "after"


def test_missing_story_text_warns_and_keeps_story(tmp_path: Path, caplog):
    _write_empty_story_catalogs(tmp_path)
    _write_json(
        tmp_path,
        "excel/story_review_table.json",
        {
            "group": {
                "id": "group",
                "name": "Event",
                "actType": "ACTIVITY_STORY",
                "infoUnlockDatas": [
                    {
                        "storyId": "STORY",
                        "storyTxt": "missing/story",
                        "avgTag": "After Operation",
                    }
                ],
            }
        },
    )
    _write_json(tmp_path, "excel/story_review_meta_table.json", {})

    with caplog.at_level(logging.WARNING, logger="arkwaifu_updateloop.incomplete_upstream"):
        (group,) = _archive_groups(tmp_path)

    (story,) = group.stories
    assert story.id == "story"
    assert story.art_references == ()
    assert "story_id=story" in caplog.text
    assert "gamedata/story/missing/story.txt" in caplog.text


def test_story_parser_classifies_records_endings_reclamation_and_others(tmp_path: Path):
    _write_json(
        tmp_path,
        "excel/story_review_table.json",
        {
            "record": {
                "id": "record",
                "name": "Operator Record",
                "actType": "NONE",
                "infoUnlockDatas": [
                    {
                        "storyId": "record-story",
                        "storyTxt": "obt/memory/record",
                        "storyInfo": "obt/memory/record",
                        "avgTag": "Interlude",
                    },
                    {
                        "storyId": "record-sandbox-story",
                        "storyTxt": "obt/sandboxperm/sandbox_1/reviewed",
                        "storyInfo": "",
                        "avgTag": "Interlude",
                    },
                ],
            }
        },
    )
    _write_json(
        tmp_path,
        "excel/story_review_meta_table.json",
        {
            "actArchiveResData": {
                "pics": {},
                "avgs": {
                    "intro": {
                        "id": "intro",
                        "desc": "Opening",
                        "contentPath": "Obt/Roguelike/RO1/level_rogue1_entry",
                    },
                    "ending_2": {
                        "id": "ending_2",
                        "desc": "Second ending",
                        "contentPath": "Obt/Roguelike/RO1/level_rogue1_ending_2",
                    },
                    "ending_1": {
                        "id": "ending_1",
                        "desc": "First ending",
                        "rawBrief": "Ending summary",
                        "contentPath": "Obt/Roguelike/RO1/level_rogue1_ending_1",
                    },
                },
            }
        },
    )
    _write_json(
        tmp_path,
        "excel/roguelike_topic_table.json",
        {
            "topics": {
                "rogue_2": {"id": "rogue_2", "name": "Second Theme", "sort": 2},
                "rogue_1": {"id": "rogue_1", "name": "Theme", "sort": 1},
            },
            "details": {
                "rogue_1": {
                    "monthSquad": {"squad": {"chatId": "month_chat_1"}},
                    "archiveComp": {
                        "chat": {
                            "chat": {
                                "month_chat_1": {
                                    "chatItemList": [
                                        {
                                            "chatStoryId": "obt/rogue/month/first",
                                        }
                                    ],
                                },
                                "unrelated_chat": {
                                    "chatItemList": [
                                        {
                                            "chatStoryId": "obt/rogue/month/unrelated",
                                        }
                                    ],
                                },
                            }
                        }
                    },
                },
                "rogue_2": {
                    "monthSquad": {"squad": {"chatId": "second_chat"}},
                    "archiveComp": {
                        "chat": {
                            "chat": {
                                "second_chat": {
                                    "chatItemList": [
                                        {
                                            "chatStoryId": "obt/rogue/month/second_theme",
                                        }
                                    ],
                                }
                            }
                        },
                        "endbook": {
                            "endbook": {
                                "ending_2": {
                                    "sortId": 2,
                                    "endingId": "rogue-2-ending-2",
                                    "title": "Later ending",
                                    "avgId": "Obt/Roguelike/RO2/level_rogue2_ending_2",
                                },
                                "ending_1": {
                                    "sortId": 1,
                                    "endingId": "rogue-2-ending-1",
                                    "title": "Earlier ending",
                                    "avgId": "Obt/Roguelike/RO2/level_rogue2_ending_1",
                                },
                            }
                        },
                    },
                },
            },
        },
    )
    _write_json(
        tmp_path,
        "excel/sandbox_perm_table.json",
        {
            "basicInfo": {
                "sandbox_1": {
                    "topicId": "sandbox_1",
                    "topicTemplate": "SANDBOX_V2",
                    "topicName": "Reclamation",
                    "sortId": 1,
                }
            },
            "detail": {
                "SANDBOX_V2": {
                    "sandbox_1": {
                        "archiveQuestData": {
                            "story_1": {
                                "sortId": 1,
                                "desc": "Chapter description",
                                "avgDataList": [
                                    {
                                        "avgId": "obt/sandboxperm/sandbox_1/entry",
                                        "avgName": "Arrival",
                                    },
                                    {
                                        "avgId": "obt/sandboxperm/sandbox_1/visual",
                                        "avgName": "Visible story",
                                    },
                                ],
                            }
                        }
                    }
                }
            },
        },
    )
    _write_story(tmp_path, "[uc]obt/memory/record.txt", "Record summary")
    _write_story(tmp_path, "[uc]orphan.txt", "Not a playable story")
    _write_story(tmp_path, "obt/memory/record.txt", '[image(image="record")]')
    _write_story(tmp_path, "obt/rogue/month/first.txt", '[image(image="monthly")]')
    _write_story(tmp_path, "obt/rogue/month/second_theme.txt", "")
    _write_story(
        tmp_path,
        "obt/rogue/month/unrelated.txt",
        '[image(image="unrelated")]',
    )
    _write_story(
        tmp_path,
        "obt/roguelike/ro1/level_rogue1_entry.txt",
        '[background(image="opening")]',
    )
    _write_story(
        tmp_path,
        "obt/roguelike/ro1/ref/ref_rogue_1.txt",
        '[image(image="preloaded-only")]',
    )
    _write_story(
        tmp_path,
        "obt/roguelike/ro1/level_rogue1_ending_1.txt",
        '[background(image="ending-one")]',
    )
    _write_story(
        tmp_path,
        "obt/roguelike/ro1/level_rogue1_ending_2.txt",
        '[character(name="ending-two")]',
    )
    _write_story(
        tmp_path,
        "obt/roguelike/ro2/level_rogue2_ending_1.txt",
        '[image(image="second-theme-one")]',
    )
    _write_story(
        tmp_path,
        "obt/roguelike/ro2/level_rogue2_ending_2.txt",
        '[image(image="second-theme-two")]',
    )
    _write_story(
        tmp_path,
        "obt/roguelike/ro2/level_rogue2_entry.txt",
        '[background(image="second-theme-opening")]',
    )
    _write_story(tmp_path, "obt/sandboxperm/sandbox_1/entry.txt", "")
    _write_story(
        tmp_path,
        "obt/sandboxperm/sandbox_1/visual.txt",
        '[background(image="reclamation")]',
    )
    _write_story(tmp_path, "obt/sandboxperm/sandbox_1/reviewed.txt", "")
    _write_story(
        tmp_path,
        "obt/sandboxperm/sandbox_1/traininglevel/tutorial.txt",
        "",
    )
    _write_story(tmp_path, "obt/sandboxperm/sandbox_1/uiavg/help.txt", "")
    _write_story(
        tmp_path,
        "obt/sandboxperm/sandbox_1/sandbox_1_challenge_mode_guide.txt",
        "",
    )
    _write_story(tmp_path, "misc/free.txt", '[background(image="free")]')

    groups = _archive_groups(tmp_path)
    by_type = {
        archive_kind: [group for group in groups if group.archive_kind == archive_kind]
        for archive_kind in {group.archive_kind for group in groups}
    }

    (record,) = by_type["operator_record"]
    assert record.stories[0].info == "Record summary"
    assert [story.id for story in record.stories] == [
        "record-story",
        "record-sandbox-story",
    ]
    endings = by_type["integrated_strategies"]
    assert [group.name for group in endings] == ["Theme", "Second Theme"]
    assert [(story.code, story.name, story.info) for story in endings[0].stories] == [
        ("ending_1", "First ending", "Ending summary"),
        ("ending_2", "Second ending", ""),
    ]
    assert [(story.code, story.name) for story in endings[1].stories] == [
        ("rogue-2-ending-1", "Earlier ending"),
        ("rogue-2-ending-2", "Later ending"),
    ]
    (reclamation,) = by_type["reclamation_algorithm"]
    assert reclamation.name == "Reclamation"
    assert [(story.name, story.info) for story in reclamation.stories] == [
        ("Visible story", "Chapter description")
    ]

    other_ids = {story.id for group in by_type["others"] for story in group.stories}
    assert other_ids == {
        "others:misc:free",
        "others:obt:rogue:month:unrelated",
        "others:obt:sandboxperm:sandbox_1:sandbox_1_challenge_mode_guide",
        "others:obt:sandboxperm:sandbox_1:traininglevel:tutorial",
        "others:obt:sandboxperm:sandbox_1:uiavg:help",
    }
    assert not any(story_id.startswith("others:obt:roguelike:ro1:") for story_id in other_ids)
    assert not any(story_id.startswith("others:obt:roguelike:ro2:") for story_id in other_ids)
    all_story_ids = [story.id for group in groups for story in group.stories]
    assert len(all_story_ids) == len(set(all_story_ids))
