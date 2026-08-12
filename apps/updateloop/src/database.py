"""Create and update the local SQLite database published by the update loop."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from importlib.resources import files
from pathlib import Path

from .domain import ArtManifest, LocaleManifest

SCHEMA_VERSION = 2
_ART_REFERENCE_INDEX = "story_art_references_by_art"
_ART_REFERENCE_INDEX_COLUMNS = ("locale", "art_id")


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = DELETE")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def _read_schema() -> str:
    return files("arkwaifu_updateloop").joinpath("arkwaifu.sql").read_text(encoding="utf-8")


def initialize_or_validate(path: Path) -> bool:
    """Prepare a supported database and report whether it must be republished."""

    path.parent.mkdir(parents=True, exist_ok=True)
    created = not path.exists()
    if created:
        connection = _connect(path)
        try:
            connection.executescript(_read_schema())
        finally:
            connection.close()
    validate_schema_version(path)
    return created or _ensure_performance_indexes(path)


def _ensure_performance_indexes(path: Path) -> bool:
    connection = _connect(path)
    try:
        columns = tuple(
            str(row[2]) for row in connection.execute(f"PRAGMA index_info({_ART_REFERENCE_INDEX})")
        )
        if columns == _ART_REFERENCE_INDEX_COLUMNS:
            return False
        if columns:
            raise ValueError(
                f"SQLite index {_ART_REFERENCE_INDEX} has columns {columns}, "
                f"expected {_ART_REFERENCE_INDEX_COLUMNS}"
            )
        connection.execute(
            f"CREATE INDEX {_ART_REFERENCE_INDEX} ON story_art_references (locale, art_id)"
        )
        return True
    finally:
        connection.close()


def validate_schema_version(path: Path) -> None:
    """Require the database's declared schema version without scanning its contents."""

    connection = sqlite3.connect(path)
    try:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported database schema version {version}, expected {SCHEMA_VERSION}"
            )
    finally:
        connection.close()


def read_versions(path: Path) -> dict[str, str]:
    """Return the published upstream version recorded for each available dataset."""

    connection = _connect(path)
    try:
        return {
            str(unit): str(res_version)
            for unit, res_version in connection.execute(
                "SELECT unit, res_version FROM unit_versions"
            )
        }
    finally:
        connection.close()


def apply_changes(
    path: Path,
    manifests: Sequence[ArtManifest | LocaleManifest],
    *,
    art_keys: Mapping[tuple[str, str], str],
    source_keys: Mapping[str, str],
) -> frozenset[str]:
    """Apply every manifest in one transaction and return referenced PNG keys.

    Art manifests overlay the current category-qualified art set. Locale
    manifests replace the complete selected locale through the cascading
    unit-version foreign key.
    """

    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            for manifest in manifests:
                if isinstance(manifest, ArtManifest):
                    _apply_art(connection, manifest, art_keys, source_keys)
            for manifest in manifests:
                if isinstance(manifest, LocaleManifest):
                    _replace_locale(connection, manifest)
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        return frozenset(
            str(row[0])
            for row in connection.execute(
                "SELECT object_key FROM arts UNION SELECT object_key FROM source_arts"
            )
        )
    finally:
        connection.close()


def _apply_art(
    connection: sqlite3.Connection,
    manifest: ArtManifest,
    art_keys: Mapping[tuple[str, str], str],
    source_keys: Mapping[str, str],
) -> None:
    connection.execute(
        """
        INSERT INTO unit_versions (unit, res_version) VALUES ('art', ?)
        ON CONFLICT (unit) DO UPDATE SET res_version = excluded.res_version
        """,
        (manifest.upstream_version,),
    )
    connection.execute(
        """
        CREATE TEMP TABLE candidate_source_arts (
            source_art_id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('body', 'face', 'whole_body')),
            variant TEXT NOT NULL CHECK (length(variant) > 0),
            object_key TEXT NOT NULL UNIQUE,
            byte_size INTEGER NOT NULL CHECK (byte_size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0)
        ) STRICT
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE candidate_arts (
            art_id TEXT NOT NULL,
            category TEXT NOT NULL
                CHECK (category IN ('image', 'background', 'item', 'character')),
            object_key TEXT NOT NULL UNIQUE,
            byte_size INTEGER NOT NULL CHECK (byte_size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            PRIMARY KEY (category, art_id)
        ) STRICT
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE candidate_art_source_refs (
            category TEXT NOT NULL CHECK (category = 'character'),
            art_id TEXT NOT NULL,
            position INTEGER NOT NULL CHECK (position >= 0),
            source_art_id TEXT NOT NULL,
            PRIMARY KEY (category, art_id, position),
            UNIQUE (category, art_id, source_art_id),
            FOREIGN KEY (category, art_id)
                REFERENCES candidate_arts (category, art_id) ON DELETE CASCADE
        ) STRICT
        """
    )
    connection.executemany(
        """
        INSERT INTO candidate_source_arts
            (source_art_id, character_id, role, variant, object_key,
             byte_size, width, height)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                source.id,
                source.character_id,
                source.role,
                source.variant,
                source_keys[source.id],
                source.image.byte_size,
                source.image.width,
                source.image.height,
            )
            for source in manifest.source_arts
        ),
    )
    connection.executemany(
        """
        INSERT INTO candidate_arts
            (art_id, category, object_key, byte_size, width, height)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                art.id,
                art.category,
                art_keys[(art.category, art.id)],
                art.image.byte_size,
                art.image.width,
                art.image.height,
            )
            for art in manifest.arts
        ),
    )
    connection.executemany(
        """
        INSERT INTO candidate_art_source_refs
            (category, art_id, position, source_art_id)
        VALUES (?, ?, ?, ?)
        """,
        (
            (art.category, art.id, position, source_id)
            for art in manifest.arts
            for position, source_id in enumerate(art.source_art_ids)
        ),
    )

    connection.execute(
        """
        INSERT INTO source_arts
            (source_art_id, character_id, role, variant, object_key,
             byte_size, width, height)
        SELECT source_art_id, character_id, role, variant, object_key,
               byte_size, width, height
        FROM candidate_source_arts WHERE true
        ON CONFLICT (source_art_id) DO UPDATE SET
            character_id = excluded.character_id,
            role = excluded.role,
            variant = excluded.variant,
            object_key = excluded.object_key,
            byte_size = excluded.byte_size,
            width = excluded.width,
            height = excluded.height
        """
    )
    connection.execute(
        """
        INSERT INTO arts
            (art_id, category, object_key, byte_size, width, height)
        SELECT art_id, category, object_key, byte_size, width, height
        FROM candidate_arts WHERE true
        ON CONFLICT (category, art_id) DO UPDATE SET
            object_key = excluded.object_key,
            byte_size = excluded.byte_size,
            width = excluded.width,
            height = excluded.height
        """
    )
    connection.execute(
        """
        DELETE FROM art_source_refs
        WHERE (category, art_id) IN (
            SELECT candidate.category, candidate.art_id
            FROM candidate_arts AS candidate
            JOIN arts USING (category, art_id)
            WHERE arts.object_key = candidate.object_key
        )
        """
    )
    connection.execute(
        """
        INSERT INTO art_source_refs (category, art_id, position, source_art_id)
        SELECT reference.category, reference.art_id,
               reference.position, reference.source_art_id
        FROM candidate_art_source_refs AS reference
        JOIN candidate_arts AS candidate USING (category, art_id)
        JOIN arts USING (category, art_id)
        WHERE arts.object_key = candidate.object_key
        """
    )


def _replace_locale(connection: sqlite3.Connection, manifest: LocaleManifest) -> None:
    unit = manifest.unit
    connection.execute("DELETE FROM unit_versions WHERE unit = ?", (unit,))
    connection.execute(
        "INSERT INTO unit_versions (unit, res_version) VALUES (?, ?)",
        (unit, manifest.upstream_version),
    )
    connection.executemany(
        """
        INSERT INTO story_groups (locale, group_id, name, group_type, position)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            (unit, group.id, group.name, group.group_type, group_position)
            for group_position, group in enumerate(manifest.story_groups)
        ),
    )
    connection.executemany(
        """
        INSERT INTO stories
            (locale, story_id, group_id, tag, tag_text, code, name, info, position)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                story.id,
                group.id,
                story.tag,
                story.tag_text,
                story.code,
                story.name,
                story.info,
                story_position,
            )
            for group in manifest.story_groups
            for story_position, story in enumerate(group.stories)
        ),
    )
    connection.executemany(
        """
        INSERT INTO story_art_references
            (locale, story_id, position, art_id, kind, category,
             title, subtitle, names_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                story.id,
                reference_position,
                reference.art_id,
                reference.kind,
                reference.category,
                reference.title,
                reference.subtitle,
                json.dumps(reference.names, ensure_ascii=False, separators=(",", ":")),
            )
            for group in manifest.story_groups
            for story in group.stories
            for reference_position, reference in enumerate(story.art_references)
        ),
    )
    connection.executemany(
        """
        INSERT INTO galleries (locale, gallery_id, name, description)
        VALUES (?, ?, ?, ?)
        """,
        ((unit, gallery.id, gallery.name, gallery.description) for gallery in manifest.galleries),
    )
    connection.executemany(
        """
        INSERT INTO gallery_entries
            (locale, gallery_id, position, entry_id, name, description, art_id, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                gallery.id,
                entry.position,
                entry.id,
                entry.name,
                entry.description,
                entry.art_id,
                entry.category,
            )
            for gallery in manifest.galleries
            for entry in gallery.entries
        ),
    )


def find_missing_art_references(path: Path) -> tuple[str, ...]:
    """Return locale art identifiers which are absent from the current art set."""

    connection = _connect(path)
    try:
        return tuple(
            str(row[0])
            for row in connection.execute(
                """
            WITH referenced AS (
                SELECT category, art_id FROM story_art_references
                UNION
                SELECT category, art_id FROM gallery_entries
            )
            SELECT referenced.category || '/' || referenced.art_id
            FROM referenced
            LEFT JOIN arts USING (category, art_id)
            WHERE arts.art_id IS NULL
            ORDER BY referenced.art_id
            """
            )
        )
    finally:
        connection.close()
