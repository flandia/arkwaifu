from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from arkwaifu_updateloop.locale import (
    normalize_character_id,
    parse_directives,
    parse_story_groups,
)


def _write_json(root: Path, relative: str, value: object) -> None:
    path = root / "assets/torappu/dynamicassets/gamedata" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _write_story(root: Path, relative: str, value: str) -> None:
    path = root / "assets/torappu/dynamicassets/gamedata/story" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


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
    _write_json(
        tmp_path,
        "excel/story_review_table.json",
        {
            "group": {
                "id": "GROUP",
                "name": "Main",
                "actType": "MAIN_STORY",
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
        '[charslot(slot="1",name="char_empty")] \n'
        '[name="Nobody"] \n'
        '[showitem(image="ITEM_ONE")] ',
    )

    (group,) = parse_story_groups(tmp_path)
    (story,) = group.stories

    assert (group.id, group.group_type) == ("group", "main_story")
    assert (story.id, story.group_id, story.tag) == ("story_1", "group", "before")
    assert story.info == "Story info"
    assert [reference.art_id for reference in story.art_references] == [
        "bg_room",
        "event",
        "item_one",
        "char_test#2$1",
    ]
    assert story.art_references[1].title == "Title"
    assert story.art_references[1].subtitle == "Subtitle"
    assert story.art_references[3].names == ("Amiya", "Doctor", "Kal'tsit")


def test_story_parser_resolves_character_variables(tmp_path: Path):
    _write_json(
        tmp_path,
        "excel/story_review_table.json",
        {
            "group": {
                "id": "group",
                "name": "Tutorial",
                "actType": "MAIN_STORY",
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

    (group,) = parse_story_groups(tmp_path)

    (reference,) = group.stories[0].art_references
    assert reference.art_id == "char_002_amiya_1#1$1"
    assert reference.names == ("Amiya",)


def test_missing_optional_info_is_empty(tmp_path: Path):
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

    (group,) = parse_story_groups(tmp_path)

    assert group.stories[0].info == ""
    assert group.stories[0].tag == "after"


def test_missing_story_text_warns_and_keeps_story(tmp_path: Path, caplog):
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
        (group,) = parse_story_groups(tmp_path)

    (story,) = group.stories
    assert story.id == "story"
    assert story.art_references == ()
    assert "story_id=story" in caplog.text
    assert "gamedata/story/missing/story.txt" in caplog.text
