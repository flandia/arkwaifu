from __future__ import annotations

import json
from pathlib import Path

from arkwaifu_updateloop.locale import parse_galleries


def _write(root: Path, name: str, value: object) -> None:
    path = root / "assets/torappu/dynamicassets/gamedata/excel" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _base(root: Path) -> None:
    _write(root, "replicate_table.json", {})
    _write(root, "roguelike_topic_table.json", {"topics": {}})


def test_missing_legacy_detail_falls_back_to_story_set(tmp_path: Path):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {
            "actArchiveResData": {
                "pics": {
                    "pic1": {
                        "id": "pic1",
                        "desc": "Picture 1",
                        "assetPath": "asset1",
                    }
                }
            },
            "actArchiveData": {
                "components": {"act1": {"pic": {"pics": [{"picId": "pic1", "picSortId": 1}]}}}
            },
        },
    )
    _write(
        tmp_path,
        "retro_table.json",
        {"retroActList": {"retro1": {"linkedActId": ["act1"], "name": "Gallery 1"}}},
    )
    _write(
        tmp_path,
        "stage_table.json",
        {
            "storylineStorySets": {
                "set1": {"relevantActivityId": "act1", "ssData": {"desc": "Fallback"}}
            }
        },
    )

    galleries = parse_galleries(tmp_path)

    assert galleries[0].description == "Fallback"
    assert galleries[0].entries[0].art_id == "asset1"


def test_current_cg_schema_merges_legacy_and_new_entries(tmp_path: Path):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {
            "actArchiveResData": {
                "pics": {
                    "legacy": {
                        "id": "legacy",
                        "desc": "Legacy",
                        "assetPath": "70_i01_2",
                    }
                }
            },
            "actArchiveData": {
                "components": {
                    "act49side": {"pic": {"pics": [{"picId": "legacy", "picSortId": 1}]}}
                }
            },
        },
    )
    _write(
        tmp_path,
        "retro_table.json",
        {"retroActList": {"retro": {"linkedActId": ["act49side"], "name": "Event"}}},
    )
    _write(tmp_path, "activity_table.json", {"basicInfo": {"act49side": {"name": "Event"}}})
    _write(
        tmp_path,
        "stage_table.json",
        {
            "storylineStorySets": {
                "set": {"relevantActivityId": "act49side", "ssData": {"desc": "Story"}}
            },
            "cgGalleryGroups": {"set": {"displays": ["display"]}},
            "cgGalleryDisplays": {
                "display": {
                    "cgList": ["70_i01_2", "70_i01_1"],
                    "displayName": "Chapter",
                    "displayDesc": "Description",
                }
            },
        },
    )

    (gallery,) = parse_galleries(tmp_path)

    assert gallery.description == "Story"
    assert [entry.art_id for entry in gallery.entries] == ["70_i01_2", "70_i01_1"]
    assert gallery.entries[0].name == "Legacy"
    assert gallery.entries[0].description == "Description"
    assert gallery.entries[1].id == "display_2"


def test_current_schema_can_create_a_gallery_without_legacy_metadata(tmp_path: Path):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {"actArchiveResData": {"pics": {}}, "actArchiveData": {"components": {}}},
    )
    _write(tmp_path, "retro_table.json", {"retroActList": {}})
    _write(tmp_path, "activity_table.json", {"basicInfo": {"act49side": {"name": "Event"}}})
    _write(
        tmp_path,
        "stage_table.json",
        {
            "storylineStorySets": {
                "set": {"relevantActivityId": "act49side", "ssData": {"desc": "Story"}}
            },
            "cgGalleryGroups": {"set": {"displays": ["display"]}},
            "cgGalleryDisplays": {
                "display": {
                    "cgList": ["70_i01_2"],
                    "displayName": "Chapter",
                    "displayDesc": "Description",
                }
            },
        },
    )

    (gallery,) = parse_galleries(tmp_path)

    assert (gallery.id, gallery.name, gallery.description) == ("act49side", "Event", "Story")
    assert gallery.entries[0].art_id == "70_i01_2"
