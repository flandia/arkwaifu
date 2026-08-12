from __future__ import annotations

import sqlite3

import pytest
from PIL import Image

from arkwaifu_updateloop.database import (
    apply_changes,
    initialize_or_validate,
    read_versions,
)
from arkwaifu_updateloop.domain import ArtManifest, ArtRecord, PngArtifact


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
            "source_art_id",
            "character_id",
            "role",
            "variant",
            "object_key",
            "byte_size",
            "width",
            "height",
        ]


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
        (ArtRecord("character#1$1", "character", image, ("missing-source",)),),
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
        )

    assert read_versions(path) == {}
