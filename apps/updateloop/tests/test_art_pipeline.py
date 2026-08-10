from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from arkwaifu_updateloop.art import (
    build_art_manifest,
    merge_art_manifests,
    read_art_manifest,
    write_art_manifest,
)
from arkwaifu_updateloop.domain import (
    ArtManifest,
    ArtRecord,
    FilePngArtifact,
    PngArtifact,
    SourceArtRecord,
)


def write_png(path: Path, color: tuple[int, int, int, int], size=(4, 4)) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, color)
    image.save(path, format="PNG")
    return path.read_bytes()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_picture_png_bytes_are_preserved(tmp_path: Path):
    picture = tmp_path / "assets/torappu/dynamicassets/avg/images/Event.png"
    expected = write_png(picture, (1, 2, 3, 255))

    manifest = build_art_manifest(tmp_path, "v1")

    assert [art.id for art in manifest.arts] == ["event"]
    assert manifest.arts[0].category == "image"
    assert manifest.arts[0].image.content == expected


def test_picture_identifier_collision_keeps_later_legacy_category(tmp_path: Path):
    write_png(
        tmp_path / "assets/torappu/dynamicassets/avg/images/shared.png",
        (1, 2, 3, 255),
    )
    expected = write_png(
        tmp_path / "assets/torappu/dynamicassets/avg/backgrounds/shared.png",
        (4, 5, 6, 255),
    )

    manifest = build_art_manifest(tmp_path, "v1")

    assert len(manifest.arts) == 1
    assert manifest.arts[0].id == "shared"
    assert manifest.arts[0].category == "background"
    assert manifest.arts[0].image.content == expected


def test_independent_bundle_manifests_merge_with_category_precedence():
    image = PngArtifact.from_image(Image.new("RGBA", (1, 1), (1, 2, 3, 255)))
    background = PngArtifact.from_image(Image.new("RGBA", (1, 1), (4, 5, 6, 255)))

    merged = merge_art_manifests(
        [
            ArtManifest("v1", (ArtRecord("shared", "background", background),), ()),
            ArtManifest("v1", (ArtRecord("shared", "image", image),), ()),
        ],
        "v1",
    )

    assert len(merged.arts) == 1
    assert merged.arts[0].category == "background"
    assert merged.arts[0].image == background


def test_cached_art_manifest_round_trips_without_pickle(tmp_path: Path):
    value = ArtManifest(
        "v1",
        (
            ArtRecord(
                "event",
                "image",
                PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255))),
            ),
        ),
        (),
    )

    write_art_manifest(value, tmp_path)

    cached = read_art_manifest(tmp_path)

    assert cached.upstream_version == value.upstream_version
    assert [(art.id, art.category, art.source_art_ids) for art in cached.arts] == [
        ("event", "image", ())
    ]
    assert isinstance(cached.arts[0].image, FilePngArtifact)
    assert cached.arts[0].image.path == (tmp_path / "processed/00000000.png").resolve()
    assert cached.arts[0].image.byte_size == len(value.arts[0].image.content)
    assert cached.arts[0].image.content == value.arts[0].image.content
    assert cached_payload(tmp_path)["arts"][0]["image_path"] == "processed/00000000.png"


def test_cached_manifest_read_does_not_read_png_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    value = ArtManifest(
        "v1",
        (
            ArtRecord(
                "event",
                "image",
                PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255))),
            ),
        ),
        (),
    )
    write_art_manifest(value, tmp_path)

    def forbid_read_bytes(_path: Path) -> bytes:
        raise AssertionError("cached PNG bytes were read eagerly")

    monkeypatch.setattr(Path, "read_bytes", forbid_read_bytes)

    cached = read_art_manifest(tmp_path)

    assert isinstance(cached.arts[0].image, FilePngArtifact)
    assert cached.arts[0].image.byte_size > 0


def test_writing_a_file_backed_manifest_streams_from_its_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source.png"
    expected = write_png(source, (1, 2, 3, 255))
    artifact = FilePngArtifact.from_path(source)
    destination = tmp_path / "cache"

    def forbid_read_bytes(_path: Path) -> bytes:
        raise AssertionError("file-backed PNG was materialized as bytes")

    with monkeypatch.context() as context:
        context.setattr(Path, "read_bytes", forbid_read_bytes)
        write_art_manifest(
            ArtManifest("v1", (ArtRecord("event", "image", artifact),), ()),
            destination,
        )

    assert (destination / "processed/00000000.png").read_bytes() == expected


def cached_character_manifest() -> ArtManifest:
    artifact = PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255)))
    source_id = "char:body:1"
    return ArtManifest(
        "v1",
        (ArtRecord("char#1$1", "character", artifact, (source_id,)),),
        (SourceArtRecord(source_id, "char", "body", "1", artifact),),
    )


def cached_payload(path: Path) -> dict:
    return json.loads((path / "manifest.json").read_text(encoding="utf-8"))


def test_cached_manifest_writes_one_ordinal_png_per_record(tmp_path: Path):
    write_art_manifest(cached_character_manifest(), tmp_path)

    payload = cached_payload(tmp_path)
    assert payload["arts"][0]["image_path"] == "processed/00000000.png"
    assert payload["source_arts"][0]["image_path"] == "processed/00000001.png"
    assert sorted(path.name for path in (tmp_path / "processed").iterdir()) == [
        "00000000.png",
        "00000001.png",
    ]
    assert (tmp_path / "processed/00000000.png").read_bytes() == (
        tmp_path / "processed/00000001.png"
    ).read_bytes()


def test_cached_manifest_missing_required_key_is_a_value_error(tmp_path: Path):
    write_art_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    del payload["arts"][0]["id"]
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="missing 'id'"):
        read_art_manifest(tmp_path)


def test_cached_manifest_converts_invalid_record_type_to_value_error(tmp_path: Path):
    write_art_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload["arts"] = [None]
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="malformed"):
        read_art_manifest(tmp_path)


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("arts", "id", 1, "invalid id"),
        ("arts", "category", "portrait", "invalid category"),
        ("source_arts", "role", "portrait", "invalid role"),
    ],
)
def test_cached_manifest_rejects_invalid_record_values(
    tmp_path: Path,
    section: str,
    field: str,
    value: object,
    message: str,
):
    write_art_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload[section][0][field] = value
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match=message):
        read_art_manifest(tmp_path)


def test_cached_manifest_rejects_empty_upstream_version(tmp_path: Path):
    write_art_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload["upstream_version"] = ""
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="invalid upstream_version"):
        read_art_manifest(tmp_path)


def test_cached_manifest_rejects_nonordinal_image_path_before_reading_it(tmp_path: Path):
    write_art_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload["arts"][0]["image_path"] = "../outside.png"
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="invalid image_path"):
        read_art_manifest(tmp_path)


def test_cached_manifest_rejects_invalid_png_content(tmp_path: Path):
    write_art_manifest(cached_character_manifest(), tmp_path)
    path = tmp_path / cached_payload(tmp_path)["arts"][0]["image_path"]
    path.write_bytes(b"not a PNG")

    with pytest.raises(ValueError, match="cannot read cached art image"):
        read_art_manifest(tmp_path)


def test_cached_manifest_rejects_missing_source_reference(tmp_path: Path):
    write_art_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload["source_arts"] = []
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="references missing sources"):
        read_art_manifest(tmp_path)


def test_character_sources_precede_resize_and_composition(tmp_path: Path):
    character_root = tmp_path / "assets/torappu/dynamicassets/avg/characters"
    directory = character_root / "char_test"
    write_png(directory / "face.png", (0, 0, 255, 255), size=(2, 2))
    write_png(directory / "face_alpha.png", (255, 255, 255, 255), size=(2, 2))
    write_png(directory / "body.png", (255, 0, 0, 255), size=(4, 4))
    write_png(directory / "body_alpha.png", (255, 255, 255, 255), size=(4, 4))
    write_json(
        directory / "AVGCharacterSpriteHubGroup.json",
        {
            "spriteGroups": [
                {
                    "FacePos": {"x": 1, "y": 1},
                    "FaceSize": {"x": 2, "y": 2},
                    "sprites": [
                        {"sprite": {"m_PathID": 1}, "alphaTex": {"m_PathID": 2}},
                        {"sprite": {"m_PathID": 3}, "alphaTex": {"m_PathID": 4}},
                    ],
                }
            ]
        },
    )
    write_json(
        character_root / "char_test.json",
        {"1": "face.png", "2": "face_alpha.png", "3": "body.png", "4": "body_alpha.png"},
    )
    write_json(character_root / "char_test.typetree.json", {"1": "face.json", "3": "body.json"})
    write_json(directory / "face.json", {"m_PixelsToUnits": 100})
    write_json(directory / "body.json", {"m_PixelsToUnits": 100})

    manifest = build_art_manifest(tmp_path, "v1")

    assert [art.id for art in manifest.arts] == ["char_test#1$1"]
    assert [source.id for source in manifest.source_arts] == [
        "char_test:body:1",
        "char_test:face:1:1",
    ]
    art = manifest.arts[0]
    assert art.source_art_ids == ("char_test:body:1", "char_test:face:1:1")
    with Image.open(Path(directory / "body.png")) as raw_body:
        assert manifest.source_arts[0].image.width == raw_body.width
    from io import BytesIO

    with Image.open(BytesIO(art.image.content)) as composed:
        assert composed.getpixel((0, 0)) == (255, 0, 0, 255)
        assert composed.getpixel((1, 1)) == (0, 0, 255, 255)


def test_whole_body_source_is_exposed_without_composition(tmp_path: Path):
    character_root = tmp_path / "assets/torappu/dynamicassets/avg/characters"
    directory = character_root / "char_whole"
    write_png(directory / "whole.png", (10, 20, 30, 255), size=(3, 5))
    write_json(
        directory / "AVGCharacterSpriteHub.json",
        {
            "FacePos": {"x": -1, "y": -1},
            "FaceSize": {"x": 0, "y": 0},
            "sprites": [{"sprite": {"m_PathID": 1}, "alphaTex": {"m_PathID": 0}}],
        },
    )
    write_json(character_root / "char_whole.json", {"1": "whole.png"})
    write_json(character_root / "char_whole.typetree.json", {"1": "whole.json"})
    write_json(directory / "whole.json", {"m_PixelsToUnits": 100})

    manifest = build_art_manifest(tmp_path, "v2")

    assert manifest.arts[0].id == "char_whole#1$1"
    assert manifest.arts[0].source_art_ids == ("char_whole:whole_body:1:1",)
    assert manifest.source_arts[0].role == "whole_body"
