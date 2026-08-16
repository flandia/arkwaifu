-- Current reader schema for the one arkwaifu.sqlite3 object.
-- The updater creates new databases from this file and requires existing
-- databases to declare the same schema version.
PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE unit_versions (
    unit TEXT PRIMARY KEY
        CHECK (unit IN ('art', 'CN', 'EN', 'JP', 'KR', 'TW')),
    res_version TEXT NOT NULL CHECK (length(res_version) > 0)
) STRICT;

CREATE TABLE arts (
    art_id TEXT NOT NULL
        CHECK (length(art_id) > 0 AND art_id = lower(art_id)),
    category TEXT NOT NULL
        CHECK (category IN ('image', 'background', 'item', 'character')),
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    PRIMARY KEY (category, art_id)
) STRICT;

CREATE TABLE source_arts (
    category TEXT NOT NULL
        CHECK (category IN ('image', 'background', 'item', 'character')),
    source_art_id TEXT NOT NULL
        CHECK (length(source_art_id) > 0 AND source_art_id = lower(source_art_id)),
    kind TEXT NOT NULL CHECK (kind IN ('character', 'composite_panel')),
    character_id TEXT,
    role TEXT CHECK (role IN ('body', 'face', 'whole_body')),
    variant TEXT,
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    PRIMARY KEY (category, source_art_id),
    CHECK (
        (kind = 'character'
            AND category = 'character'
            AND character_id IS NOT NULL
            AND length(character_id) > 0
            AND character_id = lower(character_id)
            AND role IS NOT NULL
            AND variant IS NOT NULL
            AND length(variant) > 0)
        OR
        (kind = 'composite_panel'
            AND character_id IS NULL
            AND role IS NULL
            AND variant IS NULL)
    )
) STRICT;

CREATE INDEX source_arts_by_character
    ON source_arts (character_id, role, variant, category, source_art_id)
    WHERE kind = 'character';

CREATE TABLE art_source_refs (
    category TEXT NOT NULL
        CHECK (category IN ('image', 'background', 'item', 'character')),
    art_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    source_category TEXT NOT NULL
        CHECK (source_category IN ('image', 'background', 'item', 'character')),
    source_art_id TEXT NOT NULL,
    PRIMARY KEY (category, art_id, position),
    UNIQUE (category, art_id, source_category, source_art_id),
    FOREIGN KEY (category, art_id)
        REFERENCES arts (category, art_id) ON DELETE CASCADE,
    FOREIGN KEY (source_category, source_art_id)
        REFERENCES source_arts (category, source_art_id)
) STRICT;

CREATE TABLE score_assets (
    asset_kind TEXT NOT NULL
        CHECK (asset_kind IN (
            'icon', 'logo', 'background', 'key_visual', 'title',
            'decoration', 'retro_background', 'split'
        )),
    asset_id TEXT NOT NULL
        CHECK (length(asset_id) > 0 AND asset_id = lower(asset_id)),
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    PRIMARY KEY (asset_kind, asset_id)
) STRICT;

CREATE TABLE score_videos (
    video_id TEXT PRIMARY KEY
        CHECK (length(video_id) > 0 AND video_id = lower(video_id)),
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    frame_rate_numerator INTEGER NOT NULL CHECK (frame_rate_numerator > 0),
    frame_rate_denominator INTEGER NOT NULL CHECK (frame_rate_denominator > 0),
    frame_count INTEGER NOT NULL CHECK (frame_count > 0)
) STRICT;

-- Locale tables reference unit_versions with ON DELETE CASCADE. Replacing one
-- locale removes the old Score, Archive, story, and gallery trees.
CREATE TABLE story_collections (
    locale TEXT NOT NULL CHECK (locale IN ('CN', 'EN', 'JP', 'KR', 'TW')),
    collection_id TEXT NOT NULL
        CHECK (length(collection_id) > 0 AND collection_id = lower(collection_id)),
    collection_kind TEXT NOT NULL
        CHECK (collection_kind IN ('movement_section', 'archive_group')),
    PRIMARY KEY (locale, collection_id),
    FOREIGN KEY (locale) REFERENCES unit_versions (unit) ON DELETE CASCADE,
    CHECK (
        (collection_kind = 'movement_section'
            AND collection_id GLOB 'movement_section:?*')
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
    CHECK (icon_asset_id IS NULL OR (length(icon_asset_id) > 0 AND icon_asset_id = lower(icon_asset_id))),
    CHECK (logo_asset_id IS NULL OR (length(logo_asset_id) > 0 AND logo_asset_id = lower(logo_asset_id))),
    CHECK (background_asset_id IS NULL OR (length(background_asset_id) > 0 AND background_asset_id = lower(background_asset_id)))
) STRICT;

CREATE TABLE movement_sections (
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
    CHECK (collection_id = 'movement_section:' || section_id),
    CHECK (key_visual_asset_id IS NULL OR (length(key_visual_asset_id) > 0 AND key_visual_asset_id = lower(key_visual_asset_id))),
    CHECK (review_group_id IS NULL OR (length(review_group_id) > 0 AND review_group_id = lower(review_group_id))),
    CHECK (title_asset_id IS NULL OR (length(title_asset_id) > 0 AND title_asset_id = lower(title_asset_id))),
    CHECK (background_asset_id IS NULL OR (length(background_asset_id) > 0 AND background_asset_id = lower(background_asset_id))),
    CHECK (decoration_asset_id IS NULL OR (length(decoration_asset_id) > 0 AND decoration_asset_id = lower(decoration_asset_id))),
    CHECK (retro_background_asset_id IS NULL OR (length(retro_background_asset_id) > 0 AND retro_background_asset_id = lower(retro_background_asset_id)))
) STRICT;

CREATE TABLE movement_locations (
    locale TEXT NOT NULL,
    movement_id TEXT NOT NULL,
    location_id TEXT NOT NULL
        CHECK (length(location_id) > 0 AND location_id = lower(location_id)),
    position INTEGER NOT NULL CHECK (position >= 0),
    location_type TEXT NOT NULL
        CHECK (location_type IN ('before', 'after', 'mainline_split', 'story_set')),
    sort_id INTEGER NOT NULL,
    start_time INTEGER NOT NULL,
    present_stage_id TEXT,
    unlock_stage_id TEXT,
    section_id TEXT,
    split_icon_asset_id TEXT,
    split_sub_name TEXT,
    video_id TEXT,
    PRIMARY KEY (locale, movement_id, location_id),
    UNIQUE (locale, movement_id, position),
    FOREIGN KEY (locale, movement_id)
        REFERENCES movements (locale, movement_id) ON DELETE CASCADE,
    FOREIGN KEY (locale, section_id)
        REFERENCES movement_sections (locale, section_id),
    CHECK ((location_type IN ('story_set', 'before', 'after')) = (section_id IS NOT NULL)),
    CHECK ((location_type = 'mainline_split') = (split_sub_name IS NOT NULL)),
    CHECK (split_icon_asset_id IS NULL OR (length(split_icon_asset_id) > 0 AND split_icon_asset_id = lower(split_icon_asset_id))),
    CHECK (video_id IS NULL OR (length(video_id) > 0 AND video_id = lower(video_id)))
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
    archive_kind TEXT NOT NULL
        CHECK (archive_kind IN (
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
    CHECK ((archive_kind = 'events') = (story_type IS NOT NULL))
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
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (locale, story_id),
    UNIQUE (locale, collection_id, position),
    FOREIGN KEY (locale, collection_id)
        REFERENCES story_collections (locale, collection_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE story_art_references (
    locale TEXT NOT NULL,
    story_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    art_id TEXT NOT NULL
        CHECK (length(art_id) > 0 AND art_id = lower(art_id)),
    kind TEXT NOT NULL CHECK (kind IN ('picture', 'character')),
    category TEXT NOT NULL
        CHECK (category IN ('image', 'background', 'item', 'character')),
    title TEXT,
    subtitle TEXT,
    names_json TEXT NOT NULL
        CHECK (json_valid(names_json) AND json_type(names_json) = 'array'),
    PRIMARY KEY (locale, story_id, position),
    FOREIGN KEY (locale, story_id)
        REFERENCES stories (locale, story_id) ON DELETE CASCADE,
    CHECK (kind <> 'character' OR category = 'character')
) STRICT;

CREATE INDEX story_art_references_by_art
    ON story_art_references (locale, art_id);

-- Asset references deliberately have no foreign key to their global tables.
-- A locale snapshot may lead the Windows art version; declared identifiers
-- remain representable and are reported as incomplete upstream data.

CREATE TRIGGER story_art_reference_names_insert
BEFORE INSERT ON story_art_references
WHEN EXISTS (
    SELECT 1 FROM json_each(NEW.names_json) WHERE type <> 'text'
)
BEGIN
    SELECT RAISE(ABORT, 'story art reference names must be strings');
END;

CREATE TRIGGER story_art_reference_names_update
BEFORE UPDATE OF names_json ON story_art_references
WHEN EXISTS (
    SELECT 1 FROM json_each(NEW.names_json) WHERE type <> 'text'
)
BEGIN
    SELECT RAISE(ABORT, 'story art reference names must be strings');
END;

CREATE TABLE gallery_groups (
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

CREATE INDEX gallery_groups_by_collection
    ON gallery_groups (locale, collection_id, position, gallery_id);

CREATE TABLE gallery_displays (
    locale TEXT NOT NULL,
    gallery_id TEXT NOT NULL,
    display_id TEXT NOT NULL
        CHECK (length(display_id) > 0 AND display_id = lower(display_id)),
    position INTEGER NOT NULL CHECK (position >= 0),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    related_story_id TEXT,
    related_stage_id TEXT,
    PRIMARY KEY (locale, gallery_id, display_id),
    UNIQUE (locale, gallery_id, position),
    FOREIGN KEY (locale, gallery_id)
        REFERENCES gallery_groups (locale, gallery_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE gallery_display_artworks (
    locale TEXT NOT NULL,
    gallery_id TEXT NOT NULL,
    display_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    cg_id TEXT NOT NULL
        CHECK (length(cg_id) > 0 AND cg_id = lower(cg_id)),
    art_id TEXT NOT NULL
        CHECK (length(art_id) > 0 AND art_id = lower(art_id)),
    category TEXT NOT NULL
        CHECK (category IN ('image', 'background', 'item', 'character')),
    composite_type TEXT NOT NULL
        CHECK (composite_type IN ('none', 'vertical', 'horizontal')),
    PRIMARY KEY (locale, gallery_id, display_id, position),
    UNIQUE (locale, gallery_id, display_id, cg_id),
    UNIQUE (locale, gallery_id, display_id, category, art_id),
    FOREIGN KEY (locale, gallery_id, display_id)
        REFERENCES gallery_displays (locale, gallery_id, display_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX gallery_display_artworks_by_art
    ON gallery_display_artworks (locale, category, art_id);

CREATE TABLE gallery_display_artwork_panels (
    locale TEXT NOT NULL,
    gallery_id TEXT NOT NULL,
    display_id TEXT NOT NULL,
    artwork_position INTEGER NOT NULL CHECK (artwork_position >= 0),
    position INTEGER NOT NULL CHECK (position >= 0),
    panel_art_id TEXT NOT NULL
        CHECK (
            length(panel_art_id) > 0
            AND panel_art_id = lower(panel_art_id)
            AND instr(panel_art_id, '/') = 0
        ),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    PRIMARY KEY (
        locale, gallery_id, display_id, artwork_position, position
    ),
    UNIQUE (
        locale, gallery_id, display_id, artwork_position, panel_art_id
    ),
    FOREIGN KEY (locale, gallery_id, display_id, artwork_position)
        REFERENCES gallery_display_artworks (
            locale, gallery_id, display_id, position
        ) ON DELETE CASCADE
) STRICT;

-- Search rows are a derived, locale-scoped index. The hierarchy and asset
-- tables remain authoritative; the updater rebuilds this table after every
-- art or locale transaction so the reader never observes a stale index.
CREATE TABLE search_entries (
    entry_key TEXT PRIMARY KEY CHECK (length(entry_key) > 0),
    locale TEXT NOT NULL
        CHECK (locale IN ('CN', 'EN', 'JP', 'KR', 'TW')),
    kind TEXT NOT NULL
        CHECK (kind IN (
            'story', 'movement', 'section', 'archive_group', 'gallery', 'art'
        )),
    entry_id TEXT NOT NULL CHECK (length(entry_id) > 0),
    category TEXT
        CHECK (category IS NULL OR category IN ('image', 'background', 'item', 'character')),
    collection_id TEXT,
    title TEXT NOT NULL,
    subtitle TEXT,
    search_text TEXT NOT NULL CHECK (length(search_text) > 0),
    parent_json TEXT CHECK (parent_json IS NULL OR json_valid(parent_json)),
    thumbnail_object_key TEXT,
    UNIQUE (locale, kind, entry_id, category),
    CHECK ((kind = 'art') = (category IS NOT NULL)),
    FOREIGN KEY (locale) REFERENCES unit_versions (unit) ON DELETE CASCADE
) STRICT;

CREATE INDEX search_entries_by_locale
    ON search_entries (locale, kind, entry_id);

PRAGMA user_version = 2;

COMMIT;
