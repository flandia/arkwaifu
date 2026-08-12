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
    source_art_id TEXT PRIMARY KEY
        CHECK (length(source_art_id) > 0 AND source_art_id = lower(source_art_id)),
    character_id TEXT NOT NULL
        CHECK (length(character_id) > 0 AND character_id = lower(character_id)),
    role TEXT NOT NULL CHECK (role IN ('body', 'face', 'whole_body')),
    variant TEXT NOT NULL CHECK (length(variant) > 0),
    object_key TEXT NOT NULL UNIQUE CHECK (length(object_key) > 0),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0)
) STRICT;

CREATE INDEX source_arts_by_character
    ON source_arts (character_id, role, variant, source_art_id);

CREATE TABLE art_source_refs (
    category TEXT NOT NULL CHECK (category = 'character'),
    art_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    source_art_id TEXT NOT NULL,
    PRIMARY KEY (category, art_id, position),
    UNIQUE (category, art_id, source_art_id),
    FOREIGN KEY (category, art_id)
        REFERENCES arts (category, art_id) ON DELETE CASCADE,
    FOREIGN KEY (source_art_id) REFERENCES source_arts (source_art_id)
) STRICT;

-- Locale tables reference unit_versions with ON DELETE CASCADE. Replacing one
-- locale therefore starts by deleting its version row, which removes the old
-- story and gallery tree before the new complete snapshot is inserted.
CREATE TABLE story_groups (
    locale TEXT NOT NULL CHECK (locale IN ('CN', 'EN', 'JP', 'KR', 'TW')),
    group_id TEXT NOT NULL
        CHECK (length(group_id) > 0 AND group_id = lower(group_id)),
    name TEXT NOT NULL,
    group_type TEXT NOT NULL
        CHECK (group_type IN ('main_story', 'major_event', 'minor_event', 'other')),
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (locale, group_id),
    UNIQUE (locale, position),
    FOREIGN KEY (locale) REFERENCES unit_versions (unit) ON DELETE CASCADE
) STRICT;

CREATE TABLE stories (
    locale TEXT NOT NULL,
    story_id TEXT NOT NULL
        CHECK (length(story_id) > 0 AND story_id = lower(story_id)),
    group_id TEXT NOT NULL,
    tag TEXT NOT NULL CHECK (tag IN ('before', 'after', 'interlude')),
    tag_text TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    info TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (locale, story_id),
    UNIQUE (locale, group_id, position),
    FOREIGN KEY (locale, group_id)
        REFERENCES story_groups (locale, group_id) ON DELETE CASCADE
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

-- Art references deliberately have no foreign key to arts. It is common for
-- an upstream locale snapshot to mention art which is not available yet; the
-- updater preserves that reference and emits a warning instead.

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

CREATE TABLE galleries (
    locale TEXT NOT NULL CHECK (locale IN ('CN', 'EN', 'JP', 'KR', 'TW')),
    gallery_id TEXT NOT NULL
        CHECK (length(gallery_id) > 0 AND gallery_id = lower(gallery_id)),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    PRIMARY KEY (locale, gallery_id),
    FOREIGN KEY (locale) REFERENCES unit_versions (unit) ON DELETE CASCADE
) STRICT;

CREATE TABLE gallery_entries (
    locale TEXT NOT NULL,
    gallery_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    entry_id TEXT NOT NULL
        CHECK (length(entry_id) > 0 AND entry_id = lower(entry_id)),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    art_id TEXT NOT NULL
        CHECK (length(art_id) > 0 AND art_id = lower(art_id)),
    category TEXT NOT NULL
        CHECK (category IN ('image', 'background', 'item', 'character')),
    PRIMARY KEY (locale, gallery_id, entry_id),
    UNIQUE (locale, gallery_id, position),
    FOREIGN KEY (locale, gallery_id)
        REFERENCES galleries (locale, gallery_id) ON DELETE CASCADE
) STRICT;

PRAGMA user_version = 2;

COMMIT;
