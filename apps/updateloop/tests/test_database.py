from __future__ import annotations

import sqlite3

import pytest
from PIL import Image

from arkwaifu_updateloop.database import (
    apply_changes,
    find_missing_art_references,
    initialize_or_validate,
    read_versions,
)
from arkwaifu_updateloop.domain import (
    ArtManifest,
    ArtRecord,
    CompositePanel,
    GalleryArtwork,
    GalleryDisplay,
    GalleryGroup,
    LocaleManifest,
    MovementSection,
    PngArtifact,
    SourceArtReference,
)


def test_fresh_database_has_the_current_schema_at_version_two(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"

    initialize_or_validate(path)
    initialize_or_validate(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert [row[1] for row in connection.execute("PRAGMA table_info(arts)")] == [
            "art_id",
            "category",
            "object_key",
            "byte_size",
            "width",
            "height",
        ]
        assert [row[1] for row in connection.execute("PRAGMA table_info(source_arts)")] == [
            "category",
            "source_art_id",
            "kind",
            "character_id",
            "role",
            "variant",
            "object_key",
            "byte_size",
            "width",
            "height",
        ]
        assert [row[1] for row in connection.execute("PRAGMA table_info(score_assets)")] == [
            "asset_kind",
            "asset_id",
            "object_key",
            "byte_size",
            "width",
            "height",
        ]
        assert [row[1] for row in connection.execute("PRAGMA table_info(story_collections)")] == [
            "locale",
            "collection_id",
            "collection_kind",
        ]
        assert [
            row[2] for row in connection.execute("PRAGMA index_info(story_art_references_by_art)")
        ] == ["locale", "art_id"]


def test_database_repairs_missing_performance_index_once(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    assert initialize_or_validate(path) is True
    with sqlite3.connect(path) as connection:
        connection.execute("DROP INDEX story_art_references_by_art")

    assert initialize_or_validate(path) is True
    assert initialize_or_validate(path) is False

    with sqlite3.connect(path) as connection:
        assert [
            row[2] for row in connection.execute("PRAGMA index_info(story_art_references_by_art)")
        ] == ["locale", "art_id"]


def test_database_rejects_an_unsupported_schema_version(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 3")

    with pytest.raises(ValueError, match="unsupported database schema version 3"):
        initialize_or_validate(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3


def test_database_writer_keeps_foreign_key_enforcement(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    image = PngArtifact.from_image(Image.new("RGBA", (1, 1), (1, 2, 3, 255)))
    manifest = ArtManifest(
        "v1",
        (
            ArtRecord(
                "character#1$1",
                "character",
                image,
                (SourceArtReference("character", "missing-source"),),
            ),
        ),
        (),
    )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        apply_changes(
            path,
            (manifest,),
            art_keys={
                (
                    "character",
                    "character#1$1",
                ): "ART/v1/composition/character/character%231%241.png"
            },
            source_keys={},
            score_asset_keys={},
            score_video_keys={},
        )

    assert read_versions(path) == {}


def test_archive_and_section_categories_are_explicit(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    archive_kinds = (
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
            ((f"archive_group:group-{position}",) for position, _kind in enumerate(archive_kinds)),
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
                for position, kind in enumerate(archive_kinds)
            ),
        )
        assert (
            tuple(
                row[0]
                for row in connection.execute(
                    "SELECT archive_kind FROM archive_groups ORDER BY position"
                )
            )
            == archive_kinds
        )
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute(
                "INSERT INTO story_collections VALUES ('CN', 'archive_group:old', 'archive_group')"
            )
            connection.execute(
                "INSERT INTO archive_groups VALUES "
                "('CN', 'old', 'archive_group:old', 7, 'Old', 'other', NULL)"
            )


def test_gallery_writer_constraints_cascade_and_composite_missing_art(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    section = MovementSection(
        id="set",
        collection_id="movement_section:set",
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
        CompositePanel("top", 0, 10, 20),
        CompositePanel("bottom", 1, 10, 30),
    )
    gallery = GalleryGroup(
        id="gallery",
        collection_id=section.collection_id,
        position=0,
        name="Gallery",
        description="Description",
        location_id="location",
        displays=(
            GalleryDisplay(
                id="display",
                position=0,
                name="Display",
                description="Sibling artworks",
                related_story_id=None,
                related_stage_id=None,
                artworks=(
                    GalleryArtwork(
                        position=0,
                        cg_id="composite",
                        art_id="top/bottom",
                        category="background",
                        composite_type="vertical",
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
        movement_sections=(section,),
        archive_groups=(),
        galleries=(gallery,),
    )

    apply_changes(
        path,
        (locale,),
        art_keys={},
        source_keys={},
        score_asset_keys={},
        score_video_keys={},
    )

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT kind, entry_id FROM search_entries ORDER BY kind, entry_id"
        ).fetchall() == [("gallery", "gallery")]

    assert find_missing_art_references(path) == ("background/top/bottom",)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute(
            "SELECT cg_id, art_id, composite_type FROM gallery_display_artworks"
        ).fetchone() == ("composite", "top/bottom", "vertical")
        assert connection.execute(
            "SELECT panel_art_id, width, height "
            "FROM gallery_display_artwork_panels ORDER BY position"
        ).fetchall() == [("top", 10, 20), ("bottom", 10, 30)]
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            connection.execute(
                "INSERT INTO gallery_display_artwork_panels VALUES "
                "('CN', 'gallery', 'display', 0, 2, 'top', 10, 20)"
            )
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
            connection.execute(
                "INSERT INTO gallery_display_artwork_panels VALUES "
                "('CN', 'gallery', 'display', 99, 0, 'orphan', 1, 1)"
            )
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            connection.execute(
                "INSERT INTO gallery_display_artworks VALUES "
                "('CN', 'gallery', 'display', 1, 'composite', 'other', "
                "'background', 'none')"
            )

    image = PngArtifact.from_image(Image.new("RGBA", (1, 1), (1, 2, 3, 255)))
    art = ArtManifest(
        "art-v1",
        (ArtRecord("top/bottom", "background", image),),
        (),
    )
    apply_changes(
        path,
        (art,),
        art_keys={("background", "top/bottom"): "ART/art-v1/composition/background/top/bottom.png"},
        source_keys={},
        score_asset_keys={},
        score_video_keys={},
    )

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT title, thumbnail_object_key FROM search_entries "
            "WHERE kind = 'art'"
        ).fetchone() == (
            "top/bottom",
            "ART/art-v1/composition/background/top/bottom.png",
        )

    assert find_missing_art_references(path) == ()
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM unit_versions WHERE unit = 'CN'")
        for table in (
            "story_collections",
            "movement_sections",
            "gallery_groups",
            "gallery_displays",
            "gallery_display_artworks",
            "gallery_display_artwork_panels",
        ):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
