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
    assert galleries[0].collection_id == "section:set1"
    assert galleries[0].groups[0].artworks[0].asset_id == "asset1"


def test_legacy_gallery_group_ids_are_lowercase(tmp_path: Path):
    _base(tmp_path)
    _write(
        tmp_path,
        "story_review_meta_table.json",
        {
            "actArchiveResData": {
                "pics": {"kv1": {"id": "KV1", "assetPath": "asset1"}}
            },
            "actArchiveData": {
                "components": {"act1": {"pic": {"pics": [{"picId": "KV1"}]}}}
            },
        },
    )
    _write(tmp_path, "retro_table.json", {"retroActList": {}})
    _write(
        tmp_path,
        "stage_table.json",
        {
            "storylineStorySets": {
                "set1": {"relevantActivityId": "act1", "ssData": {"desc": "Gallery"}}
            }
        },
    )

    galleries = parse_galleries(tmp_path)

    assert galleries[0].groups[0].id == "kv1_legacy"


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
    assert [artwork.asset_id for artwork in gallery.groups[0].artworks] == [
        "70_i01_2",
        "70_i01_1",
    ]
    assert gallery.groups[0].name == "Chapter"
    assert gallery.groups[0].description == "Description"
    assert gallery.groups[0].id == "display"
    assert len(gallery.groups) == 2
    assert gallery.groups[1].position == 1
    assert gallery.groups[1].name == "Legacy extra"
    assert gallery.groups[1].description == "Only in the legacy gallery"
    assert gallery.groups[1].artworks[0].asset_id == "70_i01_3"


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
        collection_names={"section:set": "Event"},
    )

    assert (gallery.id, gallery.name, gallery.description) == ("set", "Event", "Story")
    assert gallery.collection_id == "section:set"
    assert gallery.groups[0].artworks[0].asset_id == "70_i01_2"


def test_current_schema_uses_cg_source_and_keeps_category_qualified_artwork(tmp_path: Path):
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

    assert [(artwork.asset_id, artwork.category) for artwork in gallery.groups[0].artworks] == [
        ("66_i15_3", "background"),
        ("66_i16_3", "background"),
    ]
    assert [(artwork.asset_id, artwork.category) for artwork in gallery.groups[1].artworks] == [
        ("66_i15_3", "illustration")
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


def test_panel_ids_preserve_the_identity_separator(tmp_path: Path):
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
                    "cgList": ["panel-artwork"],
                }
            },
            "cgGalleryCgs": {
                "panel-artwork": {
                    "cgId": "panel-artwork",
                    "storySetId": "set",
                    "compositeType": "VERTICAL",
                    "compositeList": [{"cgId": "ambiguous/panel", "width": 1, "height": 1}],
                }
            },
        },
    )

    (gallery,) = parse_galleries(tmp_path)
    artwork = gallery.groups[0].artworks[0]
    assert artwork.asset_id == "ambiguous/panel"
    assert artwork.panels[0].id == "ambiguous/panel"


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
        ("missing_layout", "unknown Gallery Artwork layout"),
        ("gallery_id_mismatch", "mapping key does not match storySetId"),
        ("group_id_mismatch", "mapping key does not match displayId"),
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
    gallery_group = stage["cgGalleryDisplays"]["Display"]
    cg = stage["cgGalleryCgs"]["Artwork"]
    if case == "missing_cg":
        stage["cgGalleryCgs"] = {}
    elif case == "missing_layout":
        del cg["compositeType"]
    elif case == "gallery_id_mismatch":
        group["storySetId"] = "other"
    elif case == "group_id_mismatch":
        gallery_group["displayId"] = "other"
    elif case == "cg_id_mismatch":
        cg["cgId"] = "other"
    _write(tmp_path, "stage_table.json", stage)

    with pytest.raises(ValueError, match=message):
        parse_galleries(tmp_path)


def test_modern_gallery_preserves_asset_identity_panels_and_orientation(
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
    horizontal, vertical = gallery.groups[0].artworks

    assert (horizontal.position, horizontal.cg_id, horizontal.asset_id) == (
        0,
        "Horizontal",
        "Left/Right",
    )
    assert horizontal.category == "background"
    assert horizontal.layout == "horizontal"
    assert [
        (panel.position, panel.id, panel.width, panel.height) for panel in horizontal.panels
    ] == [(0, "Left", 10, 20), (1, "Right", 30, 20)]
    assert (vertical.position, vertical.cg_id, vertical.asset_id) == (
        1,
        "Vertical",
        "Top/Bottom",
    )
    assert vertical.layout == "vertical"
    assert [panel.id for panel in vertical.panels] == ["Top", "Bottom"]


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
    assert [display.id for display in early.groups] == [
        "seconddisplay",
        "firstdisplay",
    ]
    assert [artwork.cg_id for artwork in early.groups[0].artworks] == [
        "SecondArt",
        "FirstArt",
    ]


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing_story_set", "Story Set is not declared"),
        ("missing_group", "Gallery Group is not declared"),
        ("empty_gallery", "Gallery has no Gallery Groups"),
        ("empty_group", "Gallery Group has no Artwork"),
        ("duplicate_group", "duplicate Gallery Group"),
        ("duplicate_artwork", "duplicate Artwork"),
        ("group_story_set", "Gallery Group belongs to a different Story Set"),
        ("artwork_story_set", "artwork belongs to a different Story Set"),
        ("duplicate_panel", "duplicate panel"),
        ("none_with_panels", "non-panel Gallery Artwork has panels"),
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
    gallery = stage["cgGalleryGroups"]["Set"]
    gallery_group = stage["cgGalleryDisplays"]["Display"]
    artwork = stage["cgGalleryCgs"]["Artwork"]
    if case == "missing_story_set":
        stage["storylineStorySets"] = {}
    elif case == "missing_group":
        stage["cgGalleryDisplays"] = {}
    elif case == "empty_gallery":
        gallery["displays"] = []
    elif case == "empty_group":
        gallery_group["cgList"] = []
    elif case == "duplicate_group":
        gallery["displays"] = ["Display", "display"]
    elif case == "duplicate_artwork":
        gallery_group["cgList"] = ["Artwork", "artwork"]
    elif case == "group_story_set":
        gallery_group["storySetId"] = "other"
    elif case == "artwork_story_set":
        artwork["storySetId"] = "other"
    elif case == "duplicate_panel":
        artwork["compositeType"] = "VERTICAL"
        artwork["compositeList"] = [
            {"cgId": "panel", "width": 1, "height": 1},
            {"cgId": "panel", "width": 1, "height": 1},
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
