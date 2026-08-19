from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from arkwaifu_updateloop.artwork import (
    add_gallery_artworks,
    build_artwork_manifest,
    merge_artwork_manifests,
    read_artwork_manifest,
    write_artwork_manifest,
)
from arkwaifu_updateloop.domain import (
    ArtworkManifest,
    ArtworkPanel,
    ArtworkRecord,
    FileAudioArtifact,
    FilePngArtifact,
    FileVideoArtifact,
    GalleryArtwork,
    PngArtifact,
    SourceLayerRecord,
    SourceLayerReference,
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

    manifest = build_artwork_manifest(tmp_path, "v1")

    assert [artwork.id for artwork in manifest.artworks] == ["Event"]
    assert manifest.artworks[0].category == "illustration"
    assert manifest.artworks[0].image.content == expected


def test_picture_identity_includes_category(tmp_path: Path):
    write_png(
        tmp_path / "assets/torappu/dynamicassets/avg/images/shared.png",
        (1, 2, 3, 255),
    )
    background = write_png(
        tmp_path / "assets/torappu/dynamicassets/avg/backgrounds/shared.png",
        (4, 5, 6, 255),
    )

    manifest = build_artwork_manifest(tmp_path, "v1")

    assert [(artwork.category, artwork.id) for artwork in manifest.artworks] == [
        ("background", "shared"),
        ("illustration", "shared"),
    ]
    assert manifest.artworks[0].image.content == background


def test_animated_kv_keeps_poster_and_indexes_every_png(tmp_path: Path):
    root = tmp_path / "assets/torappu/dynamicassets/avg/animatedkv/act3mainss_01"
    write_png(root / "effect.png", (1, 2, 3, 255), size=(2, 2))
    expected = write_png(root / "kv_bg.png", (4, 5, 6, 255), size=(8, 4))

    manifest = build_artwork_manifest(tmp_path, "v1")

    assert [(artwork.category, artwork.id) for artwork in manifest.artworks] == [
        ("background", "act3mainss_01"),
        ("illustration", "act3mainss_01/effect"),
        ("illustration", "act3mainss_01/kv_bg"),
    ]
    assert manifest.artworks[0].image.content == expected


def test_audio_media_round_trips_through_the_cache(tmp_path: Path):
    audio_path = tmp_path / "assets/torappu/dynamicassets/audio/avg_se_0/flashback.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFF" + b"audio")
    audio_path.with_suffix(".wav.audio.json").write_text(
        '{"duration":2.5,"sample_rate":48000}', encoding="utf-8"
    )

    manifest = build_artwork_manifest(tmp_path, "v1")
    assert [(media.kind, media.id) for media in manifest.media] == [("audio", "flashback")]
    assert manifest.media[0].artifact.duration == 2.5
    assert manifest.media[0].artifact.sample_rate == 48_000

    cached_root = tmp_path / "cache"
    write_artwork_manifest(manifest, cached_root)
    cached = read_artwork_manifest(cached_root)
    assert isinstance(cached.media[0].artifact, FileAudioArtifact)
    assert cached.media[0].artifact.path == (cached_root / "processed/media-00000000.wav").resolve()
    assert cached.media[0].artifact.sample_rate == 48_000


def test_common_compressed_audio_formats_round_trip_without_reencoding(tmp_path: Path):
    root = tmp_path / "assets/torappu/dynamicassets/audio"
    mp3 = root / "music/intro.mp3"
    flac = root / "music/intro_lossless.flac"
    mp3.parent.mkdir(parents=True)
    mp3.write_bytes(b"ID3source-mp3")
    flac.write_bytes(b"fLaCsource-flac")

    manifest = build_artwork_manifest(tmp_path, "v1")

    assert [(media.id, media.artifact.content_type) for media in manifest.media] == [
        ("intro", "audio/mpeg"),
        ("intro_lossless", "audio/flac"),
    ]
    assert manifest.media[0].artifact.content == mp3.read_bytes()
    assert manifest.media[1].artifact.content == flac.read_bytes()


def test_global_audio_ids_must_be_unique(tmp_path: Path):
    root = tmp_path / "assets/torappu/dynamicassets/audio"
    first = root / "one/duplicate.mp3"
    second = root / "two/duplicate.wav"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"mp3")
    second.write_bytes(b"wav")

    with pytest.raises(ValueError, match="duplicate audio asset ID 'duplicate'"):
        build_artwork_manifest(tmp_path, "v1")


def test_character_voice_audio_ids_keep_the_character_namespace(tmp_path: Path):
    root = tmp_path / "assets/torappu/dynamicassets/audio/sound_beta_2/voice"
    for character in ("char_1016_agoat2", "char_101_sora"):
        audio_path = root / character / "CN_038/CN_038.wav"
        audio_path.parent.mkdir(parents=True)
        audio_path.write_bytes(b"RIFF" + character.encode())

    manifest = build_artwork_manifest(tmp_path, "v1")

    assert [(media.kind, media.id) for media in manifest.media] == [
        ("audio", "char_1016_agoat2/CN_038"),
        ("audio", "char_101_sora/CN_038"),
    ]


def test_animated_kv_media_is_namespaced_and_preserves_video_format(tmp_path: Path):
    root = tmp_path / "assets/torappu/dynamicassets/avg/animatedkv/act3mainss_01"
    root.mkdir(parents=True)
    audio_path = root / "voice.ogg"
    audio_path.write_bytes(b"OggS" + b"audio")
    audio_path.with_suffix(".ogg.audio.json").write_text('{"duration":1.25}', encoding="utf-8")
    video_path = root / "opening.mp4"
    video_path.write_bytes(b"video")
    video_path.with_suffix(".mp4.video.json").write_text(
        '{"content_type":"video/mp4","width":1920,"height":1080,'
        '"frame_rate_numerator":24,"frame_rate_denominator":1,"frame_count":48}',
        encoding="utf-8",
    )

    manifest = build_artwork_manifest(tmp_path, "v1")

    assert [(media.kind, media.id) for media in manifest.media] == [
        ("audio", "act3mainss_01/voice"),
        ("video", "act3mainss_01/opening"),
    ]
    assert isinstance(manifest.media[1].artifact, FileVideoArtifact)
    assert manifest.media[1].artifact.content_type == "video/mp4"
    cached_root = tmp_path / "cache"
    write_artwork_manifest(manifest, cached_root)
    cached = read_artwork_manifest(cached_root)
    assert cached.media[1].artifact.path == (cached_root / "processed/media-00000001.mp4").resolve()


def test_score_visual_directories_keep_dedicated_kinds(tmp_path: Path):
    root = tmp_path / "assets/torappu/dynamicassets/arts/ui/mixstory"
    write_png(root / "abbrs/storyline_abbr_ur.png", (1, 2, 3, 255))
    write_png(root / "splits/act_3.png", (4, 5, 6, 255))
    write_png(root / "logos/storyline_ur.png", (7, 8, 9, 255))
    write_png(root / "retrobkgs/retro_main_0.png", (10, 11, 12, 255))

    manifest = build_artwork_manifest(tmp_path, "v1")

    assert [(asset.kind, asset.id) for asset in manifest.score_assets] == [
        ("divider", "act_3"),
        ("icon", "storyline_abbr_ur"),
        ("logo", "storyline_ur"),
        ("retro-background", "retro_main_0"),
    ]


def test_known_sacrifice_torch_vertical_recipe_is_top_to_bottom():
    colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (0, 0, 0, 255)]
    panel_ids = ("66_i15_4", "66_i15_3", "66_i15_2", "66_i15_1")
    panels = tuple(
        ArtworkPanel(panel_id, position, 2, 1) for position, panel_id in enumerate(panel_ids)
    )
    manifest = ArtworkManifest(
        "v1",
        tuple(
            ArtworkRecord(
                panel_id, "background", PngArtifact.from_image(Image.new("RGBA", (2, 1), color))
            )
            for panel_id, color in zip(panel_ids, colors, strict=True)
        ),
        (),
    )
    recipe = GalleryArtwork(
        0,
        "66_i15_3",
        "/".join(panel_ids),
        "background",
        "vertical",
        panels,
    )

    result = add_gallery_artworks(manifest, (recipe,))
    gallery_artwork = next(artwork for artwork in result.artworks if artwork.id == recipe.asset_id)
    with Image.open(BytesIO(gallery_artwork.image.content)) as image:
        assert image.size == (2, 4)
        assert [image.getpixel((0, y)) for y in range(4)] == colors
    assert {(artwork.category, artwork.id) for artwork in result.artworks}.issuperset(
        {("background", panel_id) for panel_id in panel_ids}
    )
    assert {(source.category, source.id) for source in result.source_layers} == {
        ("background", panel_id) for panel_id in panel_ids
    }
    assert tuple(reference.id for reference in gallery_artwork.source_layer_references) == panel_ids


def test_known_horizontal_panorama_is_left_to_right():
    panel_ids = ("60_i11_1l", "60_i11_1r")
    panels = tuple(
        ArtworkPanel(panel_id, position, 1, 2) for position, panel_id in enumerate(panel_ids)
    )
    manifest = ArtworkManifest(
        "v1",
        (
            ArtworkRecord(
                "60_i11_1l",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (1, 2), "red")),
            ),
            ArtworkRecord(
                "60_i11_1r",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (1, 2), "blue")),
            ),
        ),
        (),
    )
    recipe = GalleryArtwork(
        0, "60_i11_1m", "/".join(panel_ids), "illustration", "horizontal", panels
    )

    result = add_gallery_artworks(manifest, (recipe,))
    gallery_artwork = next(artwork for artwork in result.artworks if artwork.id == recipe.asset_id)
    with Image.open(BytesIO(gallery_artwork.image.content)) as image:
        assert image.size == (2, 2)
        assert image.getpixel((0, 0)) == (255, 0, 0, 255)
        assert image.getpixel((1, 0)) == (0, 0, 255, 255)


def test_gallery_artwork_resizes_panels_to_declared_layout_dimensions():
    manifest = ArtworkManifest(
        "v1",
        (
            ArtworkRecord(
                "top",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (2, 1), "red")),
            ),
            ArtworkRecord(
                "bottom",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (1, 2), "blue")),
            ),
        ),
        (),
    )
    recipe = GalleryArtwork(
        0,
        "panel-artwork",
        "top/bottom",
        "illustration",
        "vertical",
        (
            ArtworkPanel("top", 0, 4, 3),
            ArtworkPanel("bottom", 1, 4, 2),
        ),
    )

    result = add_gallery_artworks(manifest, (recipe,))

    gallery_artwork = next(artwork for artwork in result.artworks if artwork.id == recipe.asset_id)
    with Image.open(BytesIO(gallery_artwork.image.content)) as image:
        assert image.size == (4, 5)
        assert image.getpixel((0, 0)) == (255, 0, 0, 255)
        assert image.getpixel((0, 4)) == (0, 0, 255, 255)
    assert {
        (source.id, source.image.width, source.image.height) for source in result.source_layers
    } == {("top", 2, 1), ("bottom", 1, 2)}


def test_independent_bundle_manifests_keep_same_id_in_distinct_categories():
    image = PngArtifact.from_image(Image.new("RGBA", (1, 1), (1, 2, 3, 255)))
    background = PngArtifact.from_image(Image.new("RGBA", (1, 1), (4, 5, 6, 255)))

    merged = merge_artwork_manifests(
        [
            ArtworkManifest("v1", (ArtworkRecord("shared", "background", background),), ()),
            ArtworkManifest("v1", (ArtworkRecord("shared", "illustration", image),), ()),
        ],
        "v1",
    )

    assert [(artwork.category, artwork.id) for artwork in merged.artworks] == [
        ("background", "shared"),
        ("illustration", "shared"),
    ]
    assert [artwork.image for artwork in merged.artworks] == [background, image]


def test_cached_artwork_manifest_round_trips_without_pickle(tmp_path: Path):
    value = ArtworkManifest(
        "v1",
        (
            ArtworkRecord(
                "event",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255))),
            ),
        ),
        (),
    )

    write_artwork_manifest(value, tmp_path)

    cached = read_artwork_manifest(tmp_path)

    assert cached.upstream_version == value.upstream_version
    assert [
        (artwork.id, artwork.category, artwork.source_layer_references)
        for artwork in cached.artworks
    ] == [("event", "illustration", ())]
    assert isinstance(cached.artworks[0].image, FilePngArtifact)
    assert cached.artworks[0].image.path == (tmp_path / "processed/00000000.png").resolve()
    assert cached.artworks[0].image.byte_size == len(value.artworks[0].image.content)
    assert cached.artworks[0].image.content == value.artworks[0].image.content
    assert cached.artworks[0].res_version is None
    assert cached_payload(tmp_path)["artworks"][0]["image_path"] == "processed/00000000.png"


def test_cached_manifest_read_does_not_read_png_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    value = ArtworkManifest(
        "v1",
        (
            ArtworkRecord(
                "event",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255))),
            ),
        ),
        (),
    )
    write_artwork_manifest(value, tmp_path)

    def forbid_read_bytes(_path: Path) -> bytes:
        raise AssertionError("cached PNG bytes were read eagerly")

    monkeypatch.setattr(Path, "read_bytes", forbid_read_bytes)

    cached = read_artwork_manifest(tmp_path)

    assert isinstance(cached.artworks[0].image, FilePngArtifact)
    assert cached.artworks[0].image.byte_size > 0


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
        write_artwork_manifest(
            ArtworkManifest("v1", (ArtworkRecord("event", "illustration", artifact),), ()),
            destination,
        )

    assert (destination / "processed/00000000.png").read_bytes() == expected


def cached_character_manifest() -> ArtworkManifest:
    artifact = PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255)))
    source_id = "char:body:1"
    return ArtworkManifest(
        "v1",
        (
            ArtworkRecord(
                "char#1$1",
                "character",
                artifact,
                (SourceLayerReference("character", source_id),),
            ),
        ),
        (
            SourceLayerRecord(
                source_id,
                "character",
                "character",
                artifact,
                character_id="char",
                role="body",
                variant="1",
            ),
        ),
    )


def cached_payload(path: Path) -> dict:
    return json.loads((path / "manifest.json").read_text(encoding="utf-8"))


def test_cached_manifest_writes_one_ordinal_png_per_record(tmp_path: Path):
    write_artwork_manifest(cached_character_manifest(), tmp_path)

    payload = cached_payload(tmp_path)
    assert payload["artworks"][0]["image_path"] == "processed/00000000.png"
    assert payload["source_layers"][0]["image_path"] == "processed/00000001.png"
    assert sorted(path.name for path in (tmp_path / "processed").iterdir()) == [
        "00000000.png",
        "00000001.png",
    ]
    assert (tmp_path / "processed/00000000.png").read_bytes() == (
        tmp_path / "processed/00000001.png"
    ).read_bytes()


def test_cached_manifest_missing_required_key_is_a_value_error(tmp_path: Path):
    write_artwork_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    del payload["artworks"][0]["id"]
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="missing 'id'"):
        read_artwork_manifest(tmp_path)


def test_cached_manifest_converts_invalid_record_type_to_value_error(tmp_path: Path):
    write_artwork_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload["artworks"] = [None]
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="malformed"):
        read_artwork_manifest(tmp_path)


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("artworks", "id", 1, "invalid id"),
        ("artworks", "category", "portrait", "invalid category"),
        ("source_layers", "role", "portrait", "invalid role"),
    ],
)
def test_cached_manifest_rejects_invalid_record_values(
    tmp_path: Path,
    section: str,
    field: str,
    value: object,
    message: str,
):
    write_artwork_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload[section][0][field] = value
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match=message):
        read_artwork_manifest(tmp_path)


def test_cached_manifest_rejects_empty_upstream_version(tmp_path: Path):
    write_artwork_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload["upstream_version"] = ""
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="invalid upstream_version"):
        read_artwork_manifest(tmp_path)


def test_cached_manifest_rejects_nonordinal_image_path_before_reading_it(tmp_path: Path):
    write_artwork_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload["artworks"][0]["image_path"] = "../outside.png"
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="invalid image_path"):
        read_artwork_manifest(tmp_path)


def test_cached_manifest_rejects_invalid_png_content(tmp_path: Path):
    write_artwork_manifest(cached_character_manifest(), tmp_path)
    path = tmp_path / cached_payload(tmp_path)["artworks"][0]["image_path"]
    path.write_bytes(b"not a PNG")

    with pytest.raises(ValueError, match="cannot read cached artwork image"):
        read_artwork_manifest(tmp_path)


def test_cached_manifest_rejects_missing_source_reference(tmp_path: Path):
    write_artwork_manifest(cached_character_manifest(), tmp_path)
    payload = cached_payload(tmp_path)
    payload["source_layers"] = []
    write_json(tmp_path / "manifest.json", payload)

    with pytest.raises(ValueError, match="references missing sources"):
        read_artwork_manifest(tmp_path)


@pytest.mark.parametrize(
    ("face_position_key", "face_size_key"),
    [("FacePos", "FaceSize"), ("facePos", "faceSize")],
)
def test_character_sources_precede_resize_and_artwork_rendering(
    tmp_path: Path,
    face_position_key: str,
    face_size_key: str,
):
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
                    face_position_key: {"x": 1, "y": 1},
                    face_size_key: {"x": 2, "y": 2},
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

    manifest = build_artwork_manifest(tmp_path, "v1")

    assert [artwork.id for artwork in manifest.artworks] == ["char_test#1$1"]
    assert [source.id for source in manifest.source_layers] == [
        "char_test:body:1",
        "char_test:face:1:1",
    ]
    artwork = manifest.artworks[0]
    assert tuple(source.id for source in artwork.source_layer_references) == (
        "char_test:body:1",
        "char_test:face:1:1",
    )
    with Image.open(Path(directory / "body.png")) as raw_body:
        assert manifest.source_layers[0].image.width == raw_body.width
    from io import BytesIO

    with Image.open(BytesIO(artwork.image.content)) as rendered:
        assert rendered.getpixel((0, 0)) == (255, 0, 0, 255)
        assert rendered.getpixel((1, 1)) == (0, 0, 255, 255)


def test_whole_body_source_is_exposed_without_layer_merging(tmp_path: Path):
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

    manifest = build_artwork_manifest(tmp_path, "v2")

    assert manifest.artworks[0].id == "char_whole#1$1"
    assert tuple(source.id for source in manifest.artworks[0].source_layer_references) == (
        "char_whole:whole_body:1:1",
    )
    assert manifest.source_layers[0].role == "whole_body"
