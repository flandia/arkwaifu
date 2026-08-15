"""Create and update the local SQLite archive published by the update loop."""

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
    """Return the upstream version recorded for each available dataset."""

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
    source_keys: Mapping[tuple[str, str], str],
    score_asset_keys: Mapping[tuple[str, str], str],
    score_video_keys: Mapping[str, str],
) -> frozenset[str]:
    """Apply all manifests atomically and return every referenced object key."""

    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            for manifest in manifests:
                if isinstance(manifest, ArtManifest):
                    _apply_art(
                        connection,
                        manifest,
                        art_keys,
                        source_keys,
                        score_asset_keys,
                        score_video_keys,
                    )
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
                """
                SELECT object_key FROM arts
                UNION SELECT object_key FROM source_arts
                UNION SELECT object_key FROM score_assets
                UNION SELECT object_key FROM score_videos
                """
            )
        )
    finally:
        connection.close()


def _apply_art(
    connection: sqlite3.Connection,
    manifest: ArtManifest,
    art_keys: Mapping[tuple[str, str], str],
    source_keys: Mapping[tuple[str, str], str],
    score_asset_keys: Mapping[tuple[str, str], str],
    score_video_keys: Mapping[str, str],
) -> None:
    connection.execute(
        """
        INSERT INTO unit_versions (unit, res_version) VALUES ('art', ?)
        ON CONFLICT (unit) DO UPDATE SET res_version = excluded.res_version
        """,
        (manifest.upstream_version,),
    )
    candidate_schema = """
        DROP TABLE IF EXISTS candidate_art_source_refs;
        DROP TABLE IF EXISTS candidate_arts;
        DROP TABLE IF EXISTS candidate_source_arts;
        DROP TABLE IF EXISTS candidate_score_assets;
        DROP TABLE IF EXISTS candidate_score_videos;

        CREATE TEMP TABLE candidate_source_arts (
            category TEXT NOT NULL,
            source_art_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            character_id TEXT,
            role TEXT,
            variant TEXT,
            object_key TEXT NOT NULL UNIQUE,
            byte_size INTEGER NOT NULL CHECK (byte_size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            PRIMARY KEY (category, source_art_id)
        ) STRICT;
        CREATE TEMP TABLE candidate_arts (
            category TEXT NOT NULL,
            art_id TEXT NOT NULL,
            object_key TEXT NOT NULL UNIQUE,
            byte_size INTEGER NOT NULL CHECK (byte_size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            PRIMARY KEY (category, art_id)
        ) STRICT;
        CREATE TEMP TABLE candidate_art_source_refs (
            category TEXT NOT NULL,
            art_id TEXT NOT NULL,
            position INTEGER NOT NULL CHECK (position >= 0),
            source_category TEXT NOT NULL,
            source_art_id TEXT NOT NULL,
            PRIMARY KEY (category, art_id, position),
            UNIQUE (category, art_id, source_category, source_art_id),
            FOREIGN KEY (category, art_id)
                REFERENCES candidate_arts (category, art_id) ON DELETE CASCADE
        ) STRICT;
        CREATE TEMP TABLE candidate_score_assets (
            asset_kind TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            object_key TEXT NOT NULL UNIQUE,
            byte_size INTEGER NOT NULL CHECK (byte_size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            PRIMARY KEY (asset_kind, asset_id)
        ) STRICT;
        CREATE TEMP TABLE candidate_score_videos (
            video_id TEXT PRIMARY KEY,
            object_key TEXT NOT NULL UNIQUE,
            byte_size INTEGER NOT NULL CHECK (byte_size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            frame_rate_numerator INTEGER NOT NULL CHECK (frame_rate_numerator > 0),
            frame_rate_denominator INTEGER NOT NULL CHECK (frame_rate_denominator > 0),
            frame_count INTEGER NOT NULL CHECK (frame_count > 0)
        ) STRICT;
        """
    for statement in candidate_schema.split(";"):
        if statement.strip():
            connection.execute(statement)
    connection.executemany(
        """
        INSERT INTO candidate_source_arts
            (category, source_art_id, kind, character_id, role, variant,
             object_key, byte_size, width, height)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                source.category,
                source.id,
                source.kind,
                source.character_id,
                source.role,
                source.variant,
                source_keys[(source.category, source.id)],
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
            (category, art_id, object_key, byte_size, width, height)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                art.category,
                art.id,
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
            (category, art_id, position, source_category, source_art_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            (art.category, art.id, position, source.category, source.id)
            for art in manifest.arts
            for position, source in enumerate(art.source_art_references)
        ),
    )
    connection.executemany(
        """
        INSERT INTO candidate_score_assets
            (asset_kind, asset_id, object_key, byte_size, width, height)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                asset.kind,
                asset.id,
                score_asset_keys[(asset.kind, asset.id)],
                asset.image.byte_size,
                asset.image.width,
                asset.image.height,
            )
            for asset in manifest.score_assets
        ),
    )
    connection.executemany(
        """
        INSERT INTO candidate_score_videos
            (video_id, object_key, byte_size, width, height,
             frame_rate_numerator, frame_rate_denominator, frame_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                video.id,
                score_video_keys[video.id],
                video.video.byte_size,
                video.video.width,
                video.video.height,
                video.video.frame_rate_numerator,
                video.video.frame_rate_denominator,
                video.video.frame_count,
            )
            for video in manifest.score_videos
        ),
    )

    connection.execute(
        """
        INSERT INTO source_arts
            (category, source_art_id, kind, character_id, role, variant,
             object_key, byte_size, width, height)
        SELECT category, source_art_id, kind, character_id, role, variant,
               object_key, byte_size, width, height
        FROM candidate_source_arts WHERE true
        ON CONFLICT (category, source_art_id) DO UPDATE SET
            kind = excluded.kind,
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
        INSERT INTO arts (category, art_id, object_key, byte_size, width, height)
        SELECT category, art_id, object_key, byte_size, width, height
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
        INSERT INTO score_assets
            (asset_kind, asset_id, object_key, byte_size, width, height)
        SELECT asset_kind, asset_id, object_key, byte_size, width, height
        FROM candidate_score_assets WHERE true
        ON CONFLICT (asset_kind, asset_id) DO UPDATE SET
            object_key = excluded.object_key,
            byte_size = excluded.byte_size,
            width = excluded.width,
            height = excluded.height
        """
    )
    connection.execute(
        """
        INSERT INTO score_videos
            (video_id, object_key, byte_size, width, height,
             frame_rate_numerator, frame_rate_denominator, frame_count)
        SELECT video_id, object_key, byte_size, width, height,
               frame_rate_numerator, frame_rate_denominator, frame_count
        FROM candidate_score_videos WHERE true
        ON CONFLICT (video_id) DO UPDATE SET
            object_key = excluded.object_key,
            byte_size = excluded.byte_size,
            width = excluded.width,
            height = excluded.height,
            frame_rate_numerator = excluded.frame_rate_numerator,
            frame_rate_denominator = excluded.frame_rate_denominator,
            frame_count = excluded.frame_count
        """
    )
    connection.execute(
        """
        DELETE FROM art_source_refs
        WHERE (category, art_id) IN (SELECT category, art_id FROM candidate_arts)
        """
    )
    connection.execute(
        """
        INSERT INTO art_source_refs
            (category, art_id, position, source_category, source_art_id)
        SELECT category, art_id, position, source_category, source_art_id
        FROM candidate_art_source_refs
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
        INSERT INTO story_collections (locale, collection_id, collection_kind)
        VALUES (?, ?, ?)
        """,
        (
            *(
                (unit, section.collection_id, "movement_section")
                for section in manifest.movement_sections
            ),
            *(
                (unit, archive.collection_id, "archive_group")
                for archive in manifest.archive_groups
            ),
        ),
    )
    connection.executemany(
        """
        INSERT INTO movements
            (locale, movement_id, position, movement_type, name,
             icon_asset_id, logo_asset_id, background_asset_id, has_video, start_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                movement.id,
                movement.position,
                movement.movement_type,
                movement.name,
                movement.icon_asset_id,
                movement.logo_asset_id,
                movement.background_asset_id,
                int(movement.has_video),
                movement.start_time,
            )
            for movement in manifest.movements
        ),
    )
    connection.executemany(
        """
        INSERT INTO movement_sections
            (locale, section_id, collection_id, section_type, name, review_group_id,
             sort_by_year, sort_within_year, key_visual_asset_id, title_asset_id,
             background_asset_id, decoration_asset_id, retro_background_asset_id,
             description, has_video)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                section.id,
                section.collection_id,
                section.section_type,
                section.name,
                section.review_group_id,
                section.sort_by_year,
                section.sort_within_year,
                section.key_visual_asset_id,
                section.title_asset_id,
                section.background_asset_id,
                section.decoration_asset_id,
                section.retro_background_asset_id,
                section.description,
                int(section.has_video),
            )
            for section in manifest.movement_sections
        ),
    )
    connection.executemany(
        """
        INSERT INTO movement_locations
            (locale, movement_id, location_id, position, location_type, sort_id,
             start_time, present_stage_id, unlock_stage_id, section_id,
             split_icon_asset_id, split_sub_name, video_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                movement.id,
                location.id,
                location.position,
                location.location_type,
                location.sort_id,
                location.start_time,
                location.present_stage_id,
                location.unlock_stage_id,
                location.section_id,
                location.split_icon_asset_id,
                location.split_sub_name,
                location.video_id,
            )
            for movement in manifest.movements
            for location in movement.locations
        ),
    )
    connection.executemany(
        """
        INSERT INTO archive_groups
            (locale, archive_id, collection_id, position, name, archive_kind, story_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                archive.id,
                archive.collection_id,
                archive.position,
                archive.name,
                archive.archive_kind,
                archive.story_type,
            )
            for archive in manifest.archive_groups
        ),
    )
    groups = (*manifest.movement_sections, *manifest.archive_groups)
    connection.executemany(
        """
        INSERT INTO stories
            (locale, story_id, collection_id, tag, tag_text, code, name, info, position)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                story.id,
                story.collection_id,
                story.tag,
                story.tag_text,
                story.code,
                story.name,
                story.info,
                story_position,
            )
            for group in groups
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
            for group in groups
            for story in group.stories
            for reference_position, reference in enumerate(story.art_references)
        ),
    )
    connection.executemany(
        """
        INSERT INTO gallery_groups
            (locale, gallery_id, collection_id, position, name, description, location_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                gallery.id,
                gallery.collection_id,
                gallery.position,
                gallery.name,
                gallery.description,
                gallery.location_id,
            )
            for gallery in manifest.galleries
        ),
    )
    connection.executemany(
        """
        INSERT INTO gallery_displays
            (locale, gallery_id, display_id, position, name, description,
             related_story_id, related_stage_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                gallery.id,
                display.id,
                display.position,
                display.name,
                display.description,
                display.related_story_id,
                display.related_stage_id,
            )
            for gallery in manifest.galleries
            for display in gallery.displays
        ),
    )
    connection.executemany(
        """
        INSERT INTO gallery_display_artworks
            (locale, gallery_id, display_id, position, cg_id, art_id,
             category, composite_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                gallery.id,
                display.id,
                artwork.position,
                artwork.cg_id,
                artwork.art_id,
                artwork.category,
                artwork.composite_type,
            )
            for gallery in manifest.galleries
            for display in gallery.displays
            for artwork in display.artworks
        ),
    )
    connection.executemany(
        """
        INSERT INTO gallery_display_artwork_panels
            (locale, gallery_id, display_id, artwork_position,
             position, panel_art_id, width, height)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                gallery.id,
                display.id,
                artwork.position,
                panel.position,
                panel.id,
                panel.width,
                panel.height,
            )
            for gallery in manifest.galleries
            for display in gallery.displays
            for artwork in display.artworks
            for panel in artwork.panels
        ),
    )


def find_missing_art_references(path: Path) -> tuple[str, ...]:
    """Return locale art identifiers absent from the current art set."""

    connection = _connect(path)
    try:
        return tuple(
            str(row[0])
            for row in connection.execute(
                """
                WITH referenced AS (
                    SELECT category, art_id FROM story_art_references
                    UNION
                    SELECT category, art_id FROM gallery_display_artworks
                )
                SELECT referenced.category || '/' || referenced.art_id
                FROM referenced
                LEFT JOIN arts USING (category, art_id)
                WHERE arts.art_id IS NULL
                ORDER BY referenced.category, referenced.art_id
                """
            )
        )
    finally:
        connection.close()


def find_missing_score_references(path: Path) -> tuple[str, ...]:
    """Return declared Score PNG and video identifiers absent from the art set."""

    connection = _connect(path)
    try:
        return tuple(
            str(row[0])
            for row in connection.execute(
                """
                WITH declared_assets(asset_kind, asset_id) AS (
                    SELECT 'icon', icon_asset_id FROM movements WHERE icon_asset_id IS NOT NULL
                    UNION SELECT 'logo', logo_asset_id FROM movements
                        WHERE logo_asset_id IS NOT NULL
                    UNION SELECT 'background', background_asset_id FROM movements
                        WHERE background_asset_id IS NOT NULL
                    UNION SELECT 'key_visual', key_visual_asset_id FROM movement_sections
                        WHERE key_visual_asset_id IS NOT NULL
                    UNION SELECT 'title', title_asset_id FROM movement_sections
                        WHERE title_asset_id IS NOT NULL
                    UNION SELECT 'background', background_asset_id FROM movement_sections
                        WHERE background_asset_id IS NOT NULL
                    UNION SELECT 'decoration', decoration_asset_id FROM movement_sections
                        WHERE decoration_asset_id IS NOT NULL
                    UNION SELECT 'retro_background', retro_background_asset_id
                        FROM movement_sections WHERE retro_background_asset_id IS NOT NULL
                    UNION SELECT 'split', split_icon_asset_id FROM movement_locations
                        WHERE split_icon_asset_id IS NOT NULL
                ), missing_assets AS (
                    SELECT 'score/' || declared.asset_kind || '/' || declared.asset_id AS identity
                    FROM declared_assets AS declared
                    LEFT JOIN score_assets AS available USING (asset_kind, asset_id)
                    WHERE available.asset_id IS NULL
                ), missing_videos AS (
                    SELECT 'score/video/' || locations.video_id AS identity
                    FROM movement_locations AS locations
                    LEFT JOIN score_videos AS available USING (video_id)
                    WHERE locations.video_id IS NOT NULL AND available.video_id IS NULL
                )
                SELECT identity FROM missing_assets
                UNION SELECT identity FROM missing_videos
                ORDER BY identity
                """
            )
        )
    finally:
        connection.close()
