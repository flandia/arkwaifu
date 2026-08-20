-- Current reader schema for the one arkwaifu.sqlite3 object.
-- The updater creates new databases from this file and requires existing
-- databases to declare the same schema version.
PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE unit_versions (
    unit TEXT PRIMARY KEY
        CHECK (unit IN ('artwork', 'CN', 'EN', 'JP', 'KR', 'TW')),
    res_version TEXT NOT NULL CHECK (length(res_version) > 0)
) STRICT;

CREATE TABLE narrative_image_assets (
    asset_id TEXT NOT NULL
        CHECK (length(asset_id) > 0),
    category TEXT NOT NULL
        CHECK (category IN ('illustration', 'background', 'item', 'character')),
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    size INTEGER NOT NULL CHECK (size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    PRIMARY KEY (category, asset_id)
) STRICT;

CREATE TABLE material_assets (
    category TEXT NOT NULL
        CHECK (category IN ('illustration', 'background', 'item', 'character')),
    asset_id TEXT NOT NULL
        CHECK (length(asset_id) > 0),
    material_type TEXT NOT NULL CHECK (material_type IN ('character', 'panel')),
    character_id TEXT,
    role TEXT CHECK (role IN ('body', 'face', 'whole_body')),
    variant TEXT,
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    size INTEGER NOT NULL CHECK (size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    PRIMARY KEY (category, asset_id),
    CHECK (
        (material_type = 'character'
            AND category = 'character'
            AND character_id IS NOT NULL
            AND length(character_id) > 0
            AND role IS NOT NULL
            AND variant IS NOT NULL
            AND length(variant) > 0)
        OR
        (material_type = 'panel'
            AND character_id IS NULL
            AND role IS NULL
            AND variant IS NULL)
    )
) STRICT;

CREATE INDEX material_assets_by_character
    ON material_assets (character_id, role, variant, category, asset_id)
    WHERE material_type = 'character';

CREATE TABLE narrative_asset_material_references (
    category TEXT NOT NULL
        CHECK (category IN ('illustration', 'background', 'item', 'character')),
    asset_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    material_category TEXT NOT NULL
        CHECK (material_category IN ('illustration', 'background', 'item', 'character')),
    material_asset_id TEXT NOT NULL,
    PRIMARY KEY (category, asset_id, position),
    UNIQUE (category, asset_id, material_category, material_asset_id),
    FOREIGN KEY (category, asset_id)
        REFERENCES narrative_image_assets (category, asset_id) ON DELETE CASCADE,
    FOREIGN KEY (material_category, material_asset_id)
        REFERENCES material_assets (category, asset_id)
) STRICT;

CREATE TABLE presentation_image_assets (
    category TEXT NOT NULL
        CHECK (category IN (
            'icon', 'logo', 'background', 'key-visual', 'title',
            'decoration', 'retro-background', 'divider'
        )),
    asset_id TEXT NOT NULL
        CHECK (length(asset_id) > 0),
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    size INTEGER NOT NULL CHECK (size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    PRIMARY KEY (category, asset_id)
) STRICT;

CREATE TABLE presentation_video_assets (
    category TEXT NOT NULL CHECK (category = 'video'),
    asset_id TEXT NOT NULL
        CHECK (length(asset_id) > 0),
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    mime TEXT NOT NULL CHECK (mime LIKE 'video/%'),
    size INTEGER NOT NULL CHECK (size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    frame_rate_numerator INTEGER NOT NULL CHECK (frame_rate_numerator > 0),
    frame_rate_denominator INTEGER NOT NULL CHECK (frame_rate_denominator > 0),
    frame_count INTEGER NOT NULL CHECK (frame_count > 0),
    PRIMARY KEY (category, asset_id)
) STRICT;

CREATE TABLE narrative_media_assets (
    category TEXT NOT NULL CHECK (category IN ('audio', 'video')),
    asset_id TEXT NOT NULL
        CHECK (length(asset_id) > 0),
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    mime TEXT NOT NULL CHECK (length(mime) > 0),
    size INTEGER NOT NULL CHECK (size > 0),
    duration REAL CHECK (duration IS NULL OR duration > 0),
    sample_rate INTEGER CHECK (sample_rate IS NULL OR sample_rate > 0),
    width INTEGER CHECK (width IS NULL OR width > 0),
    height INTEGER CHECK (height IS NULL OR height > 0),
    frame_rate_numerator INTEGER CHECK (
        frame_rate_numerator IS NULL OR frame_rate_numerator > 0
    ),
    frame_rate_denominator INTEGER CHECK (
        frame_rate_denominator IS NULL OR frame_rate_denominator > 0
    ),
    frame_count INTEGER CHECK (frame_count IS NULL OR frame_count > 0),
    PRIMARY KEY (category, asset_id),
    CHECK (
        (category = 'audio'
            AND width IS NULL AND height IS NULL
            AND frame_rate_numerator IS NULL
            AND frame_rate_denominator IS NULL
            AND frame_count IS NULL)
        OR
        (category = 'video'
            AND sample_rate IS NULL
            AND width IS NOT NULL AND height IS NOT NULL
            AND frame_rate_numerator IS NOT NULL
            AND frame_rate_denominator IS NOT NULL
            AND frame_count IS NOT NULL)
    )
) STRICT;

CREATE INDEX narrative_media_assets_by_id
    ON narrative_media_assets (asset_id, category);

-- Locale tables reference unit_versions with ON DELETE CASCADE. Replacing one
-- locale removes the old Score, Archive, story, and gallery trees.
CREATE TABLE story_collections (
    locale TEXT NOT NULL CHECK (locale IN ('CN', 'EN', 'JP', 'KR', 'TW')),
    collection_id TEXT NOT NULL
        CHECK (length(collection_id) > 0 AND collection_id = lower(collection_id)),
    collection_kind TEXT NOT NULL
        CHECK (collection_kind IN ('section', 'archive_group')),
    PRIMARY KEY (locale, collection_id),
    FOREIGN KEY (locale) REFERENCES unit_versions (unit) ON DELETE CASCADE,
    CHECK (
        (collection_kind = 'section'
            AND collection_id GLOB 'section:?*')
        OR
        (collection_kind = 'archive_group'
            AND collection_id GLOB 'archive_group:?*')
    )
) STRICT;

CREATE TABLE movements (
    locale TEXT NOT NULL CHECK (locale IN ('CN', 'EN', 'JP', 'KR', 'TW')),
    movement_id TEXT NOT NULL
        CHECK (length(movement_id) > 0 AND movement_id = lower(movement_id)),
    position INTEGER NOT NULL CHECK (position >= 0),
    movement_type TEXT NOT NULL CHECK (movement_type IN ('continue', 'discrete')),
    name TEXT NOT NULL,
    icon_asset_id TEXT,
    logo_asset_id TEXT,
    background_asset_id TEXT,
    has_video INTEGER NOT NULL CHECK (has_video IN (0, 1)),
    start_time INTEGER NOT NULL,
    PRIMARY KEY (locale, movement_id),
    UNIQUE (locale, position),
    FOREIGN KEY (locale) REFERENCES unit_versions (unit) ON DELETE CASCADE,
    CHECK (icon_asset_id IS NULL OR length(icon_asset_id) > 0),
    CHECK (logo_asset_id IS NULL OR length(logo_asset_id) > 0),
    CHECK (background_asset_id IS NULL OR length(background_asset_id) > 0)
) STRICT;

CREATE TABLE sections (
    locale TEXT NOT NULL,
    section_id TEXT NOT NULL
        CHECK (length(section_id) > 0 AND section_id = lower(section_id)),
    collection_id TEXT NOT NULL,
    section_type TEXT NOT NULL
        CHECK (section_type IN ('main_theme', 'side_story', 'vignette')),
    name TEXT NOT NULL,
    review_group_id TEXT,
    sort_by_year INTEGER NOT NULL,
    sort_within_year INTEGER NOT NULL,
    key_visual_asset_id TEXT,
    title_asset_id TEXT,
    background_asset_id TEXT,
    decoration_asset_id TEXT,
    retro_background_asset_id TEXT,
    description TEXT NOT NULL,
    has_video INTEGER NOT NULL CHECK (has_video IN (0, 1)),
    PRIMARY KEY (locale, section_id),
    UNIQUE (locale, collection_id),
    UNIQUE (locale, review_group_id),
    FOREIGN KEY (locale, collection_id)
        REFERENCES story_collections (locale, collection_id) ON DELETE CASCADE,
    CHECK (collection_id = 'section:' || section_id),
    CHECK (key_visual_asset_id IS NULL OR length(key_visual_asset_id) > 0),
    CHECK (review_group_id IS NULL OR (length(review_group_id) > 0 AND review_group_id = lower(review_group_id))),
    CHECK (title_asset_id IS NULL OR length(title_asset_id) > 0),
    CHECK (background_asset_id IS NULL OR length(background_asset_id) > 0),
    CHECK (decoration_asset_id IS NULL OR length(decoration_asset_id) > 0),
    CHECK (retro_background_asset_id IS NULL OR length(retro_background_asset_id) > 0)
) STRICT;

CREATE TABLE movement_locations (
    locale TEXT NOT NULL,
    movement_id TEXT NOT NULL,
    location_id TEXT NOT NULL
        CHECK (length(location_id) > 0 AND location_id = lower(location_id)),
    position INTEGER NOT NULL CHECK (position >= 0),
    location_type TEXT NOT NULL
        CHECK (location_type IN ('before', 'after', 'divider', 'story_set')),
    sort_id INTEGER NOT NULL,
    start_time INTEGER NOT NULL,
    present_stage_id TEXT,
    unlock_stage_id TEXT,
    section_id TEXT,
    divider_icon_asset_id TEXT,
    divider_sub_name TEXT,
    video_id TEXT,
    PRIMARY KEY (locale, movement_id, location_id),
    UNIQUE (locale, movement_id, position),
    FOREIGN KEY (locale, movement_id)
        REFERENCES movements (locale, movement_id) ON DELETE CASCADE,
    FOREIGN KEY (locale, section_id)
        REFERENCES sections (locale, section_id),
    CHECK ((location_type IN ('story_set', 'before', 'after')) = (section_id IS NOT NULL)),
    CHECK ((location_type = 'divider') = (divider_sub_name IS NOT NULL)),
    CHECK (divider_icon_asset_id IS NULL OR length(divider_icon_asset_id) > 0),
    CHECK (video_id IS NULL OR length(video_id) > 0)
) STRICT;

CREATE UNIQUE INDEX movement_locations_canonical_section
    ON movement_locations (locale, section_id)
    WHERE location_type = 'story_set';

CREATE INDEX movement_locations_by_section
    ON movement_locations (locale, section_id, movement_id, position)
    WHERE section_id IS NOT NULL;

CREATE TABLE archive_groups (
    locale TEXT NOT NULL CHECK (locale IN ('CN', 'EN', 'JP', 'KR', 'TW')),
    archive_id TEXT NOT NULL
        CHECK (length(archive_id) > 0 AND archive_id = lower(archive_id)),
    collection_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    name TEXT NOT NULL,
    archive_category TEXT NOT NULL
        CHECK (archive_category IN (
            'events', 'operator_record', 'integrated_strategies',
            'reclamation_algorithm', 'others'
        )),
    story_type TEXT CHECK (story_type IN ('side_story', 'vignette')),
    PRIMARY KEY (locale, archive_id),
    UNIQUE (locale, collection_id),
    UNIQUE (locale, position),
    FOREIGN KEY (locale, collection_id)
        REFERENCES story_collections (locale, collection_id) ON DELETE CASCADE,
    CHECK (collection_id = 'archive_group:' || archive_id),
    CHECK ((archive_category = 'events') = (story_type IS NOT NULL))
) STRICT;

CREATE TABLE stories (
    locale TEXT NOT NULL,
    story_id TEXT NOT NULL
        CHECK (length(story_id) > 0 AND story_id = lower(story_id)),
    collection_id TEXT NOT NULL,
    tag TEXT NOT NULL CHECK (tag IN ('before', 'after', 'interlude')),
    tag_text TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    info TEXT NOT NULL,
    text TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (locale, story_id),
    UNIQUE (locale, collection_id, position),
    FOREIGN KEY (locale, collection_id)
        REFERENCES story_collections (locale, collection_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE story_narrative_image_references (
    locale TEXT NOT NULL,
    story_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    asset_id TEXT NOT NULL
        CHECK (length(asset_id) > 0),
    kind TEXT NOT NULL CHECK (kind IN ('picture', 'character')),
    category TEXT NOT NULL
        CHECK (category IN ('illustration', 'background', 'item', 'character')),
    title TEXT,
    subtitle TEXT,
    names_json TEXT NOT NULL
        CHECK (json_valid(names_json) AND json_type(names_json) = 'array'),
    PRIMARY KEY (locale, story_id, position),
    FOREIGN KEY (locale, story_id)
        REFERENCES stories (locale, story_id) ON DELETE CASCADE,
    CHECK (kind <> 'character' OR category = 'character')
) STRICT;

CREATE INDEX story_narrative_image_references_by_asset
    ON story_narrative_image_references (locale, category, asset_id);

-- Story media references deliberately have no foreign key to narrative_media_assets.
-- Locale snapshots can lead the Windows asset version; unresolved identifiers are
-- retained and reported as incomplete upstream data.
CREATE TABLE story_narrative_media_references (
    locale TEXT NOT NULL,
    story_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    asset_id TEXT NOT NULL
        CHECK (length(asset_id) > 0),
    category TEXT NOT NULL CHECK (category IN ('audio', 'video')),
    usage TEXT CHECK (usage IN ('sound', 'music')),
    PRIMARY KEY (locale, story_id, position),
    FOREIGN KEY (locale, story_id)
        REFERENCES stories (locale, story_id) ON DELETE CASCADE,
    CHECK ((category = 'audio') = (usage IS NOT NULL))
) STRICT;

CREATE INDEX story_narrative_media_references_by_asset
    ON story_narrative_media_references (locale, category, asset_id);

-- Asset references deliberately have no foreign key to their global tables.
-- A locale snapshot may lead the Windows asset version; declared identifiers
-- remain representable and are reported as incomplete upstream data.

CREATE TRIGGER story_narrative_image_reference_names_insert
BEFORE INSERT ON story_narrative_image_references
WHEN EXISTS (
    SELECT 1 FROM json_each(NEW.names_json) WHERE type <> 'text'
)
BEGIN
    SELECT RAISE(ABORT, 'story narrative image reference names must be strings');
END;

CREATE TRIGGER story_narrative_image_reference_names_update
BEFORE UPDATE OF names_json ON story_narrative_image_references
WHEN EXISTS (
    SELECT 1 FROM json_each(NEW.names_json) WHERE type <> 'text'
)
BEGIN
    SELECT RAISE(ABORT, 'story narrative image reference names must be strings');
END;

CREATE TABLE galleries (
    locale TEXT NOT NULL,
    gallery_id TEXT NOT NULL
        CHECK (length(gallery_id) > 0 AND gallery_id = lower(gallery_id)),
    collection_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    location_id TEXT,
    PRIMARY KEY (locale, gallery_id),
    UNIQUE (locale, position),
    UNIQUE (locale, collection_id),
    FOREIGN KEY (locale, collection_id)
        REFERENCES story_collections (locale, collection_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX galleries_by_collection
    ON galleries (locale, collection_id, position, gallery_id);

CREATE TABLE gallery_groups (
    locale TEXT NOT NULL,
    gallery_id TEXT NOT NULL,
    group_id TEXT NOT NULL CHECK (length(group_id) > 0),
    position INTEGER NOT NULL CHECK (position >= 0),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    related_story_id TEXT,
    related_stage_id TEXT,
    PRIMARY KEY (locale, gallery_id, group_id),
    UNIQUE (locale, gallery_id, position),
    FOREIGN KEY (locale, gallery_id)
        REFERENCES galleries (locale, gallery_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE gallery_narrative_asset_references (
    locale TEXT NOT NULL,
    gallery_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    cg_id TEXT NOT NULL
        CHECK (length(cg_id) > 0),
    asset_id TEXT NOT NULL
        CHECK (length(asset_id) > 0),
    category TEXT NOT NULL
        CHECK (category IN ('illustration', 'background', 'item', 'character')),
    layout TEXT NOT NULL
        CHECK (layout IN ('none', 'vertical', 'horizontal')),
    PRIMARY KEY (locale, gallery_id, group_id, position),
    UNIQUE (locale, gallery_id, group_id, cg_id),
    UNIQUE (locale, gallery_id, group_id, category, asset_id),
    FOREIGN KEY (locale, gallery_id, group_id)
        REFERENCES gallery_groups (locale, gallery_id, group_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX gallery_narrative_asset_references_by_asset
    ON gallery_narrative_asset_references (locale, category, asset_id);

CREATE TABLE gallery_reference_panels (
    locale TEXT NOT NULL,
    gallery_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    reference_position INTEGER NOT NULL CHECK (reference_position >= 0),
    position INTEGER NOT NULL CHECK (position >= 0),
    panel_asset_id TEXT NOT NULL
        CHECK (length(panel_asset_id) > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    PRIMARY KEY (
        locale, gallery_id, group_id, reference_position, position
    ),
    UNIQUE (
        locale, gallery_id, group_id, reference_position, panel_asset_id
    ),
    FOREIGN KEY (locale, gallery_id, group_id, reference_position)
        REFERENCES gallery_narrative_asset_references (
            locale, gallery_id, group_id, position
        ) ON DELETE CASCADE
) STRICT;

-- Search rows are a derived, locale-scoped index. The hierarchy and asset
-- tables remain authoritative; the updater rebuilds this table after every
-- asset or locale transaction so the reader never observes a stale index.
CREATE TABLE search_entries (
    entry_key TEXT PRIMARY KEY CHECK (length(entry_key) > 0),
    locale TEXT NOT NULL
        CHECK (locale IN ('CN', 'EN', 'JP', 'KR', 'TW')),
    kind TEXT NOT NULL
        CHECK (kind IN (
            'story', 'movement', 'section', 'archive_group', 'gallery',
            'narrative_asset'
        )),
    entry_id TEXT NOT NULL CHECK (length(entry_id) > 0),
    category TEXT
        CHECK (category IS NULL OR category IN (
            'illustration', 'background', 'item', 'character'
        )),
    collection_id TEXT,
    title TEXT NOT NULL,
    subtitle TEXT,
    search_text TEXT NOT NULL CHECK (length(search_text) > 0),
    parent_json TEXT CHECK (parent_json IS NULL OR json_valid(parent_json)),
    thumbnail_object_key TEXT,
    UNIQUE (locale, kind, entry_id, category),
    CHECK ((kind = 'narrative_asset') = (category IS NOT NULL)),
    FOREIGN KEY (locale) REFERENCES unit_versions (unit) ON DELETE CASCADE
) STRICT;

CREATE INDEX search_entries_by_locale
    ON search_entries (locale, kind, entry_id);

PRAGMA user_version = 2;

COMMIT;
