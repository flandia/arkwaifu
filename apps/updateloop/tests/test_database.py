from __future__ import annotations

import sqlite3

import pytest
from PIL import Image

from arkwaifu_updateloop.database import (
    apply_changes,
    find_missing_artwork_references,
    find_missing_media_references,
    initialize_or_validate,
    read_versions,
)
from arkwaifu_updateloop.domain import (
    ArchiveGroup,
    ArtworkManifest,
    ArtworkPanel,
    ArtworkRecord,
    FileAudioArtifact,
    Gallery,
    GalleryArtwork,
    GalleryGroup,
    LocaleManifest,
    MediaRecord,
    Movement,
    PngArtifact,
    ScoreAssetRecord,
    Section,
    SourceLayerReference,
    StoryArtworkReference,
    StoryMediaReference,
    StoryRecord,
)


def test_fresh_database_has_the_current_schema_at_version_two(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"

    initialize_or_validate(path)
    initialize_or_validate(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert [
            row[1] for row in connection.execute("PRAGMA table_info(narrative_image_assets)")
        ] == [
            "asset_id",
            "category",
            "object_key",
            "size",
            "width",
            "height",
        ]
        assert [row[1] for row in connection.execute("PRAGMA table_info(material_assets)")] == [
            "category",
            "asset_id",
            "material_type",
            "character_id",
            "role",
            "variant",
            "object_key",
            "size",
            "width",
            "height",
        ]
        assert [
            row[1] for row in connection.execute("PRAGMA table_info(presentation_image_assets)")
        ] == [
            "category",
            "asset_id",
            "object_key",
            "size",
            "width",
            "height",
        ]
        assert [row[1] for row in connection.execute("PRAGMA table_info(story_collections)")] == [
            "locale",
            "collection_id",
            "collection_kind",
        ]
        assert [
            row[2]
            for row in connection.execute(
                "PRAGMA index_info(story_narrative_image_references_by_asset)"
            )
        ] == ["locale", "category", "asset_id"]


def test_database_repairs_missing_performance_index_once(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    assert initialize_or_validate(path) is True
    with sqlite3.connect(path) as connection:
        connection.execute("DROP INDEX story_narrative_image_references_by_asset")

    assert initialize_or_validate(path) is True
    assert initialize_or_validate(path) is False

    with sqlite3.connect(path) as connection:
        assert [
            row[2]
            for row in connection.execute(
                "PRAGMA index_info(story_narrative_image_references_by_asset)"
            )
        ] == ["locale", "category", "asset_id"]


def test_database_rejects_an_unsupported_schema_version(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 3")

    with pytest.raises(ValueError, match="unsupported database schema version 3"):
        initialize_or_validate(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3


@pytest.mark.parametrize(
    "damage",
    [
        "DROP TABLE narrative_media_assets",
        "ALTER TABLE stories DROP COLUMN text",
    ],
)
def test_database_rejects_incomplete_version_two_before_repairing_indexes(tmp_path, damage):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    with sqlite3.connect(path) as connection:
        connection.execute(damage)
        connection.execute("DROP INDEX story_narrative_image_references_by_asset")

    with pytest.raises(ValueError, match="unsupported database schema shape"):
        initialize_or_validate(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert (
            list(connection.execute("PRAGMA index_info(story_narrative_image_references_by_asset)"))
            == []
        )


def test_database_writer_keeps_foreign_key_enforcement(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    image = PngArtifact.from_image(Image.new("RGBA", (1, 1), (1, 2, 3, 255)))
    manifest = ArtworkManifest(
        "v1",
        (
            ArtworkRecord(
                "character#1$1",
                "character",
                image,
                (SourceLayerReference("character", "missing-source"),),
            ),
        ),
        (),
    )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        apply_changes(
            path,
            (manifest,),
            artwork_keys={
                (
                    "character",
                    "character#1$1",
                ): "ART/v1/composition/character/character%231%241.png"
            },
            source_layer_keys={},
            score_asset_keys={},
            score_video_keys={},
        )

    assert read_versions(path) == {}


def test_story_text_and_media_are_published_and_searchable(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    audio_path = tmp_path / "flashback.wav"
    audio_path.write_bytes(b"RIFF" + b"audio")
    audio = FileAudioArtifact.from_path(
        audio_path, content_type="audio/wav", duration=1.5, sample_rate=48_000
    )
    media = MediaRecord("flashback", "audio", audio)
    story = StoryRecord(
        id="story",
        collection_id="archive_group:group",
        tag="before",
        tag_text="",
        code="1-1",
        name="Opening",
        info="summary",
        artwork_references=(StoryArtworkReference("indexed-artwork", "picture", "illustration"),),
        text="A searchable context sentence.",
        media_references=(StoryMediaReference("flashback", "sound"),),
    )
    locale = LocaleManifest(
        unit="CN",
        upstream_version="locale-v1",
        movements=(),
        sections=(),
        archive_groups=(
            ArchiveGroup(
                id="group",
                collection_id="archive_group:group",
                position=0,
                name="Group",
                archive_category="others",
                story_type=None,
                stories=(story,),
            ),
        ),
        galleries=(),
    )

    apply_changes(
        path,
        (
            ArtworkManifest(
                "artwork-v1",
                (
                    ArtworkRecord(
                        "indexed-artwork",
                        "illustration",
                        PngArtifact.from_image(Image.new("RGBA", (1, 1))),
                    ),
                ),
                (),
                media=(media,),
            ),
            locale,
        ),
        artwork_keys={
            (
                "illustration",
                "indexed-artwork",
            ): "ART/artwork-v1/composition/illustration/indexed-artwork.png"
        },
        source_layer_keys={},
        score_asset_keys={},
        score_video_keys={},
        media_keys={("audio", "flashback"): "MEDIA/artwork-v1/audio/flashback.wav"},
    )

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT text FROM stories").fetchone() == (
            "A searchable context sentence.",
        )
        assert connection.execute(
            "SELECT usage, asset_id FROM story_narrative_media_references"
        ).fetchone() == ("sound", "flashback")
        assert connection.execute(
            "SELECT object_key, duration, sample_rate FROM narrative_media_assets"
        ).fetchone() == ("MEDIA/artwork-v1/audio/flashback.wav", 1.5, 48_000)
        search_text = connection.execute(
            "SELECT search_text FROM search_entries WHERE kind = 'story'"
        ).fetchone()[0]
        assert "summary" in search_text
        assert "searchable context" not in search_text
        assert (
            "indexed-artwork"
            in connection.execute(
                "SELECT search_text FROM search_entries "
                "WHERE kind = 'narrative_asset' AND entry_id = 'indexed-artwork'"
            ).fetchone()[0]
        )
    assert find_missing_media_references(path) == ()


def test_archive_and_section_categories_are_explicit(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    archive_categories = (
        "events",
        "operator_record",
        "integrated_strategies",
        "reclamation_algorithm",
        "others",
    )

    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO unit_versions VALUES ('CN', 'v1')")
        connection.executemany(
            "INSERT INTO story_collections VALUES ('CN', ?, 'archive_group')",
            (
                (f"archive_group:group-{position}",)
                for position, _category in enumerate(archive_categories)
            ),
        )
        connection.executemany(
            "INSERT INTO archive_groups VALUES ('CN', ?, ?, ?, ?, ?, ?)",
            (
                (
                    f"group-{position}",
                    f"archive_group:group-{position}",
                    position,
                    kind,
                    kind,
                    "side_story" if kind == "events" else None,
                )
                for position, kind in enumerate(archive_categories)
            ),
        )
        assert (
            tuple(
                row[0]
                for row in connection.execute(
                    "SELECT archive_category FROM archive_groups ORDER BY position"
                )
            )
            == archive_categories
        )
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute(
                "INSERT INTO story_collections VALUES ('CN', 'archive_group:old', 'archive_group')"
            )
            connection.execute(
                "INSERT INTO archive_groups VALUES "
                "('CN', 'old', 'archive_group:old', 7, 'Old', 'other', NULL)"
            )


def test_gallery_writer_constraints_cascade_and_missing_panel_artwork(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    section = Section(
        id="set",
        collection_id="section:set",
        section_type="side_story",
        name="Section",
        review_group_id=None,
        sort_by_year=0,
        sort_within_year=0,
        key_visual_asset_id=None,
        title_asset_id=None,
        background_asset_id=None,
        decoration_asset_id=None,
        retro_background_asset_id=None,
        description="Description",
        has_video=False,
        stories=(),
    )
    panels = (
        ArtworkPanel("top", 0, 10, 20),
        ArtworkPanel("bottom", 1, 10, 30),
    )
    gallery = Gallery(
        id="gallery",
        collection_id=section.collection_id,
        position=0,
        name="Gallery",
        description="Description",
        location_id="location",
        groups=(
            GalleryGroup(
                id="group",
                position=0,
                name="Group",
                description="Gallery Group Artwork",
                related_story_id=None,
                related_stage_id=None,
                artworks=(
                    GalleryArtwork(
                        position=0,
                        cg_id="panel-artwork",
                        asset_id="top/bottom",
                        category="background",
                        layout="vertical",
                        panels=panels,
                    ),
                ),
            ),
        ),
    )
    locale = LocaleManifest(
        unit="CN",
        upstream_version="locale-v1",
        movements=(),
        sections=(section,),
        archive_groups=(),
        galleries=(gallery,),
    )

    apply_changes(
        path,
        (locale,),
        artwork_keys={},
        source_layer_keys={},
        score_asset_keys={},
        score_video_keys={},
    )

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT kind, entry_id FROM search_entries ORDER BY kind, entry_id"
        ).fetchall() == [("gallery", "gallery")]
        connection.execute(
            "INSERT INTO gallery_groups VALUES "
            "('CN', 'gallery', 'RawGroup', 1, 'Raw', '', NULL, NULL)"
        )
        assert connection.execute(
            "SELECT group_id FROM gallery_groups WHERE group_id = 'RawGroup'"
        ).fetchone() == ("RawGroup",)

    assert find_missing_artwork_references(path) == ("background/top/bottom",)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute(
            "SELECT cg_id, asset_id, layout FROM gallery_narrative_asset_references"
        ).fetchone() == ("panel-artwork", "top/bottom", "vertical")
        assert connection.execute(
            "SELECT panel_asset_id, width, height FROM gallery_reference_panels ORDER BY position"
        ).fetchall() == [("top", 10, 20), ("bottom", 10, 30)]
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            connection.execute(
                "INSERT INTO gallery_reference_panels VALUES "
                "('CN', 'gallery', 'group', 0, 2, 'top', 10, 20)"
            )
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
            connection.execute(
                "INSERT INTO gallery_reference_panels VALUES "
                "('CN', 'gallery', 'group', 99, 0, 'orphan', 1, 1)"
            )
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            connection.execute(
                "INSERT INTO gallery_narrative_asset_references VALUES "
                "('CN', 'gallery', 'group', 1, 'panel-artwork', 'other', "
                "'background', 'none')"
            )

    image = PngArtifact.from_image(Image.new("RGBA", (1, 1), (1, 2, 3, 255)))
    artwork = ArtworkManifest(
        "artwork-v1",
        (ArtworkRecord("top/bottom", "background", image),),
        (),
    )
    apply_changes(
        path,
        (artwork,),
        artwork_keys={
            ("background", "top/bottom"): "ART/artwork-v1/composition/background/top/bottom.png"
        },
        source_layer_keys={},
        score_asset_keys={},
        score_video_keys={},
    )

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT title, thumbnail_object_key FROM search_entries WHERE kind = 'narrative_asset'"
        ).fetchone() == (
            "top/bottom",
            "ART/artwork-v1/composition/background/top/bottom.png",
        )

    assert find_missing_artwork_references(path) == ()
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM unit_versions WHERE unit = 'CN'")
        for table in (
            "story_collections",
            "sections",
            "galleries",
            "gallery_groups",
            "gallery_narrative_asset_references",
            "gallery_reference_panels",
        ):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_references_resolve_unique_upstream_case_variants(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    audio_path = tmp_path / "sound.wav"
    audio_path.write_bytes(b"RIFFaudio")
    story = StoryRecord(
        id="story",
        collection_id="archive_group:group",
        tag="before",
        tag_text="",
        code="",
        name="Story",
        info="",
        artwork_references=(
            StoryArtworkReference("assetid", "picture", "illustration"),
            StoryArtworkReference("ambiguous", "picture", "illustration"),
        ),
        text="",
        media_references=(StoryMediaReference("soundid", "sound"),),
    )
    locale = LocaleManifest(
        unit="CN",
        upstream_version="locale-v1",
        movements=(
            Movement(
                id="movement",
                position=0,
                movement_type="continue",
                name="Movement",
                icon_asset_id=None,
                logo_asset_id="scorelogo",
                background_asset_id=None,
                has_video=False,
                start_time=0,
                locations=(),
            ),
        ),
        sections=(),
        archive_groups=(
            ArchiveGroup(
                id="group",
                collection_id="archive_group:group",
                position=0,
                name="Group",
                archive_category="others",
                story_type=None,
                stories=(story,),
            ),
        ),
        galleries=(),
    )
    artwork = ArtworkManifest(
        "art-v1",
        (
            ArtworkRecord(
                "AssetID",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (1, 1))),
            ),
            ArtworkRecord(
                "Ambiguous",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (1, 1))),
            ),
            ArtworkRecord(
                "AMBIGUOUS",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (1, 1))),
            ),
        ),
        (),
        score_assets=(
            ScoreAssetRecord(
                "ScoreLogo",
                "logo",
                PngArtifact.from_image(Image.new("RGBA", (1, 1))),
            ),
        ),
        media=(
            MediaRecord(
                "SoundID",
                "audio",
                FileAudioArtifact.from_path(audio_path, content_type="audio/wav"),
            ),
        ),
    )

    apply_changes(
        path,
        (artwork, locale),
        artwork_keys={
            ("illustration", "AssetID"): "ART/art-v1/AssetID.png",
            ("illustration", "Ambiguous"): "ART/art-v1/Ambiguous.png",
            ("illustration", "AMBIGUOUS"): "ART/art-v1/AMBIGUOUS.png",
        },
        source_layer_keys={},
        score_asset_keys={("logo", "ScoreLogo"): "ART/art-v1/ScoreLogo.png"},
        score_video_keys={},
        media_keys={("audio", "SoundID"): "MEDIA/art-v1/SoundID.wav"},
    )

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT asset_id FROM story_narrative_image_references ORDER BY position"
        ).fetchall() == [("AssetID",), ("ambiguous",)]
        assert connection.execute(
            "SELECT asset_id FROM story_narrative_media_references"
        ).fetchone() == ("SoundID",)
        assert connection.execute("SELECT logo_asset_id FROM movements").fetchone() == (
            "ScoreLogo",
        )


def test_complete_artwork_rejects_an_empty_manifest(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)

    with pytest.raises(ValueError, match="contains no assets"):
        apply_changes(
            path,
            (ArtworkManifest("art-v1", (), ()),),
            artwork_keys={},
            source_layer_keys={},
            score_asset_keys={},
            score_video_keys={},
            complete_artwork=True,
        )

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM unit_versions").fetchone()[0] == 0


def test_complete_artwork_rejects_a_same_sized_disjoint_manifest(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    image = PngArtifact.from_image(Image.new("RGBA", (1, 1)))
    initial = ArtworkManifest(
        "art-v1",
        tuple(ArtworkRecord(f"asset-{index}", "illustration", image) for index in range(30)),
        (),
    )
    initial_keys = {
        (artwork.category, artwork.id): f"ART/art-v1/{artwork.id}.png"
        for artwork in initial.artworks
    }
    apply_changes(
        path,
        (initial,),
        artwork_keys=initial_keys,
        source_layer_keys={},
        score_asset_keys={},
        score_video_keys={},
    )
    disjoint = ArtworkManifest(
        "art-v2",
        tuple(ArtworkRecord(f"replacement-{index}", "illustration", image) for index in range(30)),
        (),
    )

    with pytest.raises(ValueError, match="would remove too many rows"):
        apply_changes(
            path,
            (disjoint,),
            artwork_keys={
                (artwork.category, artwork.id): f"ART/art-v2/{artwork.id}.png"
                for artwork in disjoint.artworks
            },
            source_layer_keys={},
            score_asset_keys={},
            score_video_keys={},
            complete_artwork=True,
        )

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM narrative_image_assets").fetchone()[0] == 30
        assert connection.execute(
            "SELECT res_version FROM unit_versions WHERE unit = 'artwork'"
        ).fetchone() == ("art-v1",)


def test_complete_artwork_accepts_case_only_identity_changes(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    image = PngArtifact.from_image(Image.new("RGBA", (1, 1)))
    initial = ArtworkManifest(
        "art-v1",
        tuple(ArtworkRecord(f"Asset-{index}", "illustration", image) for index in range(10)),
        (),
    )
    replacement = ArtworkManifest(
        "art-v2",
        tuple(ArtworkRecord(f"asset-{index}", "illustration", image) for index in range(10)),
        (),
    )

    for manifest in (initial, replacement):
        apply_changes(
            path,
            (manifest,),
            artwork_keys={
                (artwork.category, artwork.id): (
                    f"ART/{manifest.upstream_version}/{artwork.id}.png"
                )
                for artwork in manifest.artworks
            },
            source_layer_keys={},
            score_asset_keys={},
            score_video_keys={},
            complete_artwork=manifest is replacement,
        )

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT lower(asset_id) FROM narrative_image_assets ORDER BY lower(asset_id)"
        ).fetchall() == [(f"asset-{index}",) for index in range(10)]


def test_complete_artwork_counts_collapsed_case_variants_as_removals(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    image = PngArtifact.from_image(Image.new("RGBA", (1, 1)))
    initial = ArtworkManifest(
        "art-v1",
        tuple(
            ArtworkRecord(f"{prefix}-{index}", "illustration", image)
            for index in range(6)
            for prefix in ("Asset", "asset")
        ),
        (),
    )
    collapsed = ArtworkManifest(
        "art-v2",
        tuple(ArtworkRecord(f"asset-{index}", "illustration", image) for index in range(6)),
        (),
    )
    apply_changes(
        path,
        (initial,),
        artwork_keys={
            (artwork.category, artwork.id): f"ART/art-v1/{artwork.id}.png"
            for artwork in initial.artworks
        },
        source_layer_keys={},
        score_asset_keys={},
        score_video_keys={},
    )

    with pytest.raises(ValueError, match="would remove too many rows"):
        apply_changes(
            path,
            (collapsed,),
            artwork_keys={
                (artwork.category, artwork.id): f"ART/art-v2/{artwork.id}.png"
                for artwork in collapsed.artworks
            },
            source_layer_keys={},
            score_asset_keys={},
            score_video_keys={},
            complete_artwork=True,
        )


def test_complete_artwork_accepts_a_bounded_removal(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    image = PngArtifact.from_image(Image.new("RGBA", (1, 1)))
    initial = ArtworkManifest(
        "art-v1",
        tuple(ArtworkRecord(f"asset-{index}", "illustration", image) for index in range(100)),
        (),
    )
    replacement = ArtworkManifest("art-v2", initial.artworks[:91], ())

    for manifest in (initial, replacement):
        apply_changes(
            path,
            (manifest,),
            artwork_keys={
                (artwork.category, artwork.id): (
                    f"ART/{manifest.upstream_version}/{artwork.id}.png"
                )
                for artwork in manifest.artworks
            },
            source_layer_keys={},
            score_asset_keys={},
            score_video_keys={},
            complete_artwork=manifest is replacement,
        )

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM narrative_image_assets").fetchone()[0] == 91
