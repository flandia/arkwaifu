from __future__ import annotations

import sqlite3

import pytest
from PIL import Image

from arkwaifu_updateloop.database import (
    apply_changes,
    initialize_or_validate,
    read_versions,
    validate_schema_version,
)
from arkwaifu_updateloop.domain import ArtManifest, ArtRecord, PngArtifact


def test_database_validation_keeps_schema_version_compatibility_check(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 2")

    with pytest.raises(ValueError, match="unsupported database schema version 2"):
        validate_schema_version(path)


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
            art_keys={"character#1$1": "ART/v1/composition/character/character%231%241.png"},
            source_keys={},
        )

    assert read_versions(path) == {}
