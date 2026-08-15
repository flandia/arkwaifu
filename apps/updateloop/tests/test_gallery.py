from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    assert galleries[0].collection_id == "movement_section:set1"
    assert galleries[0].displays[0].artworks[0].art_id == "asset1"


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
                    },
                    "extra": {
                        "id": "extra",
                        "desc": "Legacy extra",
                        "picDescription": "Only in the legacy gallery",
                        "assetPath": "70_i01_3",
                    },
                }
            },
            "actArchiveData": {
                "components": {
                    "act49side": {
                        "pic": {
                            "pics": [
                                {"picId": "legacy", "picSortId": 1},
                                {"picId": "extra", "picSortId": 2},
                            ]
                        }
                    }
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
            "cgGalleryGroups": {"set": {"storySetId": "Set", "displays": ["display"]}},
            "cgGalleryDisplays": {
                "display": {
                    "displayId": "Display",
                    "storySetId": "Set",
                    "cgSource": "IMAGE",
                    "cgList": ["70_i01_2", "70_i01_1"],
                    "displayName": "Chapter",
                    "displayDesc": "Description",
                }
            },
            "cgGalleryCgs": {
                cg_id: {
                    "cgId": cg_id,
                    "storySetId": "Set",
                    "compositeType": "NONE",
                }
                for cg_id in ("70_i01_2", "70_i01_1")
            },
        },
    )

    (gallery,) = parse_galleries(tmp_path)

    assert gallery.description == "Story"
    assert gallery.id == "set"
    assert [artwork.art_id for artwork in gallery.displays[0].artworks] == [
        "70_i01_2",
        "70_i01_1",
    ]
    assert gallery.displays[0].name == "Chapter"
    assert gallery.displays[0].description == "Description"
    assert gallery.displays[0].id == "display"
    assert len(gallery.displays) == 2
    assert gallery.displays[1].position == 1
    assert gallery.displays[1].name == "Legacy extra"
    assert gallery.displays[1].description == "Only in the legacy gallery"
    assert gallery.displays[1].artworks[0].art_id == "70_i01_3"


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
            "cgGalleryGroups": {"set": {"storySetId": "set", "displays": ["display"]}},
            "cgGalleryDisplays": {
                "display": {
                    "displayId": "display",
                    "storySetId": "set",
                    "cgSource": "IMAGE",
                    "cgList": ["70_i01_2"],
                    "displayName": "Chapter",
                    "displayDesc": "Description",
                }
            },
            "cgGalleryCgs": {
                "70_i01_2": {
                    "cgId": "70_i01_2",
                    "storySetId": "set",
                    "compositeType": "NONE",
                }
            },
        },
    )

    (gallery,) = parse_galleries(
        tmp_path,
        collection_names={"movement_section:set": "Event"},
    )

    assert (gallery.id, gallery.name, gallery.description) == ("set", "Event", "Story")
    assert gallery.collection_id == "movement_section:set"
    assert gallery.displays[0].artworks[0].art_id == "70_i01_2"


def test_current_schema_uses_cg_source_and_keeps_category_qualified_art(tmp_path: Path):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {
            "actArchiveResData": {
                "pics": {
                    "legacy": {
                        "id": "legacy",
                        "desc": "Legacy illustration",
                        "assetPath": "66_i15_3",
                    }
                }
            },
            "actArchiveData": {
                "components": {
                    "act3mainss": {"pic": {"pics": [{"picId": "legacy", "picSortId": 1}]}}
                }
            },
        },
    )
    _write(
        tmp_path,
        "retro_table.json",
        {"retroActList": {"retro": {"linkedActId": ["act3mainss"], "name": "Event"}}},
    )
    _write(tmp_path, "activity_table.json", {"basicInfo": {"act3mainss": {"name": "Event"}}})
    _write(
        tmp_path,
        "stage_table.json",
        {
            "storylineStorySets": {
                "set": {"relevantActivityId": "act3mainss", "ssData": {"desc": "Story"}}
            },
            "cgGalleryGroups": {"set": {"storySetId": "set", "displays": ["backgrounds"]}},
            "cgGalleryDisplays": {
                "backgrounds": {
                    "displayId": "backgrounds",
                    "storySetId": "set",
                    "cgSource": "BACKGROUND",
                    "cgList": ["66_i15_3", "66_i16_3"],
                    "displayName": "Chapter",
                    "displayDesc": "Description",
                }
            },
            "cgGalleryCgs": {
                cg_id: {
                    "cgId": cg_id,
                    "storySetId": "set",
                    "compositeType": "NONE",
                }
                for cg_id in ("66_i15_3", "66_i16_3")
            },
        },
    )

    (gallery,) = parse_galleries(tmp_path)

    assert [(artwork.art_id, artwork.category) for artwork in gallery.displays[0].artworks] == [
        ("66_i15_3", "background"),
        ("66_i16_3", "background"),
    ]
    assert [(artwork.art_id, artwork.category) for artwork in gallery.displays[1].artworks] == [
        ("66_i15_3", "image")
    ]


def test_unknown_modern_cg_source_is_rejected(tmp_path: Path):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {"actArchiveResData": {"pics": {}}, "actArchiveData": {"components": {}}},
    )
    _write(tmp_path, "retro_table.json", {"retroActList": {}})
    _write(tmp_path, "activity_table.json", {"basicInfo": {"act1": {"name": "Event"}}})
    _write(
        tmp_path,
        "stage_table.json",
        {
            "storylineStorySets": {"set": {"relevantActivityId": "act1"}},
            "cgGalleryGroups": {"set": {"storySetId": "set", "displays": ["display"]}},
            "cgGalleryDisplays": {
                "display": {
                    "displayId": "display",
                    "storySetId": "set",
                    "cgSource": "UNKNOWN",
                    "cgList": ["asset"],
                }
            },
            "cgGalleryCgs": {
                "asset": {
                    "cgId": "asset",
                    "storySetId": "set",
                    "compositeType": "NONE",
                }
            },
        },
    )

    with pytest.raises(ValueError, match="unknown gallery CG source"):
        parse_galleries(tmp_path)


def test_composite_panel_ids_reject_the_identity_separator(tmp_path: Path):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {"actArchiveResData": {"pics": {}}, "actArchiveData": {"components": {}}},
    )
    _write(tmp_path, "retro_table.json", {"retroActList": {}})
    _write(
        tmp_path,
        "stage_table.json",
        {
            "storylineStorySets": {"set": {}},
            "cgGalleryGroups": {"set": {"storySetId": "set", "displays": ["display"]}},
            "cgGalleryDisplays": {
                "display": {
                    "displayId": "display",
                    "storySetId": "set",
                    "cgSource": "IMAGE",
                    "cgList": ["composite"],
                }
            },
            "cgGalleryCgs": {
                "composite": {
                    "cgId": "composite",
                    "storySetId": "set",
                    "compositeType": "VERTICAL",
                    "compositeList": [{"cgId": "ambiguous/panel", "width": 1, "height": 1}],
                }
            },
        },
    )

    with pytest.raises(ValueError, match="contains reserved '/'"):
        parse_galleries(tmp_path)


def _valid_modern_gallery_stage() -> dict[str, object]:
    return {
        "storylineStorySets": {"set": {}},
        "cgGalleryGroups": {"Set": {"storySetId": "set", "displays": ["Display"]}},
        "cgGalleryDisplays": {
            "Display": {
                "displayId": "display",
                "storySetId": "set",
                "cgSource": "IMAGE",
                "cgList": ["Artwork"],
            }
        },
        "cgGalleryCgs": {
            "Artwork": {
                "cgId": "artwork",
                "storySetId": "set",
                "compositeType": "NONE",
            }
        },
    }


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing_cg", "artwork is not declared"),
        ("missing_composite_type", "unknown gallery composite type"),
        ("group_id_mismatch", "mapping key does not match storySetId"),
        ("display_id_mismatch", "mapping key does not match displayId"),
        ("cg_id_mismatch", "mapping key does not match cgId"),
    ],
)
def test_modern_gallery_rejects_missing_records_and_declared_id_drift(
    tmp_path: Path,
    case: str,
    message: str,
):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {"actArchiveResData": {"pics": {}}, "actArchiveData": {"components": {}}},
    )
    _write(tmp_path, "retro_table.json", {"retroActList": {}})
    stage = _valid_modern_gallery_stage()
    group = stage["cgGalleryGroups"]["Set"]
    display = stage["cgGalleryDisplays"]["Display"]
    cg = stage["cgGalleryCgs"]["Artwork"]
    if case == "missing_cg":
        stage["cgGalleryCgs"] = {}
    elif case == "missing_composite_type":
        del cg["compositeType"]
    elif case == "group_id_mismatch":
        group["storySetId"] = "other"
    elif case == "display_id_mismatch":
        display["displayId"] = "other"
    elif case == "cg_id_mismatch":
        cg["cgId"] = "other"
    _write(tmp_path, "stage_table.json", stage)

    with pytest.raises(ValueError, match=message):
        parse_galleries(tmp_path)


def test_modern_gallery_preserves_composite_identity_panels_and_orientation(
    tmp_path: Path,
):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {"actArchiveResData": {"pics": {}}, "actArchiveData": {"components": {}}},
    )
    _write(tmp_path, "retro_table.json", {"retroActList": {}})
    _write(
        tmp_path,
        "stage_table.json",
        {
            "storylineStorySets": {"Set": {}},
            "cgGalleryGroups": {"Set": {"storySetId": "Set", "displays": ["Display"]}},
            "cgGalleryDisplays": {
                "Display": {
                    "displayId": "Display",
                    "storySetId": "Set",
                    "cgSource": "BACKGROUND",
                    "cgList": ["Horizontal", "Vertical"],
                }
            },
            "cgGalleryCgs": {
                "Horizontal": {
                    "cgId": "Horizontal",
                    "storySetId": "Set",
                    "compositeType": "HORIZONTAL",
                    "compositeList": [
                        {"cgId": "Left", "width": 10, "height": 20},
                        {"cgId": "Right", "width": 30, "height": 20},
                    ],
                },
                "Vertical": {
                    "cgId": "Vertical",
                    "storySetId": "Set",
                    "compositeType": "VERTICAL",
                    "compositeList": [
                        {"cgId": "Top", "width": 40, "height": 50},
                        {"cgId": "Bottom", "width": 40, "height": 60},
                    ],
                },
            },
        },
    )

    (gallery,) = parse_galleries(tmp_path)
    horizontal, vertical = gallery.displays[0].artworks

    assert (horizontal.position, horizontal.cg_id, horizontal.art_id) == (
        0,
        "horizontal",
        "left/right",
    )
    assert horizontal.category == "background"
    assert horizontal.composite_type == "horizontal"
    assert [
        (panel.position, panel.id, panel.width, panel.height) for panel in horizontal.panels
    ] == [(0, "left", 10, 20), (1, "right", 30, 20)]
    assert (vertical.position, vertical.cg_id, vertical.art_id) == (
        1,
        "vertical",
        "top/bottom",
    )
    assert vertical.composite_type == "vertical"
    assert [panel.id for panel in vertical.panels] == ["top", "bottom"]


def test_modern_gallery_uses_movement_and_reference_array_order(tmp_path: Path):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {"actArchiveResData": {"pics": {}}, "actArchiveData": {"components": {}}},
    )
    _write(tmp_path, "retro_table.json", {"retroActList": {}})
    _write(
        tmp_path,
        "stage_table.json",
        {
            "storylineStorySets": {"SetLate": {}, "SetEarly": {}},
            "storylines": {
                "LineLate": {
                    "storylineId": "LineLate",
                    "sortId": 20,
                    "locations": {
                        "LocLate": {
                            "locationId": "LocLate",
                            "locationType": "STORY_SET",
                            "relevantStorySetId": "SetLate",
                            "sortId": 1,
                        }
                    },
                },
                "LineEarly": {
                    "storylineId": "LineEarly",
                    "sortId": 10,
                    "locations": {
                        "LocEarly": {
                            "locationId": "LocEarly",
                            "locationType": "STORY_SET",
                            "relevantStorySetId": "SetEarly",
                            "sortId": 1,
                        }
                    },
                },
            },
            "cgGalleryGroups": {
                "SetLate": {
                    "storySetId": "SetLate",
                    "storylineId": "LineLate",
                    "locationId": "LocLate",
                    "displays": ["LateDisplay"],
                },
                "SetEarly": {
                    "storySetId": "SetEarly",
                    "storylineId": "LineEarly",
                    "locationId": "LocEarly",
                    "displays": ["SecondDisplay", "FirstDisplay"],
                },
            },
            "cgGalleryDisplays": {
                "LateDisplay": {
                    "displayId": "LateDisplay",
                    "storySetId": "SetLate",
                    "cgSource": "IMAGE",
                    "cgList": ["LateArt"],
                    "sortId": 0,
                },
                "SecondDisplay": {
                    "displayId": "SecondDisplay",
                    "storySetId": "SetEarly",
                    "cgSource": "IMAGE",
                    "cgList": ["SecondArt", "FirstArt"],
                    "sortId": 99,
                },
                "FirstDisplay": {
                    "displayId": "FirstDisplay",
                    "storySetId": "SetEarly",
                    "cgSource": "IMAGE",
                    "cgList": ["OtherArt"],
                    "sortId": 1,
                },
            },
            "cgGalleryCgs": {
                cg_id: {
                    "cgId": cg_id,
                    "storySetId": "SetLate" if cg_id == "LateArt" else "SetEarly",
                    "compositeType": "NONE",
                    "sortId": sort_id,
                }
                for cg_id, sort_id in (
                    ("LateArt", 0),
                    ("SecondArt", 99),
                    ("FirstArt", 1),
                    ("OtherArt", 0),
                )
            },
        },
    )

    galleries = parse_galleries(tmp_path)

    assert [gallery.id for gallery in galleries] == ["setearly", "setlate"]
    early = galleries[0]
    assert [display.id for display in early.displays] == [
        "seconddisplay",
        "firstdisplay",
    ]
    assert [artwork.cg_id for artwork in early.displays[0].artworks] == [
        "secondart",
        "firstart",
    ]


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing_story_set", "Story Set is not declared"),
        ("missing_display", "display is not declared"),
        ("empty_group", "group has no displays"),
        ("empty_display", "display has no artworks"),
        ("duplicate_display", "duplicate display"),
        ("duplicate_artwork", "duplicate artwork"),
        ("display_story_set", "display belongs to a different Story Set"),
        ("artwork_story_set", "artwork belongs to a different Story Set"),
        ("duplicate_panel", "duplicate panel"),
        ("none_with_panels", "non-composite gallery artwork has panels"),
    ],
)
def test_modern_gallery_rejects_hierarchy_invariant_violations(
    tmp_path: Path,
    case: str,
    message: str,
):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {"actArchiveResData": {"pics": {}}, "actArchiveData": {"components": {}}},
    )
    _write(tmp_path, "retro_table.json", {"retroActList": {}})
    stage = _valid_modern_gallery_stage()
    group = stage["cgGalleryGroups"]["Set"]
    display = stage["cgGalleryDisplays"]["Display"]
    artwork = stage["cgGalleryCgs"]["Artwork"]
    if case == "missing_story_set":
        stage["storylineStorySets"] = {}
    elif case == "missing_display":
        stage["cgGalleryDisplays"] = {}
    elif case == "empty_group":
        group["displays"] = []
    elif case == "empty_display":
        display["cgList"] = []
    elif case == "duplicate_display":
        group["displays"] = ["Display", "display"]
    elif case == "duplicate_artwork":
        display["cgList"] = ["Artwork", "artwork"]
    elif case == "display_story_set":
        display["storySetId"] = "other"
    elif case == "artwork_story_set":
        artwork["storySetId"] = "other"
    elif case == "duplicate_panel":
        artwork["compositeType"] = "VERTICAL"
        artwork["compositeList"] = [
            {"cgId": "panel", "width": 1, "height": 1},
            {"cgId": "PANEL", "width": 1, "height": 1},
        ]
    elif case == "none_with_panels":
        artwork["compositeList"] = [{"cgId": "panel", "width": 1, "height": 1}]
    _write(tmp_path, "stage_table.json", stage)

    with pytest.raises(ValueError, match=message):
        parse_galleries(tmp_path)


@pytest.mark.parametrize(
    ("field", "actual", "message"),
    [
        ("storylineId", "other", "Movement does not match canonical placement"),
        ("locationId", "other", "location does not match canonical placement"),
    ],
)
def test_modern_gallery_rejects_noncanonical_group_placement(
    tmp_path: Path,
    field: str,
    actual: str,
    message: str,
):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {"actArchiveResData": {"pics": {}}, "actArchiveData": {"components": {}}},
    )
    _write(tmp_path, "retro_table.json", {"retroActList": {}})
    stage = _valid_modern_gallery_stage()
    stage["storylines"] = {
        "line": {
            "storylineId": "line",
            "sortId": 0,
            "locations": {
                "location": {
                    "locationId": "location",
                    "locationType": "STORY_SET",
                    "relevantStorySetId": "set",
                    "sortId": 0,
                }
            },
        }
    }
    group = stage["cgGalleryGroups"]["Set"]
    group["storylineId"] = "line"
    group["locationId"] = "location"
    group[field] = actual
    _write(tmp_path, "stage_table.json", stage)

    with pytest.raises(ValueError, match=message):
        parse_galleries(tmp_path)
