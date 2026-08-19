"""Create and update the local SQLite archive published by the update loop."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from importlib.resources import files
from pathlib import Path

from .domain import ArtworkManifest, FileAudioArtifact, FileVideoArtifact, LocaleManifest

SCHEMA_VERSION = 2
_NARRATIVE_IMAGE_REFERENCE_INDEX = "story_narrative_image_references_by_asset"
_NARRATIVE_IMAGE_REFERENCE_INDEX_COLUMNS = ("locale", "category", "asset_id")


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
            str(row[2])
            for row in connection.execute(f"PRAGMA index_info({_NARRATIVE_IMAGE_REFERENCE_INDEX})")
        )
        if columns == _NARRATIVE_IMAGE_REFERENCE_INDEX_COLUMNS:
            return False
        if columns:
            raise ValueError(
                f"SQLite index {_NARRATIVE_IMAGE_REFERENCE_INDEX} has columns {columns}, "
                f"expected {_NARRATIVE_IMAGE_REFERENCE_INDEX_COLUMNS}"
            )
        connection.execute(
            f"CREATE INDEX {_NARRATIVE_IMAGE_REFERENCE_INDEX} "
            "ON story_narrative_image_references (locale, category, asset_id)"
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
    manifests: Sequence[ArtworkManifest | LocaleManifest],
    *,
    artwork_keys: Mapping[tuple[str, str], str],
    source_layer_keys: Mapping[tuple[str, str], str],
    score_asset_keys: Mapping[tuple[str, str], str],
    score_video_keys: Mapping[str, str],
    media_keys: Mapping[tuple[str, str], str] | None = None,
) -> frozenset[str]:
    """Apply all manifests atomically and return every referenced object key."""

    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            for manifest in manifests:
                if isinstance(manifest, ArtworkManifest):
                    _apply_artwork(
                        connection,
                        manifest,
                        artwork_keys,
                        source_layer_keys,
                        score_asset_keys,
                        score_video_keys,
                        media_keys or {},
                    )
            for manifest in manifests:
                if isinstance(manifest, LocaleManifest):
                    _replace_locale(connection, manifest)
            _rebuild_search_entries(connection)
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        return frozenset(
            str(row[0])
            for row in connection.execute(
                """
                SELECT object_key FROM narrative_image_assets
                UNION SELECT object_key FROM material_assets
                UNION SELECT object_key FROM presentation_image_assets
                UNION SELECT object_key FROM presentation_video_assets
                UNION SELECT object_key FROM narrative_media_assets
                """
            )
        )
    finally:
        connection.close()


def _apply_artwork(
    connection: sqlite3.Connection,
    manifest: ArtworkManifest,
    artwork_keys: Mapping[tuple[str, str], str],
    source_layer_keys: Mapping[tuple[str, str], str],
    score_asset_keys: Mapping[tuple[str, str], str],
    score_video_keys: Mapping[str, str],
    media_keys: Mapping[tuple[str, str], str],
) -> None:
    connection.execute(
        """
        INSERT INTO unit_versions (unit, res_version) VALUES ('artwork', ?)
        ON CONFLICT (unit) DO UPDATE SET res_version = excluded.res_version
        """,
        (manifest.upstream_version,),
    )
    candidate_schema = """
        DROP TABLE IF EXISTS candidate_narrative_asset_material_references;
        DROP TABLE IF EXISTS candidate_narrative_image_assets;
        DROP TABLE IF EXISTS candidate_material_assets;
        DROP TABLE IF EXISTS candidate_presentation_image_assets;
        DROP TABLE IF EXISTS candidate_presentation_video_assets;
        DROP TABLE IF EXISTS candidate_narrative_media_assets;

        CREATE TEMP TABLE candidate_material_assets (
            category TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            material_type TEXT NOT NULL,
            character_id TEXT,
            role TEXT,
            variant TEXT,
            object_key TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL CHECK (size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            PRIMARY KEY (category, asset_id)
        ) STRICT;
        CREATE TEMP TABLE candidate_narrative_image_assets (
            category TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            object_key TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL CHECK (size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            PRIMARY KEY (category, asset_id)
        ) STRICT;
        CREATE TEMP TABLE candidate_narrative_asset_material_references (
            category TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            position INTEGER NOT NULL CHECK (position >= 0),
            material_category TEXT NOT NULL,
            material_asset_id TEXT NOT NULL,
            PRIMARY KEY (category, asset_id, position),
            UNIQUE (category, asset_id, material_category, material_asset_id),
            FOREIGN KEY (category, asset_id)
                REFERENCES candidate_narrative_image_assets (category, asset_id) ON DELETE CASCADE
        ) STRICT;
        CREATE TEMP TABLE candidate_presentation_image_assets (
            category TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            object_key TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL CHECK (size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            PRIMARY KEY (category, asset_id)
        ) STRICT;
        CREATE TEMP TABLE candidate_presentation_video_assets (
            category TEXT NOT NULL CHECK (category = 'video'),
            asset_id TEXT NOT NULL,
            object_key TEXT NOT NULL UNIQUE,
            mime TEXT NOT NULL,
            size INTEGER NOT NULL CHECK (size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            frame_rate_numerator INTEGER NOT NULL CHECK (frame_rate_numerator > 0),
            frame_rate_denominator INTEGER NOT NULL CHECK (frame_rate_denominator > 0),
            frame_count INTEGER NOT NULL CHECK (frame_count > 0),
            PRIMARY KEY (category, asset_id)
        ) STRICT;
        CREATE TEMP TABLE candidate_narrative_media_assets (
            category TEXT NOT NULL CHECK (category IN ('audio', 'video')),
            asset_id TEXT NOT NULL,
            object_key TEXT NOT NULL UNIQUE,
            mime TEXT NOT NULL,
            size INTEGER NOT NULL CHECK (size > 0),
            duration REAL,
            sample_rate INTEGER,
            width INTEGER,
            height INTEGER,
            frame_rate_numerator INTEGER,
            frame_rate_denominator INTEGER,
            frame_count INTEGER,
            PRIMARY KEY (category, asset_id)
        ) STRICT;
        """
    for statement in candidate_schema.split(";"):
        if statement.strip():
            connection.execute(statement)
    connection.executemany(
        """
        INSERT INTO candidate_material_assets
            (category, asset_id, material_type, character_id, role, variant,
             object_key, size, width, height)
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
                source_layer_keys[(source.category, source.id)],
                source.image.byte_size,
                source.image.width,
                source.image.height,
            )
            for source in manifest.source_layers
        ),
    )
    connection.executemany(
        """
        INSERT INTO candidate_narrative_media_assets
            (category, asset_id, object_key, mime, size, duration,
             sample_rate, width, height, frame_rate_numerator,
             frame_rate_denominator, frame_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                media.kind,
                media.id,
                media_keys[(media.kind, media.id)],
                media.artifact.content_type,
                media.artifact.byte_size,
                media.artifact.duration if isinstance(media.artifact, FileAudioArtifact) else None,
                media.artifact.sample_rate
                if isinstance(media.artifact, FileAudioArtifact)
                else None,
                media.artifact.width if isinstance(media.artifact, FileVideoArtifact) else None,
                media.artifact.height if isinstance(media.artifact, FileVideoArtifact) else None,
                media.artifact.frame_rate_numerator
                if isinstance(media.artifact, FileVideoArtifact)
                else None,
                media.artifact.frame_rate_denominator
                if isinstance(media.artifact, FileVideoArtifact)
                else None,
                media.artifact.frame_count
                if isinstance(media.artifact, FileVideoArtifact)
                else None,
            )
            for media in manifest.media
        ),
    )
    connection.executemany(
        """
        INSERT INTO candidate_narrative_image_assets
            (category, asset_id, object_key, size, width, height)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                artwork.category,
                artwork.id,
                artwork_keys[(artwork.category, artwork.id)],
                artwork.image.byte_size,
                artwork.image.width,
                artwork.image.height,
            )
            for artwork in manifest.artworks
        ),
    )
    connection.executemany(
        """
        INSERT INTO candidate_narrative_asset_material_references
            (category, asset_id, position, material_category, material_asset_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            (artwork.category, artwork.id, position, source.category, source.id)
            for artwork in manifest.artworks
            for position, source in enumerate(artwork.source_layer_references)
        ),
    )
    connection.executemany(
        """
        INSERT INTO candidate_presentation_image_assets
            (category, asset_id, object_key, size, width, height)
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
        INSERT INTO candidate_presentation_video_assets
            (category, asset_id, object_key, mime, size, width, height,
             frame_rate_numerator, frame_rate_denominator, frame_count)
        VALUES ('video', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                video.id,
                score_video_keys[video.id],
                video.video.content_type,
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
        INSERT INTO material_assets
            (category, asset_id, material_type, character_id, role, variant,
             object_key, size, width, height)
        SELECT category, asset_id, material_type, character_id, role, variant,
               object_key, size, width, height
        FROM candidate_material_assets WHERE true
        ON CONFLICT (category, asset_id) DO UPDATE SET
            material_type = excluded.material_type,
            character_id = excluded.character_id,
            role = excluded.role,
            variant = excluded.variant,
            object_key = excluded.object_key,
            size = excluded.size,
            width = excluded.width,
            height = excluded.height
        """
    )
    connection.execute(
        """
        INSERT INTO narrative_image_assets (category, asset_id, object_key, size, width, height)
        SELECT category, asset_id, object_key, size, width, height
        FROM candidate_narrative_image_assets WHERE true
        ON CONFLICT (category, asset_id) DO UPDATE SET
            object_key = excluded.object_key,
            size = excluded.size,
            width = excluded.width,
            height = excluded.height
        """
    )
    connection.execute(
        """
        INSERT INTO presentation_image_assets
            (category, asset_id, object_key, size, width, height)
        SELECT category, asset_id, object_key, size, width, height
        FROM candidate_presentation_image_assets WHERE true
        ON CONFLICT (category, asset_id) DO UPDATE SET
            object_key = excluded.object_key,
            size = excluded.size,
            width = excluded.width,
            height = excluded.height
        """
    )
    connection.execute(
        """
        INSERT INTO presentation_video_assets
            (category, asset_id, object_key, mime, size, width, height,
             frame_rate_numerator, frame_rate_denominator, frame_count)
        SELECT category, asset_id, object_key, mime, size, width, height,
               frame_rate_numerator, frame_rate_denominator, frame_count
        FROM candidate_presentation_video_assets WHERE true
        ON CONFLICT (category, asset_id) DO UPDATE SET
            object_key = excluded.object_key,
            mime = excluded.mime,
            size = excluded.size,
            width = excluded.width,
            height = excluded.height,
            frame_rate_numerator = excluded.frame_rate_numerator,
            frame_rate_denominator = excluded.frame_rate_denominator,
            frame_count = excluded.frame_count
        """
    )
    connection.execute(
        """
        DELETE FROM narrative_asset_material_references
        WHERE (category, asset_id) IN (SELECT category, asset_id FROM candidate_narrative_image_assets)
        """
    )
    connection.execute(
        """
        INSERT INTO narrative_media_assets
            (category, asset_id, object_key, mime, size, duration,
             sample_rate, width, height, frame_rate_numerator,
             frame_rate_denominator, frame_count)
        SELECT category, asset_id, object_key, mime, size, duration,
               sample_rate, width, height, frame_rate_numerator,
               frame_rate_denominator, frame_count
        FROM candidate_narrative_media_assets WHERE true
        ON CONFLICT (category, asset_id) DO UPDATE SET
            object_key = excluded.object_key,
            mime = excluded.mime,
            size = excluded.size,
            duration = excluded.duration,
            sample_rate = excluded.sample_rate,
            width = excluded.width,
            height = excluded.height,
            frame_rate_numerator = excluded.frame_rate_numerator,
            frame_rate_denominator = excluded.frame_rate_denominator,
            frame_count = excluded.frame_count
        """
    )
    connection.execute(
        """
        INSERT INTO narrative_asset_material_references
            (category, asset_id, position, material_category, material_asset_id)
        SELECT category, asset_id, position, material_category, material_asset_id
        FROM candidate_narrative_asset_material_references
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
            *((unit, section.collection_id, "section") for section in manifest.sections),
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
        INSERT INTO sections
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
            for section in manifest.sections
        ),
    )
    connection.executemany(
        """
        INSERT INTO movement_locations
            (locale, movement_id, location_id, position, location_type, sort_id,
             start_time, present_stage_id, unlock_stage_id, section_id,
             divider_icon_asset_id, divider_sub_name, video_id)
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
                location.divider_icon_asset_id,
                location.divider_sub_name,
                location.video_id,
            )
            for movement in manifest.movements
            for location in movement.locations
        ),
    )
    connection.executemany(
        """
        INSERT INTO archive_groups
            (locale, archive_id, collection_id, position, name, archive_category, story_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                archive.id,
                archive.collection_id,
                archive.position,
                archive.name,
                archive.archive_category,
                archive.story_type,
            )
            for archive in manifest.archive_groups
        ),
    )
    groups = (*manifest.sections, *manifest.archive_groups)
    connection.executemany(
        """
        INSERT INTO stories
            (locale, story_id, collection_id, tag, tag_text, code, name, info, text, position)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                story.text,
                story_position,
            )
            for group in groups
            for story_position, story in enumerate(group.stories)
        ),
    )
    connection.executemany(
        """
        INSERT INTO story_narrative_image_references
            (locale, story_id, position, asset_id, kind, category,
             title, subtitle, names_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                story.id,
                reference_position,
                reference.asset_id,
                reference.kind,
                reference.category,
                reference.title,
                reference.subtitle,
                json.dumps(reference.names, ensure_ascii=False, separators=(",", ":")),
            )
            for group in groups
            for story in group.stories
            for reference_position, reference in enumerate(story.artwork_references)
        ),
    )
    connection.executemany(
        """
        INSERT INTO story_narrative_media_references
            (locale, story_id, position, asset_id, category, usage)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                story.id,
                reference_position,
                reference.asset_id,
                "video" if reference.kind == "video" else "audio",
                None if reference.kind == "video" else reference.kind,
            )
            for group in groups
            for story in group.stories
            for reference_position, reference in enumerate(story.media_references)
        ),
    )
    connection.executemany(
        """
        INSERT INTO galleries
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
        INSERT INTO gallery_groups
            (locale, gallery_id, group_id, position, name, description,
             related_story_id, related_stage_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                gallery.id,
                group.id,
                group.position,
                group.name,
                group.description,
                group.related_story_id,
                group.related_stage_id,
            )
            for gallery in manifest.galleries
            for group in gallery.groups
        ),
    )
    connection.executemany(
        """
        INSERT INTO gallery_narrative_asset_references
            (locale, gallery_id, group_id, position, cg_id, asset_id,
             category, layout)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                gallery.id,
                group.id,
                artwork.position,
                artwork.cg_id,
                artwork.asset_id,
                artwork.category,
                artwork.layout,
            )
            for gallery in manifest.galleries
            for group in gallery.groups
            for artwork in group.artworks
        ),
    )
    connection.executemany(
        """
        INSERT INTO gallery_reference_panels
            (locale, gallery_id, group_id, reference_position,
             position, panel_asset_id, width, height)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                unit,
                gallery.id,
                group.id,
                artwork.position,
                panel.position,
                panel.id,
                panel.width,
                panel.height,
            )
            for gallery in manifest.galleries
            for group in gallery.groups
            for artwork in group.artworks
            for panel in artwork.panels
        ),
    )


def _rebuild_search_entries(connection: sqlite3.Connection) -> None:
    """Rebuild the locale-scoped derived search index inside the write transaction."""
    connection.execute("DELETE FROM search_entries")
    connection.execute(
        """
        WITH
        locale_units AS (
            SELECT unit AS locale FROM unit_versions WHERE unit <> 'artwork'
        ),
        story_terms AS (
            SELECT reference.locale, reference.story_id,
                   group_concat(name.value, ' ') AS names,
                   group_concat(
                       COALESCE(reference.title, '') || ' ' ||
                       COALESCE(reference.subtitle, ''), ' '
                   ) AS labels,
                   group_concat(
                       reference.category || ' ' || reference.asset_id, ' '
                   ) AS narrative_image_assets
            FROM story_narrative_image_references AS reference
            LEFT JOIN json_each(reference.names_json) AS name ON true
            GROUP BY reference.locale, reference.story_id
        ),
        story_thumbnails AS (
            SELECT locale, story_id, object_key
            FROM (
                SELECT reference.locale, reference.story_id, artwork.object_key,
                       ROW_NUMBER() OVER (
                           PARTITION BY reference.locale, reference.story_id
                           ORDER BY CASE reference.category
                               WHEN 'illustration' THEN 0
                               WHEN 'background' THEN 1
                               ELSE 2
                           END, reference.position
                       ) AS thumbnail_rank
                FROM story_narrative_image_references AS reference
                JOIN narrative_image_assets AS artwork
                  ON artwork.category = reference.category
                 AND artwork.asset_id = reference.asset_id
                WHERE reference.category IN ('illustration', 'background')
            )
            WHERE thumbnail_rank = 1
        ),
        collection_thumbnails AS (
            SELECT locale, collection_id, object_key
            FROM (
                SELECT story.locale, story.collection_id, artwork.object_key,
                       ROW_NUMBER() OVER (
                           PARTITION BY story.locale, story.collection_id
                           ORDER BY CASE reference.category
                               WHEN 'illustration' THEN 0
                               WHEN 'background' THEN 1
                               ELSE 2
                           END, story.position, reference.position
                       ) AS thumbnail_rank
                FROM stories AS story
                JOIN story_narrative_image_references AS reference
                  ON reference.locale = story.locale
                 AND reference.story_id = story.story_id
                JOIN narrative_image_assets AS artwork
                  ON artwork.category = reference.category
                 AND artwork.asset_id = reference.asset_id
                WHERE reference.category IN ('illustration', 'background')
            )
            WHERE thumbnail_rank = 1
        ),
        gallery_thumbnails AS (
            SELECT locale, gallery_id, object_key
            FROM (
                SELECT group_artwork.locale, group_artwork.gallery_id, artwork.object_key,
                       ROW_NUMBER() OVER (
                           PARTITION BY group_artwork.locale, group_artwork.gallery_id
                           ORDER BY CASE group_artwork.category
                               WHEN 'illustration' THEN 0
                               WHEN 'background' THEN 1
                               ELSE 2
                           END, gallery_group.position, group_artwork.position
                       ) AS thumbnail_rank
                FROM gallery_narrative_asset_references AS group_artwork
                JOIN gallery_groups AS gallery_group
                  ON gallery_group.locale = group_artwork.locale
                 AND gallery_group.gallery_id = group_artwork.gallery_id
                 AND gallery_group.group_id = group_artwork.group_id
                JOIN narrative_image_assets AS artwork
                  ON artwork.category = group_artwork.category
                 AND artwork.asset_id = group_artwork.asset_id
                WHERE group_artwork.category IN ('illustration', 'background')
            )
            WHERE thumbnail_rank = 1
        ),
        artwork_names AS (
            SELECT reference.locale, reference.category, reference.asset_id,
                   min(name.value) AS first_name,
                   group_concat(name.value, ' ') AS names
            FROM story_narrative_image_references AS reference
            JOIN json_each(reference.names_json) AS name ON true
            GROUP BY reference.locale, reference.category, reference.asset_id
        ),
        artwork_labels AS (
            SELECT reference.locale, reference.category, reference.asset_id,
                   group_concat(
                       COALESCE(reference.title, '') || ' ' ||
                       COALESCE(reference.subtitle, ''), ' '
                   ) AS labels
            FROM story_narrative_image_references AS reference
            WHERE reference.title IS NOT NULL OR reference.subtitle IS NOT NULL
            GROUP BY reference.locale, reference.category, reference.asset_id
            ),
        entries AS (
        SELECT 'story:' || story.locale || ':' || story.story_id,
               story.locale, 'story', story.story_id, NULL, story.collection_id,
               story.name, story.code,
               trim(
                   story.story_id || ' ' || story.code || ' ' || story.name ||
                   ' ' || story.info || ' ' || COALESCE(terms.names, '') ||
                   ' ' || COALESCE(terms.labels, '') || ' ' ||
                   COALESCE(terms.narrative_image_assets, '')
               ),
               CASE
                   WHEN section.section_id IS NOT NULL THEN json_object(
                       'parentKind', 'section',
                       'movementID', movement.movement_id,
                       'movementName', movement.name,
                       'sectionID', section.section_id,
                       'sectionName', section.name
                   )
                   WHEN archive.archive_id IS NOT NULL THEN json_object(
                       'parentKind', 'archive_group',
                       'archiveCategory', archive.archive_category,
                       'groupID', archive.archive_id,
                       'groupName', archive.name
                   )
               END,
               story_thumbnail.object_key
        FROM stories AS story
        LEFT JOIN story_terms AS terms
          ON terms.locale = story.locale AND terms.story_id = story.story_id
        LEFT JOIN story_thumbnails AS story_thumbnail
          ON story_thumbnail.locale = story.locale
         AND story_thumbnail.story_id = story.story_id
        LEFT JOIN sections AS section
          ON section.locale = story.locale
         AND section.collection_id = story.collection_id
        LEFT JOIN movement_locations AS location
          ON location.locale = section.locale
         AND location.section_id = section.section_id
         AND location.location_type = 'story_set'
        LEFT JOIN movements AS movement
          ON movement.locale = location.locale
         AND movement.movement_id = location.movement_id
        LEFT JOIN archive_groups AS archive
          ON archive.locale = story.locale
         AND archive.collection_id = story.collection_id

        UNION ALL

        SELECT 'movement:' || movement.locale || ':' || movement.movement_id,
               movement.locale, 'movement', movement.movement_id, NULL, NULL,
               movement.name, movement.movement_type,
               trim(movement.movement_id || ' ' || movement.name || ' ' ||
                    movement.movement_type),
               NULL, NULL
        FROM movements AS movement

        UNION ALL

        SELECT 'section:' || section.locale || ':' || section.section_id,
               section.locale, 'section', section.section_id, NULL,
               section.collection_id, section.name, section.description,
               trim(section.section_id || ' ' || section.name || ' ' ||
                    section.description),
               json_object(
                   'parentKind', 'section',
                   'movementID', movement.movement_id,
                   'movementName', movement.name,
                   'sectionID', section.section_id,
                   'sectionName', section.name
               ),
               collection_thumbnail.object_key
        FROM sections AS section
        JOIN movement_locations AS location
          ON location.locale = section.locale
         AND location.section_id = section.section_id
         AND location.location_type = 'story_set'
        JOIN movements AS movement
          ON movement.locale = location.locale
         AND movement.movement_id = location.movement_id
        LEFT JOIN collection_thumbnails AS collection_thumbnail
          ON collection_thumbnail.locale = section.locale
         AND collection_thumbnail.collection_id = section.collection_id

        UNION ALL

        SELECT 'archive_group:' || archive.locale || ':' || archive.archive_id,
               archive.locale, 'archive_group', archive.archive_id, NULL,
               archive.collection_id, archive.name, archive.archive_category,
               trim(archive.archive_id || ' ' || archive.name || ' ' ||
                    archive.archive_category),
               json_object(
                   'parentKind', 'archive_group',
                   'archiveCategory', archive.archive_category,
                   'groupID', archive.archive_id,
                   'groupName', archive.name
               ),
               collection_thumbnail.object_key
        FROM archive_groups AS archive
        LEFT JOIN collection_thumbnails AS collection_thumbnail
          ON collection_thumbnail.locale = archive.locale
         AND collection_thumbnail.collection_id = archive.collection_id

        UNION ALL

        SELECT 'gallery:' || gallery.locale || ':' || gallery.gallery_id,
               gallery.locale, 'gallery', gallery.gallery_id, NULL,
               gallery.collection_id, gallery.name, gallery.description,
               trim(gallery.gallery_id || ' ' || gallery.name || ' ' ||
                    gallery.description),
               CASE
                   WHEN section.section_id IS NOT NULL THEN json_object(
                       'parentKind', 'section',
                       'movementID', movement.movement_id,
                       'movementName', movement.name,
                       'sectionID', section.section_id,
                       'sectionName', section.name
                   )
                   WHEN archive.archive_id IS NOT NULL THEN json_object(
                       'parentKind', 'archive_group',
                       'archiveCategory', archive.archive_category,
                       'groupID', archive.archive_id,
                       'groupName', archive.name
                   )
               END,
               gallery_thumbnail.object_key
        FROM galleries AS gallery
        LEFT JOIN gallery_thumbnails AS gallery_thumbnail
          ON gallery_thumbnail.locale = gallery.locale
         AND gallery_thumbnail.gallery_id = gallery.gallery_id
        LEFT JOIN sections AS section
          ON section.locale = gallery.locale
         AND section.collection_id = gallery.collection_id
        LEFT JOIN movement_locations AS location
          ON location.locale = section.locale
         AND location.section_id = section.section_id
         AND location.location_type = 'story_set'
        LEFT JOIN movements AS movement
          ON movement.locale = location.locale
         AND movement.movement_id = location.movement_id
        LEFT JOIN archive_groups AS archive
          ON archive.locale = gallery.locale
         AND archive.collection_id = gallery.collection_id

        UNION ALL

        SELECT 'narrative_asset:' || locale_units.locale || ':' || artwork.category || ':' || artwork.asset_id,
               locale_units.locale, 'narrative_asset', artwork.asset_id, artwork.category, NULL,
               COALESCE(artwork_name.first_name, artwork.asset_id), artwork.category,
               trim(
                   artwork.asset_id || ' ' || artwork.category || ' ' ||
                   COALESCE(artwork_name.names, '') || ' ' ||
                   COALESCE(artwork_label.labels, '')
               ),
               NULL, artwork.object_key
        FROM locale_units
        CROSS JOIN narrative_image_assets AS artwork
        LEFT JOIN artwork_names AS artwork_name
          ON artwork_name.locale = locale_units.locale
         AND artwork_name.category = artwork.category
         AND artwork_name.asset_id = artwork.asset_id
        LEFT JOIN artwork_labels AS artwork_label
          ON artwork_label.locale = locale_units.locale
         AND artwork_label.category = artwork.category
         AND artwork_label.asset_id = artwork.asset_id
        )
        INSERT INTO search_entries (
            entry_key, locale, kind, entry_id, category, collection_id, title,
            subtitle, search_text, parent_json, thumbnail_object_key
        )
        SELECT * FROM entries
        """
    )


def find_missing_artwork_references(path: Path) -> tuple[str, ...]:
    """Return locale artwork identifiers absent from the current artwork set."""

    connection = _connect(path)
    try:
        return tuple(
            str(row[0])
            for row in connection.execute(
                """
                WITH referenced AS (
                    SELECT category, asset_id FROM story_narrative_image_references
                    UNION
                    SELECT category, asset_id FROM gallery_narrative_asset_references
                )
                SELECT referenced.category || '/' || referenced.asset_id
                FROM referenced
                LEFT JOIN narrative_image_assets USING (category, asset_id)
                WHERE narrative_image_assets.asset_id IS NULL
                ORDER BY referenced.category, referenced.asset_id
                """
            )
        )
    finally:
        connection.close()


def find_missing_media_references(path: Path) -> tuple[str, ...]:
    """Return story media identifiers absent from the current media set."""

    connection = _connect(path)
    try:
        return tuple(
            str(row[0])
            for row in connection.execute(
                """
                SELECT reference.category || '/' || reference.asset_id
                FROM story_narrative_media_references AS reference
                LEFT JOIN narrative_media_assets AS media
                  ON media.asset_id = reference.asset_id
                 AND media.category = reference.category
                WHERE media.asset_id IS NULL
                GROUP BY reference.category, reference.asset_id
                ORDER BY reference.category, reference.asset_id
                """
            )
        )
    finally:
        connection.close()


def find_missing_score_references(path: Path) -> tuple[str, ...]:
    """Return declared Score PNG and video identifiers absent from the artwork set."""

    connection = _connect(path)
    try:
        return tuple(
            str(row[0])
            for row in connection.execute(
                """
                WITH declared_assets(category, asset_id) AS (
                    SELECT 'icon', icon_asset_id FROM movements WHERE icon_asset_id IS NOT NULL
                    UNION SELECT 'logo', logo_asset_id FROM movements
                        WHERE logo_asset_id IS NOT NULL
                    UNION SELECT 'background', background_asset_id FROM movements
                        WHERE background_asset_id IS NOT NULL
                    UNION SELECT 'key-visual', key_visual_asset_id FROM sections
                        WHERE key_visual_asset_id IS NOT NULL
                    UNION SELECT 'title', title_asset_id FROM sections
                        WHERE title_asset_id IS NOT NULL
                    UNION SELECT 'background', background_asset_id FROM sections
                        WHERE background_asset_id IS NOT NULL
                    UNION SELECT 'decoration', decoration_asset_id FROM sections
                        WHERE decoration_asset_id IS NOT NULL
                    UNION SELECT 'retro-background', retro_background_asset_id
                        FROM sections WHERE retro_background_asset_id IS NOT NULL
                    UNION SELECT 'divider', divider_icon_asset_id FROM movement_locations
                        WHERE divider_icon_asset_id IS NOT NULL
                ), missing_assets AS (
                    SELECT 'presentation/' || declared.category || '/' || declared.asset_id AS identity
                    FROM declared_assets AS declared
                    LEFT JOIN presentation_image_assets AS available USING (category, asset_id)
                    WHERE available.asset_id IS NULL
                ), missing_videos AS (
                    SELECT 'presentation/video/' || locations.video_id AS identity
                    FROM movement_locations AS locations
                    LEFT JOIN presentation_video_assets AS available
                      ON available.category = 'video'
                     AND available.asset_id = locations.video_id
                    WHERE locations.video_id IS NOT NULL AND available.asset_id IS NULL
                )
                SELECT identity FROM missing_assets
                UNION SELECT identity FROM missing_videos
                ORDER BY identity
                """
            )
        )
    finally:
        connection.close()
