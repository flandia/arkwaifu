(** SQLite readers and the remote-generation replacement implementation. *)

open Lwt.Infix

type error = [ `Not_found | `Unavailable of string ]

type sitemap_data = {
  movements : (string * string) list;
  sections : (string * string * string) list;
  archive_groups : (string * string * string) list;
  galleries : (string * string) list;
}

type t = {
  close : unit -> unit Lwt.t;
  check : unit -> (unit, error) result Lwt.t;
  health : unit -> (unit, error) result Lwt.t;
  sitemap_data : unit -> (sitemap_data, error) result Lwt.t;
  narrative_image_asset : string -> string -> (Model.narrative_image_asset, error) result Lwt.t;
  material_asset : string -> string -> (Model.material_asset, error) result Lwt.t;
  narrative_media_asset :
    string -> string -> (Model.narrative_media_asset, error) result Lwt.t;
  orphan_narrative_image_assets : string -> (Model.orphan_narrative_image_asset list, error) result Lwt.t;
  orphan_narrative_media_assets :
    string -> (Model.orphan_narrative_media_asset list, error) result Lwt.t;
  narrative_image_asset_reverse_references :
    string -> string -> string -> (Model.narrative_image_asset_reverse_references, error) result Lwt.t;
  narrative_media_asset_reverse_references :
    string -> string -> string -> (Model.narrative_media_asset_reverse_references, error) result Lwt.t;
  movements : string -> (Model.movement list, error) result Lwt.t;
  movement : string -> string -> (Model.movement_detail, error) result Lwt.t;
  section :
    string ->
    string ->
    string ->
    (Model.section_detail, error) result Lwt.t;
  score_story :
    string ->
    string ->
    string ->
    string ->
    (Model.story_detail, error) result Lwt.t;
  archive_index : string -> (Model.archive_index_entry list, error) result Lwt.t;
  archive_groups :
    string -> string -> (Model.archive_group_summary list, error) result Lwt.t;
  archive_group :
    string ->
    string ->
    string ->
    (Model.archive_group_detail, error) result Lwt.t;
  archive_story :
    string ->
    string ->
    string ->
    string ->
    (Model.story_detail, error) result Lwt.t;
  galleries : string -> (Model.gallery_summary list, error) result Lwt.t;
  gallery : string -> string -> (Model.gallery, error) result Lwt.t;
  presentation_assets :
    string -> (Model.presentation_asset list, error) result Lwt.t;
  presentation_asset :
    string ->
    string ->
    string ->
    (Model.presentation_asset_detail, error) result Lwt.t;
  search : string -> string -> (Model.search_result list, error) result Lwt.t;
}

let unique_story_narrative_image_references references =
  let seen = Hashtbl.create (List.length references) in
  List.filter
    (fun (reference : Model.story_narrative_image_reference) ->
      let key = (reference.category, reference.asset_id) in
      if Hashtbl.mem seen key then false
      else (
        Hashtbl.add seen key ();
        true))
    references

let unique_story_narrative_media_references references =
  let seen = Hashtbl.create (List.length references) in
  List.filter
    (fun (reference : Model.story_narrative_media_reference) ->
      let key = (reference.kind, reference.asset_id) in
      if Hashtbl.mem seen key then false
      else (
        Hashtbl.add seen key ();
        true))
    references

let representative_story_narrative_image_reference = function
  | reference :: _ -> Some reference
  | [] -> None

let unique_strings values =
  let seen = Hashtbl.create (List.length values) in
  List.filter
    (fun value ->
      if Hashtbl.mem seen value then false
      else (
        Hashtbl.add seen value ();
        true))
    values

let character_prefix asset_id =
  match String.index_opt asset_id '#' with
  | Some position -> String.sub asset_id 0 position
  | None -> asset_id

let archive_category_of_route = function
  | "events" -> Some "events"
  | "operator-record" -> Some "operator_record"
  | "integrated-strategies" -> Some "integrated_strategies"
  | "reclamation-algorithm" -> Some "reclamation_algorithm"
  | "others" -> Some "others"
  | _ -> None

let archive_route_of_category = function
  | "events" -> "events"
  | "operator_record" -> "operator-record"
  | "integrated_strategies" -> "integrated-strategies"
  | "reclamation_algorithm" -> "reclamation-algorithm"
  | "others" -> "others"
  | value -> invalid_arg ("unknown Archive Category: " ^ value)

module Query = struct
  open Caqti_type.Std
  open Caqti_request.Infix

  let schema_version = (unit ->! int) "PRAGMA user_version"
  let ping =
    (unit ->! int)
      "SELECT EXISTS(SELECT 1 FROM sqlite_schema WHERE name = 'unit_versions')"

  let sitemap_movements =
    (unit ->* t2 string string)
      "SELECT locale, movement_id FROM movements ORDER BY locale, position"

  let sitemap_sections =
    (unit ->* t2 string (t2 string string))
      {|
        SELECT location.locale, location.movement_id, location.section_id
        FROM movement_locations AS location
        WHERE location.location_type = 'story_set'
        ORDER BY location.locale, location.movement_id, location.position
      |}

  let sitemap_archive_groups =
    (unit ->* t2 string (t2 string string))
      {|
        SELECT locale, archive_category, archive_id
        FROM archive_groups
        ORDER BY locale, position
      |}

  let sitemap_galleries =
    (unit ->* t2 string string)
      "SELECT locale, gallery_id FROM galleries ORDER BY locale, position"

  let narrative_image_asset =
    let row =
      t2 string
        (t2 string
           (t2 int64
              (t2 int
                 (t2 int (t2 (option string) (option string))))))
    in
    (t2 string string ->* row)
      {|
        SELECT narrative_image_asset.category, narrative_image_asset.object_key, narrative_image_asset.size, narrative_image_asset.width,
               narrative_image_asset.height, reference.material_category, reference.material_asset_id
        FROM narrative_image_assets AS narrative_image_asset
        LEFT JOIN narrative_asset_material_references AS reference
          ON reference.category = narrative_image_asset.category
         AND reference.asset_id = narrative_image_asset.asset_id
        WHERE narrative_image_asset.category = ? AND narrative_image_asset.asset_id = ?
        ORDER BY reference.position
      |}

  let material_asset =
    let row =
      t2 string
        (t2 string
           (t2 (option string)
              (t2 (option string)
                 (t2 (option string)
                    (t2 string (t2 int64 (t2 int int)))))))
    in
    (t2 string string ->? row)
      {|
        SELECT material_type, category, character_id, role, variant, object_key,
               size, width, height
        FROM material_assets
        WHERE category = ? AND asset_id = ?
      |}

  let material_asset_uses =
    (t2 string string ->* t2 string string)
      {|
        SELECT category, asset_id
        FROM narrative_asset_material_references
        WHERE material_category = ? AND material_asset_id = ?
        ORDER BY category, asset_id
      |}

  let narrative_media_asset =
    (t2 string string ->? string)
      {|
        SELECT json_object(
          'id', asset_id,
          'kind', category,
          'objectKey', object_key,
          'contentType', mime,
          'byteSize', size,
          'duration', COALESCE(
            duration,
            CAST(frame_count AS REAL) * frame_rate_denominator /
              frame_rate_numerator
          ),
          'sampleRate', sample_rate,
          'width', width,
          'height', height,
          'frameRate', CAST(frame_rate_numerator AS REAL) /
            frame_rate_denominator,
          'frameCount', frame_count
        )
        FROM narrative_media_assets
        WHERE category = ? AND asset_id = ?
      |}

  let orphan_narrative_image_assets =
    (string ->* t2 string (t2 string (t2 string (t2 int64 (t2 int int)))))
      {|
        WITH scope(locale) AS (VALUES (?))
        SELECT narrative_image_asset.category, narrative_image_asset.asset_id, narrative_image_asset.object_key,
               narrative_image_asset.size, narrative_image_asset.width, narrative_image_asset.height
        FROM narrative_image_assets AS narrative_image_asset
        WHERE NOT EXISTS (
          SELECT 1
          FROM story_narrative_image_references AS reference
          WHERE reference.asset_id = narrative_image_asset.asset_id
            AND reference.category = narrative_image_asset.category
            AND reference.locale = (SELECT locale FROM scope)
        )
          AND NOT EXISTS (
            SELECT 1
            FROM gallery_narrative_asset_references AS group_reference
            WHERE group_reference.category = narrative_image_asset.category
              AND group_reference.asset_id = narrative_image_asset.asset_id
              AND group_reference.locale = (SELECT locale FROM scope)
          )
        ORDER BY CASE narrative_image_asset.category
                   WHEN 'illustration' THEN 0
                   WHEN 'background' THEN 1
                   WHEN 'item' THEN 2
                   WHEN 'character' THEN 3
                   ELSE 4
                 END,
                 narrative_image_asset.asset_id
      |}

  let orphan_narrative_media_assets =
    (string ->* t2 string (t2 string (t2 string (t2 int64 string))))
      {|
        WITH scope(locale) AS (VALUES (?))
        SELECT media.category, media.asset_id, media.mime,
               media.size, media.object_key
        FROM narrative_media_assets AS media
        WHERE NOT EXISTS (
          SELECT 1
          FROM story_narrative_media_references AS reference
          WHERE reference.asset_id = media.asset_id
            AND reference.locale = (SELECT locale FROM scope)
            AND reference.category = media.category
        )
        ORDER BY CASE media.category WHEN 'video' THEN 0 ELSE 1 END,
                 media.asset_id
      |}

  let narrative_image_asset_reverse_references_exists =
    (t2 string string ->? int)
      "SELECT 1 FROM narrative_image_assets WHERE category = ? AND asset_id = ?"

  let narrative_media_asset_reverse_references_exists =
    (t2 string string ->? int)
      "SELECT 1 FROM narrative_media_assets WHERE category = ? AND asset_id = ?"

  let narrative_image_asset_reverse_references_occurrences =
    (t2 string (t2 string string) ->* string)
      {|
        SELECT json_object(
          'parentKind', collection.collection_kind,
          'movementID', movement.movement_id,
          'movementName', movement.name,
          'sectionID', section.section_id,
          'sectionName', section.name,
          'archiveCategory', archive.archive_category,
          'groupID', archive.archive_id,
          'groupName', archive.name,
          'storyID', story.story_id,
          'storyName', story.name,
          'storyCode', story.code,
          'storyTagText', story.tag_text,
          'names', reference.names_json
        )
        FROM story_narrative_image_references AS reference
        JOIN stories AS story
          ON story.locale = reference.locale
         AND story.story_id = reference.story_id
        JOIN story_collections AS collection
          ON collection.locale = story.locale
         AND collection.collection_id = story.collection_id
        LEFT JOIN sections AS section
          ON section.locale = collection.locale
         AND section.collection_id = collection.collection_id
        LEFT JOIN movement_locations AS location
          ON location.locale = section.locale
         AND location.section_id = section.section_id
         AND location.location_type = 'story_set'
        LEFT JOIN movements AS movement
          ON movement.locale = location.locale
         AND movement.movement_id = location.movement_id
        LEFT JOIN archive_groups AS archive
          ON archive.locale = collection.locale
         AND archive.collection_id = collection.collection_id
        WHERE reference.locale = ? AND reference.category = ?
          AND reference.asset_id = ?
        ORDER BY COALESCE(movement.position, archive.position), story.position,
                 reference.position
      |}

  let narrative_image_asset_reverse_references_character_variants =
    (t2 string (t2 string (t2 string (t2 string string))) ->* string)
      {|
        SELECT json_object(
          'artworkID', narrative_image_asset.asset_id,
          'objectKey', narrative_image_asset.object_key,
          'names', reference.names_json
        )
        FROM narrative_image_assets AS narrative_image_asset
        LEFT JOIN story_narrative_image_references AS reference
          ON reference.locale = ?
         AND reference.category = narrative_image_asset.category
         AND reference.asset_id = narrative_image_asset.asset_id
        WHERE narrative_image_asset.category = 'character' AND narrative_image_asset.asset_id <> ?
          AND (
            narrative_image_asset.asset_id = ?
            OR substr(narrative_image_asset.asset_id, 1, length(?) + 1) = ? || '#'
          )
        ORDER BY narrative_image_asset.asset_id, reference.story_id, reference.position
      |}

  let narrative_image_asset_reverse_references_textures =
    (t2 string string ->* t2 string string)
      {|
        SELECT asset_id, object_key
        FROM narrative_image_assets
        WHERE category = 'illustration'
          AND substr(asset_id, 1, length(?) + 1) = ? || '/'
        ORDER BY asset_id
      |}

  let narrative_image_asset_reverse_references_galleries =
    (t2 string (t2 string string) ->* string)
      {|
        SELECT json_object(
          'galleryID', gallery.gallery_id,
          'galleryName', gallery.name,
          'galleryDescription', gallery.description,
          'groupID', gallery_group.group_id,
          'groupName', gallery_group.name,
          'groupDescription', gallery_group.description,
          'cgID', narrative_image_asset.cg_id
        )
        FROM gallery_narrative_asset_references AS narrative_image_asset
        JOIN gallery_groups AS gallery_group
          ON gallery_group.locale = narrative_image_asset.locale
         AND gallery_group.gallery_id = narrative_image_asset.gallery_id
         AND gallery_group.group_id = narrative_image_asset.group_id
        JOIN galleries AS gallery
          ON gallery.locale = gallery_group.locale
         AND gallery.gallery_id = gallery_group.gallery_id
        WHERE narrative_image_asset.locale = ? AND narrative_image_asset.category = ? AND narrative_image_asset.asset_id = ?
        ORDER BY gallery.position, gallery_group.position, narrative_image_asset.position
      |}

  let narrative_media_asset_reverse_references_occurrences =
    (t2 string (t2 string string) ->* string)
      {|
        SELECT json_object(
          'parentKind', collection.collection_kind,
          'movementID', movement.movement_id,
          'movementName', movement.name,
          'sectionID', section.section_id,
          'sectionName', section.name,
          'archiveCategory', archive.archive_category,
          'groupID', archive.archive_id,
          'groupName', archive.name,
          'storyID', story.story_id,
          'storyName', story.name,
          'storyCode', story.code,
          'storyTagText', story.tag_text
        )
        FROM story_narrative_media_references AS reference
        JOIN stories AS story
          ON story.locale = reference.locale
         AND story.story_id = reference.story_id
        JOIN story_collections AS collection
          ON collection.locale = story.locale
         AND collection.collection_id = story.collection_id
        LEFT JOIN sections AS section
          ON section.locale = collection.locale
         AND section.collection_id = collection.collection_id
        LEFT JOIN movement_locations AS location
          ON location.locale = section.locale
         AND location.section_id = section.section_id
         AND location.location_type = 'story_set'
        LEFT JOIN movements AS movement
          ON movement.locale = location.locale
         AND movement.movement_id = location.movement_id
        LEFT JOIN archive_groups AS archive
          ON archive.locale = collection.locale
         AND archive.collection_id = collection.collection_id
        WHERE reference.locale = ?
          AND reference.category = ?
          AND reference.asset_id = ?
        ORDER BY COALESCE(movement.position, archive.position), story.position,
                 reference.position
      |}

  let narrative_media_asset_reverse_references_sections =
    (t2 string (t2 string string) ->* string)
      {|
        SELECT json_object(
          'parentKind', 'section',
          'movementID', movement.movement_id,
          'movementName', movement.name,
          'sectionID', section.section_id,
          'sectionName', section.name
        )
        FROM sections AS section
        JOIN movement_locations AS location
          ON location.locale = section.locale
         AND location.section_id = section.section_id
         AND location.location_type = 'story_set'
        JOIN movements AS movement
          ON movement.locale = location.locale
         AND movement.movement_id = location.movement_id
        WHERE section.locale = ? AND ? = 'video'
          AND EXISTS (
            SELECT 1
            FROM stories AS entry_story
            JOIN story_narrative_media_references AS reference
              ON reference.locale = entry_story.locale
             AND reference.story_id = entry_story.story_id
            WHERE entry_story.locale = section.locale
              AND reference.category = 'video'
              AND reference.asset_id = ?
              AND (
                entry_story.story_id =
                  'others:obt:main:' || section.review_group_id || '_zone_enter'
                OR entry_story.story_id =
                  'others:activities:' || section.review_group_id ||
                  ':level_' || section.review_group_id || '_entry'
              )
          )
        ORDER BY movement.position, location.position
      |}

  let narrative_media_asset_reverse_references_archives =
    (t2 string (t2 string string) ->* string)
      {|
        SELECT json_object(
          'parentKind', 'archive_group',
          'archiveCategory', archive.archive_category,
          'groupID', archive.archive_id,
          'groupName', archive.name
        )
        FROM archive_groups AS archive
        WHERE archive.locale = ? AND ? = 'video'
          AND EXISTS (
            SELECT 1
            FROM stories AS entry_story
            JOIN story_narrative_media_references AS reference
              ON reference.locale = entry_story.locale
             AND reference.story_id = entry_story.story_id
            WHERE entry_story.locale = archive.locale
              AND entry_story.story_id =
                'others:activities:' || archive.archive_id ||
                ':level_' || archive.archive_id || '_entry'
              AND reference.category = 'video'
              AND reference.asset_id = ?
          )
        ORDER BY archive.position
      |}

  let movements =
    (string ->* string)
      {|
        SELECT json_object(
          'id', movement.movement_id,
          'name', movement.name,
          'type', movement.movement_type,
          'position', movement.position,
          'sectionCount', (
            SELECT COUNT(*)
            FROM movement_locations AS section_location
            WHERE section_location.locale = movement.locale
              AND section_location.movement_id = movement.movement_id
              AND section_location.location_type = 'story_set'
              AND section_location.section_id IS NOT NULL
          ),
          'startTime', movement.start_time,
          'iconID', movement.icon_asset_id,
          'iconObjectKey', icon.object_key,
          'iconByteSize', icon.size,
          'iconWidth', icon.width,
          'iconHeight', icon.height,
          'logoID', movement.logo_asset_id,
          'logoObjectKey', logo.object_key,
          'logoByteSize', logo.size,
          'logoWidth', logo.width,
          'logoHeight', logo.height,
          'backgroundID', movement.background_asset_id,
          'backgroundObjectKey', background.object_key,
          'backgroundByteSize', background.size,
          'backgroundWidth', background.width,
          'backgroundHeight', background.height,
          'videoID', video_location.video_id,
          'videoObjectKey', video.object_key,
          'videoByteSize', video.size,
          'videoWidth', video.width,
          'videoHeight', video.height,
          'videoRateNumerator', video.frame_rate_numerator,
          'videoRateDenominator', video.frame_rate_denominator,
          'videoFrameCount', video.frame_count
        )
        FROM movements AS movement
        LEFT JOIN presentation_image_assets AS icon
          ON icon.category = 'icon'
         AND icon.asset_id = movement.icon_asset_id
        LEFT JOIN presentation_image_assets AS logo
          ON logo.category = 'logo'
         AND logo.asset_id = movement.logo_asset_id
        LEFT JOIN presentation_image_assets AS background
          ON background.category = 'background'
         AND background.asset_id = movement.background_asset_id
        LEFT JOIN movement_locations AS video_location
          ON video_location.locale = movement.locale
         AND video_location.movement_id = movement.movement_id
         AND video_location.location_id = (
           SELECT candidate.location_id
           FROM movement_locations AS candidate
           WHERE candidate.locale = movement.locale
             AND candidate.movement_id = movement.movement_id
             AND candidate.video_id IS NOT NULL
           ORDER BY CASE candidate.location_type
                      WHEN 'story_set' THEN 0
                      WHEN 'divider' THEN 1
                      ELSE 2
                    END,
                    candidate.position
           LIMIT 1
         )
        LEFT JOIN presentation_video_assets AS video
          ON video.category = 'video' AND video.asset_id = video_location.video_id
        WHERE movement.locale = ?
        ORDER BY movement.position
      |}

  let sections_by_movement =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'id', section.section_id,
          'collectionID', section.collection_id,
          'name', section.name,
          'description', section.description,
          'type', section.section_type,
          'position', location.position,
          'sortByYear', section.sort_by_year,
          'sortWithinYear', section.sort_within_year,
          'storyCount', (
            SELECT COUNT(*) FROM stories AS story
            WHERE story.locale = section.locale
              AND story.collection_id = section.collection_id
          ),
          'keyVisualID', section.key_visual_asset_id,
          'keyVisualObjectKey', key_visual.object_key,
          'keyVisualByteSize', key_visual.size,
          'keyVisualWidth', key_visual.width,
          'keyVisualHeight', key_visual.height,
          'titleID', section.title_asset_id,
          'titleObjectKey', title.object_key,
          'titleByteSize', title.size,
          'titleWidth', title.width,
          'titleHeight', title.height,
          'backgroundID', section.background_asset_id,
          'backgroundObjectKey', background.object_key,
          'backgroundByteSize', background.size,
          'backgroundWidth', background.width,
          'backgroundHeight', background.height,
          'decorationID', section.decoration_asset_id,
          'decorationObjectKey', decoration.object_key,
          'decorationByteSize', decoration.size,
          'decorationWidth', decoration.width,
          'decorationHeight', decoration.height,
          'retroBackgroundID', section.retro_background_asset_id,
          'retroBackgroundObjectKey', retro_background.object_key,
          'retroBackgroundByteSize', retro_background.size,
          'retroBackgroundWidth', retro_background.width,
          'retroBackgroundHeight', retro_background.height,
          'videoID', location.video_id,
          'videoObjectKey', video.object_key,
          'videoByteSize', video.size,
          'videoWidth', video.width,
          'videoHeight', video.height,
          'videoRateNumerator', video.frame_rate_numerator,
          'videoRateDenominator', video.frame_rate_denominator,
          'videoFrameCount', video.frame_count,
          'openingMedia', COALESCE((
            SELECT json_group_array(json_object(
              'id', reference.asset_id,
              'kind', CASE WHEN reference.category = 'video'
                           THEN 'video' ELSE reference.usage END,
              'contentType', asset.mime,
              'byteSize', asset.size,
              'objectKey', asset.object_key
            ))
            FROM stories AS entry_story
            JOIN story_narrative_media_references AS reference
              ON reference.locale = entry_story.locale
             AND reference.story_id = entry_story.story_id
            LEFT JOIN narrative_media_assets AS asset
              ON asset.category = 'video'
             AND asset.asset_id = reference.asset_id
            WHERE entry_story.locale = section.locale
              AND reference.category = 'video'
              AND (
                entry_story.story_id =
                  'others:obt:main:' || section.review_group_id || '_zone_enter'
                OR entry_story.story_id =
                  'others:activities:' || section.review_group_id ||
                  ':level_' || section.review_group_id || '_entry'
              )
            ORDER BY reference.position
          ), json('[]'))
        )
        FROM movement_locations AS location
        JOIN sections AS section
          ON section.locale = location.locale
         AND section.section_id = location.section_id
        LEFT JOIN presentation_image_assets AS key_visual
          ON key_visual.category = 'key-visual'
         AND key_visual.asset_id = section.key_visual_asset_id
        LEFT JOIN presentation_image_assets AS title
          ON title.category = 'title'
         AND title.asset_id = section.title_asset_id
        LEFT JOIN presentation_image_assets AS background
          ON background.category = 'background'
         AND background.asset_id = section.background_asset_id
        LEFT JOIN presentation_image_assets AS decoration
          ON decoration.category = 'decoration'
         AND decoration.asset_id = section.decoration_asset_id
        LEFT JOIN presentation_image_assets AS retro_background
          ON retro_background.category = 'retro-background'
         AND retro_background.asset_id = section.retro_background_asset_id
        LEFT JOIN presentation_video_assets AS video
          ON video.category = 'video' AND video.asset_id = location.video_id
        WHERE location.locale = ? AND location.movement_id = ?
          AND location.location_type = 'story_set'
        ORDER BY location.position
      |}

  let section =
    (t2 string (t2 string string) ->? string)
      {|
        SELECT json_object(
          'id', section.section_id,
          'collectionID', section.collection_id,
          'name', section.name,
          'description', section.description,
          'type', section.section_type,
          'position', location.position,
          'sortByYear', section.sort_by_year,
          'sortWithinYear', section.sort_within_year,
          'storyCount', (
            SELECT COUNT(*) FROM stories AS story
            WHERE story.locale = section.locale
              AND story.collection_id = section.collection_id
          ),
          'keyVisualID', section.key_visual_asset_id,
          'keyVisualObjectKey', key_visual.object_key,
          'keyVisualByteSize', key_visual.size,
          'keyVisualWidth', key_visual.width,
          'keyVisualHeight', key_visual.height,
          'titleID', section.title_asset_id,
          'titleObjectKey', title.object_key,
          'titleByteSize', title.size,
          'titleWidth', title.width,
          'titleHeight', title.height,
          'backgroundID', section.background_asset_id,
          'backgroundObjectKey', background.object_key,
          'backgroundByteSize', background.size,
          'backgroundWidth', background.width,
          'backgroundHeight', background.height,
          'decorationID', section.decoration_asset_id,
          'decorationObjectKey', decoration.object_key,
          'decorationByteSize', decoration.size,
          'decorationWidth', decoration.width,
          'decorationHeight', decoration.height,
          'retroBackgroundID', section.retro_background_asset_id,
          'retroBackgroundObjectKey', retro_background.object_key,
          'retroBackgroundByteSize', retro_background.size,
          'retroBackgroundWidth', retro_background.width,
          'retroBackgroundHeight', retro_background.height,
          'videoID', active_video_location.video_id,
          'videoObjectKey', video.object_key,
          'videoByteSize', video.size,
          'videoWidth', video.width,
          'videoHeight', video.height,
          'videoRateNumerator', video.frame_rate_numerator,
          'videoRateDenominator', video.frame_rate_denominator,
          'videoFrameCount', video.frame_count,
          'openingMedia', COALESCE((
            SELECT json_group_array(json_object(
              'id', reference.asset_id,
              'kind', CASE WHEN reference.category = 'video'
                           THEN 'video' ELSE reference.usage END,
              'contentType', asset.mime,
              'byteSize', asset.size,
              'objectKey', asset.object_key
            ))
            FROM stories AS entry_story
            JOIN story_narrative_media_references AS reference
              ON reference.locale = entry_story.locale
             AND reference.story_id = entry_story.story_id
            LEFT JOIN narrative_media_assets AS asset
              ON asset.category = 'video'
             AND asset.asset_id = reference.asset_id
            WHERE entry_story.locale = section.locale
              AND reference.category = 'video'
              AND (
                entry_story.story_id =
                  'others:obt:main:' || section.review_group_id || '_zone_enter'
                OR entry_story.story_id =
                  'others:activities:' || section.review_group_id ||
                  ':level_' || section.review_group_id || '_entry'
              )
            ORDER BY reference.position
          ), json('[]'))
        )
        FROM movement_locations AS location
        JOIN sections AS section
          ON section.locale = location.locale
         AND section.section_id = location.section_id
        LEFT JOIN presentation_image_assets AS key_visual
          ON key_visual.category = 'key-visual'
         AND key_visual.asset_id = section.key_visual_asset_id
        LEFT JOIN presentation_image_assets AS title
          ON title.category = 'title'
         AND title.asset_id = section.title_asset_id
        LEFT JOIN presentation_image_assets AS background
          ON background.category = 'background'
         AND background.asset_id = section.background_asset_id
        LEFT JOIN presentation_image_assets AS decoration
          ON decoration.category = 'decoration'
         AND decoration.asset_id = section.decoration_asset_id
        LEFT JOIN presentation_image_assets AS retro_background
          ON retro_background.category = 'retro-background'
         AND retro_background.asset_id = section.retro_background_asset_id
        LEFT JOIN movement_locations AS active_video_location
          ON active_video_location.locale = location.locale
         AND active_video_location.movement_id = location.movement_id
         AND active_video_location.location_id = (
           SELECT candidate.location_id
           FROM movement_locations AS candidate
           WHERE candidate.locale = location.locale
             AND candidate.movement_id = location.movement_id
             AND candidate.location_type = 'divider'
             AND candidate.video_id IS NOT NULL
             AND candidate.position <= location.position
           ORDER BY candidate.position DESC
           LIMIT 1
         )
        LEFT JOIN presentation_video_assets AS video
          ON video.category = 'video'
         AND video.asset_id = active_video_location.video_id
        WHERE location.locale = ? AND location.movement_id = ?
          AND location.section_id = ? AND location.location_type = 'story_set'
      |}

  let movement_dividers =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'id', location.location_id,
          'position', location.position,
          'subName', location.divider_sub_name,
          'iconID', location.divider_icon_asset_id,
          'iconObjectKey', icon.object_key,
          'iconByteSize', icon.size,
          'iconWidth', icon.width,
          'iconHeight', icon.height,
          'videoID', location.video_id,
          'videoObjectKey', video.object_key,
          'videoByteSize', video.size,
          'videoWidth', video.width,
          'videoHeight', video.height,
          'videoRateNumerator', video.frame_rate_numerator,
          'videoRateDenominator', video.frame_rate_denominator,
          'videoFrameCount', video.frame_count
        )
        FROM movement_locations AS location
        LEFT JOIN presentation_image_assets AS icon
          ON icon.category = 'divider'
         AND icon.asset_id = location.divider_icon_asset_id
        LEFT JOIN presentation_video_assets AS video
          ON video.category = 'video' AND video.asset_id = location.video_id
        WHERE location.locale = ? AND location.movement_id = ?
          AND location.location_type = 'divider'
        ORDER BY location.position
      |}

  let collection_stories =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'id', story_id, 'tag', tag, 'tagText', tag_text, 'code', code,
          'name', name, 'info', info
        )
        FROM stories
        WHERE locale = ? AND collection_id = ?
        ORDER BY position
      |}

  let story_detail =
    (t2 string (t2 string string) ->? string)
      {|
        SELECT json_object(
          'id', story.story_id, 'tag', story.tag, 'tagText', story.tag_text,
          'code', story.code, 'name', story.name, 'info', story.info,
          'text', story.text,
          'media', COALESCE(
            (
              SELECT json_group_array(json_object(
                'id', reference.asset_id,
                'kind', CASE WHEN reference.category = 'video'
                             THEN 'video' ELSE reference.usage END,
                'contentType', asset.mime,
                'byteSize', asset.size,
                'objectKey', asset.object_key
              ))
              FROM story_narrative_media_references AS reference
              LEFT JOIN narrative_media_assets AS asset
                ON asset.category = CASE
                  WHEN reference.category = 'video' THEN 'video'
                  ELSE 'audio'
                END
               AND asset.asset_id = reference.asset_id
              WHERE reference.locale = story.locale
                AND reference.story_id = story.story_id
              ORDER BY reference.position
            ),
            json('[]')
          )
        )
        FROM stories AS story
        WHERE story.locale = ?
          AND story.collection_id = ?
          AND story.story_id = ?
      |}

  let collection_story_references =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'storyID', story.story_id, 'artworkID', reference.asset_id,
          'kind', reference.kind, 'category', reference.category,
          'isAnimeKV', json(CASE
            WHEN reference.category = 'background' AND EXISTS (
              SELECT 1
              FROM narrative_image_assets AS texture
              WHERE texture.category = 'illustration'
                AND substr(texture.asset_id, 1, length(reference.asset_id) + 1) =
                    reference.asset_id || '/'
            ) THEN 'true' ELSE 'false' END),
          'title', reference.title, 'subtitle', reference.subtitle,
          'names', json(reference.names_json), 'objectKey', narrative_image_asset.object_key
        )
        FROM stories AS story
        JOIN story_narrative_image_references AS reference
          ON reference.locale = story.locale
         AND reference.story_id = story.story_id
        LEFT JOIN narrative_image_assets AS narrative_image_asset
          ON narrative_image_asset.category = reference.category
         AND narrative_image_asset.asset_id = reference.asset_id
        WHERE story.locale = ? AND story.collection_id = ?
        ORDER BY story.position, reference.position
      |}

  let collection_story_narrative_media_references =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'id', reference.asset_id,
          'kind', CASE WHEN reference.category = 'video'
                       THEN 'video' ELSE reference.usage END,
          'contentType', asset.mime,
          'byteSize', asset.size,
          'objectKey', asset.object_key
        )
        FROM stories AS story
        JOIN story_narrative_media_references AS reference
          ON reference.locale = story.locale
         AND reference.story_id = story.story_id
        LEFT JOIN narrative_media_assets AS asset
          ON asset.category = CASE
            WHEN reference.category = 'video' THEN 'video'
            ELSE 'audio'
          END
         AND asset.asset_id = reference.asset_id
        WHERE story.locale = ? AND story.collection_id = ?
        ORDER BY story.position, reference.position
      |}

  let story_references =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'storyID', reference.story_id, 'artworkID', reference.asset_id,
          'kind', reference.kind, 'category', reference.category,
          'isAnimeKV', json(CASE
            WHEN reference.category = 'background' AND EXISTS (
              SELECT 1
              FROM narrative_image_assets AS texture
              WHERE texture.category = 'illustration'
                AND substr(texture.asset_id, 1, length(reference.asset_id) + 1) =
                    reference.asset_id || '/'
            ) THEN 'true' ELSE 'false' END),
          'title', reference.title, 'subtitle', reference.subtitle,
          'names', json(reference.names_json), 'objectKey', narrative_image_asset.object_key
        )
        FROM story_narrative_image_references AS reference
        LEFT JOIN narrative_image_assets AS narrative_image_asset
          ON narrative_image_asset.category = reference.category
         AND narrative_image_asset.asset_id = reference.asset_id
        WHERE reference.locale = ? AND reference.story_id = ?
        ORDER BY reference.position
      |}

  let archive_index =
    (string ->* t2 string int)
      {|
        WITH categories(category, position) AS (
          VALUES ('events', 0), ('operator_record', 1),
                 ('integrated_strategies', 2),
                 ('reclamation_algorithm', 3), ('others', 4)
        )
        SELECT categories.category, COUNT(archive.archive_id)
        FROM categories
        LEFT JOIN archive_groups AS archive
          ON archive.locale = ? AND archive.archive_category = categories.category
        GROUP BY categories.category, categories.position
        ORDER BY categories.position
      |}

  let archive_groups =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'id', archive_id, 'collectionID', collection_id, 'name', name,
          'archiveCategory', archive_category, 'storyType', story_type
        )
        FROM archive_groups
        WHERE locale = ? AND archive_category = ?
        ORDER BY position
      |}

  let archive_group_references =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'groupID', archive.archive_id, 'storyID', story.story_id,
          'artworkID', reference.asset_id, 'kind', reference.kind,
          'category', reference.category, 'title', reference.title,
          'isAnimeKV', json(CASE
            WHEN reference.category = 'background' AND EXISTS (
              SELECT 1
              FROM narrative_image_assets AS texture
              WHERE texture.category = 'illustration'
                AND substr(texture.asset_id, 1, length(reference.asset_id) + 1) =
                    reference.asset_id || '/'
            ) THEN 'true' ELSE 'false' END),
          'subtitle', reference.subtitle, 'names', json(reference.names_json),
          'objectKey', narrative_image_asset.object_key
        )
        FROM archive_groups AS archive
        JOIN stories AS story
          ON story.locale = archive.locale
         AND story.collection_id = archive.collection_id
        JOIN story_narrative_image_references AS reference
          ON reference.locale = story.locale
         AND reference.story_id = story.story_id
        LEFT JOIN narrative_image_assets AS narrative_image_asset
          ON narrative_image_asset.category = reference.category AND narrative_image_asset.asset_id = reference.asset_id
        WHERE archive.locale = ? AND archive.archive_category = ?
        ORDER BY archive.position, story.position, reference.position
      |}

  let archive_group =
    (t2 string (t2 string string) ->? string)
      {|
        SELECT json_object(
          'id', archive_id, 'collectionID', collection_id, 'name', name,
          'archiveCategory', archive_category, 'storyType', story_type
        )
        FROM archive_groups
        WHERE locale = ? AND archive_category = ? AND archive_id = ?
      |}

  let archive_entry_media =
    (t2 string (t2 string string) ->* string)
      {|
        SELECT json_object(
          'id', reference.asset_id,
          'kind', CASE WHEN reference.category = 'video'
                       THEN 'video' ELSE reference.usage END,
          'contentType', asset.mime,
          'byteSize', asset.size,
          'objectKey', asset.object_key
        )
        FROM stories AS entry_story
        JOIN story_narrative_media_references AS reference
          ON reference.locale = entry_story.locale
         AND reference.story_id = entry_story.story_id
        LEFT JOIN narrative_media_assets AS asset
          ON asset.category = 'video'
         AND asset.asset_id = reference.asset_id
        WHERE entry_story.locale = ?
          AND entry_story.story_id =
            'others:activities:' || ? || ':level_' || ? || '_entry'
          AND reference.category = 'video'
        ORDER BY reference.position
      |}

  let gallery_bases =
    (string ->* string)
      {|
        SELECT json_object(
          'id', gallery.gallery_id, 'collectionID', gallery.collection_id,
          'name', gallery.name, 'description', gallery.description,
          'parentKind', collection.collection_kind,
          'movementID', movement.movement_id, 'movementName', movement.name,
          'sectionID', section.section_id, 'sectionName', section.name,
          'archiveCategory', archive.archive_category, 'groupID', archive.archive_id,
          'groupName', archive.name
        )
        FROM galleries AS gallery
        JOIN story_collections AS collection
          ON collection.locale = gallery.locale
         AND collection.collection_id = gallery.collection_id
        LEFT JOIN sections AS section
          ON section.locale = collection.locale
         AND section.collection_id = collection.collection_id
        LEFT JOIN movement_locations AS location
          ON location.locale = section.locale
         AND location.section_id = section.section_id
         AND location.location_type = 'story_set'
        LEFT JOIN movements AS movement
          ON movement.locale = location.locale
         AND movement.movement_id = location.movement_id
        LEFT JOIN archive_groups AS archive
          ON archive.locale = collection.locale
         AND archive.collection_id = collection.collection_id
        WHERE gallery.locale = ?
        ORDER BY gallery.position
      |}

  let gallery_base =
    (t2 string string ->? string)
      {|
        SELECT json_object(
          'id', gallery.gallery_id, 'collectionID', gallery.collection_id,
          'name', gallery.name, 'description', gallery.description,
          'parentKind', collection.collection_kind,
          'movementID', movement.movement_id, 'movementName', movement.name,
          'sectionID', section.section_id, 'sectionName', section.name,
          'archiveCategory', archive.archive_category, 'groupID', archive.archive_id,
          'groupName', archive.name
        )
        FROM galleries AS gallery
        JOIN story_collections AS collection
          ON collection.locale = gallery.locale
         AND collection.collection_id = gallery.collection_id
        LEFT JOIN sections AS section
          ON section.locale = collection.locale
         AND section.collection_id = collection.collection_id
        LEFT JOIN movement_locations AS location
          ON location.locale = section.locale
         AND location.section_id = section.section_id
         AND location.location_type = 'story_set'
        LEFT JOIN movements AS movement
          ON movement.locale = location.locale
         AND movement.movement_id = location.movement_id
        LEFT JOIN archive_groups AS archive
          ON archive.locale = collection.locale
         AND archive.collection_id = collection.collection_id
        WHERE gallery.locale = ? AND gallery.gallery_id = ?
      |}

  let gallery_by_collection =
    (t2 string string ->? string)
      {|
        SELECT gallery_id FROM galleries
        WHERE locale = ? AND collection_id = ?
        ORDER BY position LIMIT 1
      |}

  let gallery_groups =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'id', group_id, 'position', position, 'name', name,
          'description', description, 'relatedStoryID', related_story_id,
          'relatedStageID', related_stage_id
        )
        FROM gallery_groups
        WHERE locale = ? AND gallery_id = ?
        ORDER BY position
      |}

  let gallery_references =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'groupID', group_reference.group_id, 'position', group_reference.position,
          'cgID', group_reference.cg_id, 'artworkID', group_reference.asset_id,
          'category', group_reference.category, 'objectKey', narrative_image_asset.object_key
        )
        FROM gallery_narrative_asset_references AS group_reference
        LEFT JOIN narrative_image_assets AS narrative_image_asset
          ON narrative_image_asset.category = group_reference.category
         AND narrative_image_asset.asset_id = group_reference.asset_id
        WHERE group_reference.locale = ? AND group_reference.gallery_id = ?
        ORDER BY group_reference.group_id, group_reference.position
      |}

  let gallery_previews =
    (t2 string string ->* t2 string (option string))
      {|
        WITH first_members AS (
          SELECT narrative_image_asset.locale, narrative_image_asset.gallery_id, narrative_image_asset.group_id,
                 narrative_image_asset.category, narrative_image_asset.asset_id,
                 ROW_NUMBER() OVER (
                   PARTITION BY narrative_image_asset.locale, narrative_image_asset.gallery_id,
                                narrative_image_asset.group_id
                   ORDER BY narrative_image_asset.position
                 ) AS member_rank
          FROM gallery_narrative_asset_references AS narrative_image_asset
          WHERE narrative_image_asset.locale = ?
        )
        SELECT gallery.gallery_id, narrative_image_asset.object_key
        FROM galleries AS gallery
        JOIN gallery_groups AS gallery_group
          ON gallery_group.locale = gallery.locale
         AND gallery_group.gallery_id = gallery.gallery_id
        LEFT JOIN first_members AS member
          ON member.locale = gallery_group.locale
         AND member.gallery_id = gallery_group.gallery_id
         AND member.group_id = gallery_group.group_id
         AND member.member_rank = 1
        LEFT JOIN narrative_image_assets AS narrative_image_asset
          ON narrative_image_asset.category = member.category AND narrative_image_asset.asset_id = member.asset_id
        WHERE gallery.locale = ?
        ORDER BY gallery.position, gallery_group.position
      |}

  let presentation_assets =
    (t3 string string string ->* string)
      {|
        WITH scope(locale, category_filter, asset_id_filter) AS (VALUES (?, ?, ?)),
        presentation_references(category, asset_id) AS (
          SELECT 'icon', icon_asset_id FROM movements
            WHERE locale = (SELECT locale FROM scope) AND icon_asset_id IS NOT NULL
          UNION ALL SELECT 'logo', logo_asset_id FROM movements
            WHERE locale = (SELECT locale FROM scope) AND logo_asset_id IS NOT NULL
          UNION ALL SELECT 'background', background_asset_id FROM movements
            WHERE locale = (SELECT locale FROM scope) AND background_asset_id IS NOT NULL
          UNION ALL SELECT 'key-visual', key_visual_asset_id FROM sections
            WHERE locale = (SELECT locale FROM scope) AND key_visual_asset_id IS NOT NULL
          UNION ALL SELECT 'title', title_asset_id FROM sections
            WHERE locale = (SELECT locale FROM scope) AND title_asset_id IS NOT NULL
          UNION ALL SELECT 'background', background_asset_id FROM sections
            WHERE locale = (SELECT locale FROM scope) AND background_asset_id IS NOT NULL
          UNION ALL SELECT 'decoration', decoration_asset_id FROM sections
            WHERE locale = (SELECT locale FROM scope) AND decoration_asset_id IS NOT NULL
          UNION ALL SELECT 'retro-background', retro_background_asset_id FROM sections
            WHERE locale = (SELECT locale FROM scope) AND retro_background_asset_id IS NOT NULL
          UNION ALL SELECT 'divider', divider_icon_asset_id FROM movement_locations
            WHERE locale = (SELECT locale FROM scope) AND divider_icon_asset_id IS NOT NULL
          UNION ALL SELECT 'video', video_id FROM movement_locations
            WHERE locale = (SELECT locale FROM scope) AND video_id IS NOT NULL
        ), reference_counts AS (
          SELECT category, asset_id, COUNT(*) AS reference_count
          FROM presentation_references GROUP BY category, asset_id
        ), assets AS (
          SELECT category, asset_id, 'image' AS format, 'image/png' AS mime,
                 size, object_key, width, height, NULL AS duration,
                 NULL AS frame_rate, NULL AS frame_count
          FROM presentation_image_assets
          UNION ALL
          SELECT category, asset_id, 'video', mime, size, object_key,
                 width, height,
                 CAST(frame_count AS REAL) * frame_rate_denominator /
                   frame_rate_numerator,
                 CAST(frame_rate_numerator AS REAL) / frame_rate_denominator,
                 frame_count
          FROM presentation_video_assets
        )
        SELECT json_object(
          'id', assets.asset_id, 'category', assets.category,
          'format', assets.format, 'mime', assets.mime, 'size', assets.size,
          'objectKey', assets.object_key, 'width', assets.width,
          'height', assets.height, 'duration', assets.duration,
          'frameRate', assets.frame_rate, 'frameCount', assets.frame_count,
          'referenceCount', COALESCE(reference_counts.reference_count, 0)
        )
        FROM assets
        LEFT JOIN reference_counts USING (category, asset_id)
        WHERE ((SELECT category_filter FROM scope) = ''
               OR assets.category = (SELECT category_filter FROM scope))
          AND ((SELECT asset_id_filter FROM scope) = ''
               OR assets.asset_id = (SELECT asset_id_filter FROM scope))
        ORDER BY assets.category, assets.asset_id
      |}

  let presentation_reverse_references =
    (t2 string (t2 string string) ->* string)
      {|
        WITH presentation_references AS (
          SELECT movement.locale, 'movement' AS owner_type,
                 movement.movement_id AS owner_id, movement.movement_id,
                 'icon' AS role, movement.name, movement.icon_asset_id AS asset_id
          FROM movements AS movement
          UNION ALL
          SELECT movement.locale, 'movement', movement.movement_id,
                 movement.movement_id, 'logo', movement.name,
                 movement.logo_asset_id
          FROM movements AS movement
          UNION ALL
          SELECT movement.locale, 'movement', movement.movement_id,
                 movement.movement_id, 'background', movement.name,
                 movement.background_asset_id
          FROM movements AS movement
          UNION ALL
          SELECT section.locale, 'section', section.section_id,
                 location.movement_id, 'key-visual', section.name,
                 section.key_visual_asset_id
          FROM sections AS section JOIN movement_locations AS location
            ON location.locale = section.locale AND location.section_id = section.section_id
           AND location.location_type = 'story_set'
          UNION ALL
          SELECT section.locale, 'section', section.section_id,
                 location.movement_id, 'title', section.name, section.title_asset_id
          FROM sections AS section JOIN movement_locations AS location
            ON location.locale = section.locale AND location.section_id = section.section_id
           AND location.location_type = 'story_set'
          UNION ALL
          SELECT section.locale, 'section', section.section_id,
                 location.movement_id, 'background', section.name,
                 section.background_asset_id
          FROM sections AS section JOIN movement_locations AS location
            ON location.locale = section.locale AND location.section_id = section.section_id
           AND location.location_type = 'story_set'
          UNION ALL
          SELECT section.locale, 'section', section.section_id,
                 location.movement_id, 'decoration', section.name,
                 section.decoration_asset_id
          FROM sections AS section JOIN movement_locations AS location
            ON location.locale = section.locale AND location.section_id = section.section_id
           AND location.location_type = 'story_set'
          UNION ALL
          SELECT section.locale, 'section', section.section_id,
                 location.movement_id, 'retro-background', section.name,
                 section.retro_background_asset_id
          FROM sections AS section JOIN movement_locations AS location
            ON location.locale = section.locale AND location.section_id = section.section_id
           AND location.location_type = 'story_set'
          UNION ALL
          SELECT location.locale, 'movement-divider', location.location_id,
                 location.movement_id, 'divider', location.divider_sub_name,
                 location.divider_icon_asset_id
          FROM movement_locations AS location WHERE location.location_type = 'divider'
          UNION ALL
          SELECT location.locale,
                 CASE location.location_type
                   WHEN 'divider' THEN 'movement-divider'
                   WHEN 'story_set' THEN 'section'
                   ELSE 'movement'
                 END,
                 CASE location.location_type
                   WHEN 'divider' THEN location.location_id
                   WHEN 'story_set' THEN location.section_id
                   ELSE location.movement_id
                 END,
                 location.movement_id, 'video',
                 CASE location.location_type
                   WHEN 'divider' THEN location.divider_sub_name
                   WHEN 'story_set' THEN section.name
                   ELSE movement.name
                 END,
                 location.video_id
          FROM movement_locations AS location
          JOIN movements AS movement
            ON movement.locale = location.locale
           AND movement.movement_id = location.movement_id
          LEFT JOIN sections AS section
            ON section.locale = location.locale
           AND section.section_id = location.section_id
          WHERE location.video_id IS NOT NULL
        )
        SELECT json_object(
          'ownerType', owner_type, 'ownerID', owner_id,
          'movementID', movement_id,
          'role', CASE WHEN role = 'divider' THEN 'icon' ELSE role END,
          'name', COALESCE(name, '')
        )
        FROM presentation_references
        WHERE locale = ? AND role = ? AND asset_id = ?
        ORDER BY movement_id, owner_type, owner_id, role
      |}

  let search =
    (t2 string string ->* string)
      {|
        WITH input(query, locale) AS (SELECT lower(trim(?)), ?),
        matching_stories AS MATERIALIZED (
          SELECT story.locale, story.story_id
          FROM stories AS story
          CROSS JOIN input
          WHERE story.locale = input.locale
            AND instr(
            lower(COALESCE(story.info, '') || ' ' || COALESCE(story.text, '')),
            input.query
          ) > 0
        ),
        matching_story_narrative_image_assets AS MATERIALIZED (
          SELECT DISTINCT reference.locale, reference.category, reference.asset_id
          FROM matching_stories AS story
          JOIN story_narrative_image_references AS reference
            ON reference.locale = story.locale
           AND reference.story_id = story.story_id
        )
        SELECT json_object(
          'kind', entry.kind,
          'id', entry.entry_id,
          'category', entry.category,
          'title', entry.title,
          'subtitle', entry.subtitle,
          'thumbnailObjectKey', entry.thumbnail_object_key,
          'parent', CASE
            WHEN entry.parent_json IS NULL THEN NULL
            ELSE json(entry.parent_json)
          END
        )
        FROM search_entries AS entry
        CROSS JOIN input
        WHERE entry.locale = input.locale
          AND (
            instr(lower(entry.search_text), input.query) > 0
            OR (
              entry.kind = 'story'
              AND EXISTS (
                SELECT 1
                FROM matching_stories AS story
                WHERE story.locale = entry.locale
                  AND story.story_id = entry.entry_id
              )
            )
            OR (
              entry.kind = 'narrative_asset'
              AND EXISTS (
                SELECT 1
                FROM matching_story_narrative_image_assets AS narrative_image_asset
                WHERE narrative_image_asset.locale = entry.locale
                  AND narrative_image_asset.category = entry.category
                  AND narrative_image_asset.asset_id = entry.entry_id
              )
            )
          )
        ORDER BY
          CASE
            WHEN lower(entry.entry_id) = input.query
              OR (entry.kind = 'story' AND lower(entry.subtitle) = input.query)
              THEN 0
            WHEN lower(entry.title) = input.query THEN 1
            WHEN instr(lower(entry.entry_id), input.query) = 1
              OR (entry.kind = 'story'
                  AND instr(lower(entry.subtitle), input.query) = 1)
              THEN 2
            WHEN instr(lower(entry.title), input.query) = 1 THEN 3
            ELSE 4
          END,
          CASE entry.kind
            WHEN 'story' THEN 0
            WHEN 'narrative_asset' THEN 1
            WHEN 'gallery' THEN 2
            WHEN 'section' THEN 3
            WHEN 'archive_group' THEN 4
            WHEN 'movement' THEN 5
            ELSE 6
          END,
          lower(entry.title), lower(entry.entry_id), COALESCE(entry.category, '')
        LIMIT 100
      |}
end

let unavailable error = `Unavailable (Caqti_error.show error)

let idempotent_close callback =
  let task = ref None in
  fun () ->
    match !task with
    | Some value -> value
    | None ->
        let value = callback () in
        task := Some value;
        value

let sqlite_uri path =
  Uri.make ~scheme:"sqlite3" ~path
    ~query:[ ("write", [ "false" ]); ("create", [ "false" ]) ]
    ()

module Json = struct
  open Yojson.Safe.Util

  let parse raw = Yojson.Safe.from_string raw
  let string value key = value |> member key |> to_string
  let bool value key = value |> member key |> to_bool
  let int value key = value |> member key |> to_int

  let int64 value key =
    match value |> member key with
    | `Int number -> Int64.of_int number
    | `Intlit number -> Int64.of_string number
    | _ -> invalid_arg ("expected integer field " ^ key)

  let string_opt value key =
    match value |> member key with `Null -> None | json -> Some (to_string json)

  let int_opt value key =
    match value |> member key with `Null -> None | json -> Some (to_int json)

  let int64_opt value key =
    match value |> member key with
    | `Null -> None
    | `Int number -> Some (Int64.of_int number)
    | `Intlit number -> Some (Int64.of_string number)
    | _ -> invalid_arg ("expected nullable integer field " ^ key)

  let float_opt value key =
    match value |> member key with `Null -> None | json -> Some (to_float json)

  let names_value = function
    | `List values -> List.filter_map to_string_option values
    | `String raw ->
        Yojson.Safe.from_string raw |> to_list |> List.filter_map to_string_option
    | `Null -> []
    | _ -> invalid_arg "expected names array"

  let names value key = value |> member key |> names_value

  let list value key = value |> member key |> to_list
end

let decode_presentation_asset raw =
  let value = Json.parse raw in
  Model.
    {
      id = Json.string value "id";
      category = Json.string value "category";
      format = Json.string value "format";
      mime = Json.string value "mime";
      size = Json.int64 value "size";
      object_key = Json.string value "objectKey";
      width = Json.int_opt value "width";
      height = Json.int_opt value "height";
      duration = Json.float_opt value "duration";
      frame_rate = Json.float_opt value "frameRate";
      frame_count = Json.int_opt value "frameCount";
      reference_count = Json.int value "referenceCount";
    }

let decode_presentation_reverse_reference raw =
  let value = Json.parse raw in
  Model.
    {
      owner_type = Json.string value "ownerType";
      owner_id = Json.string value "ownerID";
      movement_id = Json.string value "movementID";
      role = Json.string value "role";
      name = Json.string value "name";
    }

let decode_image_reference category prefix value =
  match Json.string_opt value (prefix ^ "ID") with
  | None -> None
  | Some id ->
      let image =
        match Json.string_opt value (prefix ^ "ObjectKey") with
        | None -> None
        | Some object_key ->
            Some
              Model.
                {
                  object_key;
                  size =
                    Option.get (Json.int64_opt value (prefix ^ "ByteSize"));
                  width = Option.get (Json.int_opt value (prefix ^ "Width"));
                  height = Option.get (Json.int_opt value (prefix ^ "Height"));
                }
      in
      Some Model.{ id; category; image }

let decode_video_reference value =
  match Json.string_opt value "videoID" with
  | None -> None
  | Some id ->
      let video =
        match Json.string_opt value "videoObjectKey" with
        | None -> None
        | Some object_key ->
            let numerator = Json.int value "videoRateNumerator" in
            let denominator = Json.int value "videoRateDenominator" in
            Some
              Model.
                {
                  object_key;
                  size = Json.int64 value "videoByteSize";
                  width = Json.int value "videoWidth";
                  height = Json.int value "videoHeight";
                  frame_rate =
                    Float.of_int numerator /. Float.of_int denominator;
                  frame_count = Json.int value "videoFrameCount";
                }
      in
      Some Model.{ id; category = "video"; video }

let decode_movement raw =
  let value = Json.parse raw in
  Model.
    {
      id = Json.string value "id";
      name = Json.string value "name";
      movement_type = Json.string value "type";
      position = Json.int value "position";
      section_count = Json.int value "sectionCount";
      start_time = Json.int64 value "startTime";
      icon = decode_image_reference "icon" "icon" value;
      logo = decode_image_reference "logo" "logo" value;
      background = decode_image_reference "background" "background" value;
      background_video = decode_video_reference value;
    }

let decode_story_narrative_media_reference value =
  Model.
    {
      asset_id = Json.string value "id";
      kind = Json.string value "kind";
      mime = Json.string_opt value "contentType";
      size = Json.int64_opt value "byteSize";
      object_key = Json.string_opt value "objectKey";
    }

let decode_section raw =
  let value = Json.parse raw in
  let section =
    Model.
      {
        id = Json.string value "id";
        name = Json.string value "name";
        description = Json.string value "description";
        section_type = Json.string value "type";
        position = Json.int value "position";
        sort_by_year = Json.int value "sortByYear";
        sort_within_year = Json.int value "sortWithinYear";
        key_visual = decode_image_reference "key-visual" "keyVisual" value;
        title_image = decode_image_reference "title" "title" value;
        background = decode_image_reference "background" "background" value;
        decoration = decode_image_reference "decoration" "decoration" value;
        retro_background =
          decode_image_reference "retro-background" "retroBackground" value;
        story_count = Json.int value "storyCount";
        opening_media_references =
          Json.list value "openingMedia"
          |> List.map decode_story_narrative_media_reference;
      }
  in
  (section, Json.string value "collectionID", decode_video_reference value)

let decode_divider raw =
  let value = Json.parse raw in
  Model.
    {
      id = Json.string value "id";
      position = Json.int value "position";
      sub_name = Json.string value "subName";
      icon = decode_image_reference "divider" "icon" value;
      video = decode_video_reference value;
    }

let decode_story_value value =
  Model.
    {
      id = Json.string value "id";
      tag = Json.string value "tag";
      tag_text = Json.string value "tagText";
      code = Json.string value "code";
      name = Json.string value "name";
      info = Json.string value "info";
      text = Json.string_opt value "text" |> Option.value ~default:"";
      media_references = [];
      narrative_image_asset_references = [];
    }

let decode_story raw = decode_story_value (Json.parse raw)

let decode_story_detail raw =
  let value = Json.parse raw in
  let story = decode_story_value value in
  {
    story with
    media_references =
      Json.list value "media"
      |> List.map decode_story_narrative_media_reference;
  }

let decode_story_reference raw =
  let value = Json.parse raw in
  ( Json.string value "storyID",
    Model.
      {
        asset_id = Json.string value "artworkID";
        kind = Json.string value "kind";
        category = Json.string value "category";
        is_anime_kv = Json.bool value "isAnimeKV";
        title = Json.string_opt value "title";
        subtitle = Json.string_opt value "subtitle";
        names = Json.names value "names";
        asset_object_key = Json.string_opt value "objectKey";
      } )

let preview_references references =
  let available =
    references
    |> List.filter (fun (reference : Model.story_narrative_image_reference) ->
        Option.is_some reference.asset_object_key
        && (String.equal reference.category "illustration"
           || String.equal reference.category "background"))
    |> unique_story_narrative_image_references
  in
  let images =
    List.filter
      (fun (reference : Model.story_narrative_image_reference) ->
        String.equal reference.category "illustration")
      available
  in
  (match images with [] -> available | values -> values) |> List.take 3

let story_data story_raws reference_raws =
  let stories = List.map decode_story story_raws in
  let references = List.map decode_story_reference reference_raws in
  let for_story id =
    references
    |> List.filter_map (fun (story_id, reference) ->
        if String.equal story_id id then Some reference else None)
  in
  let summaries =
    List.map
      (fun (story : Model.story) ->
        let preview_narrative_image_asset_references = for_story story.id |> preview_references in
        Model.
          {
            story;
            representative_narrative_image_asset_reference =
              representative_story_narrative_image_reference preview_narrative_image_asset_references;
            preview_narrative_image_asset_references;
          })
      stories
  in
  let all_references = references |> List.map snd in
  (stories, summaries, all_references)

let decode_parent value =
  match Json.string value "parentKind" with
  | "section" ->
      Model.Score_parent
        {
          movement_id = Json.string value "movementID";
          movement_name = Json.string value "movementName";
          section_id = Json.string value "sectionID";
          section_name = Json.string value "sectionName";
        }
  | "archive_group" ->
      Model.Archive_parent
        {
          archive_category =
            Json.string value "archiveCategory" |> archive_route_of_category;
          group_id = Json.string value "groupID";
          group_name = Json.string value "groupName";
        }
  | kind -> invalid_arg ("unknown collection parent: " ^ kind)

let decode_search_result raw =
  let value = Json.parse raw in
  let parent =
    match Yojson.Safe.Util.member "parent" value with
    | `Null -> None
    | parent -> Some (decode_parent parent)
  in
  Model.
    {
      kind = Json.string value "kind";
      id = Json.string value "id";
      category = Json.string_opt value "category";
      title = Json.string value "title";
      subtitle = Json.string_opt value "subtitle";
      thumbnail_object_key = Json.string_opt value "thumbnailObjectKey";
      parent;
    }

let decode_archive_group raw =
  let value = Json.parse raw in
  let archive_category = Json.string value "archiveCategory" in
  let group_type =
    Json.string_opt value "storyType" |> Option.value ~default:archive_category
  in
  ( Model.
      {
        id = Json.string value "id";
        name = Json.string value "name";
        category = archive_route_of_category archive_category;
        group_type;
      },
    Json.string value "collectionID" )

type gallery_base = {
  id : string;
  name : string;
  description : string;
  parent : Model.collection_parent;
}

let decode_gallery_base raw =
  let value = Json.parse raw in
  {
    id = Json.string value "id";
    name = Json.string value "name";
    description = Json.string value "description";
    parent = decode_parent value;
  }

let decode_gallery_reference raw =
  let value = Json.parse raw in
  ( Json.string value "groupID",
    Model.
      {
        position = Json.int value "position";
        cg_id = Json.string value "cgID";
        asset_id = Json.string value "artworkID";
        category = Json.string value "category";
        asset_object_key = Json.string_opt value "objectKey";
      } )

let decode_gallery base_raw group_raws reference_raws =
  let base = decode_gallery_base base_raw in
  let references = List.map decode_gallery_reference reference_raws in
  let groups =
    List.map
      (fun raw ->
        let value = Json.parse raw in
        let id = Json.string value "id" in
        Model.
          {
            id;
            position = Json.int value "position";
            name = Json.string value "name";
            description = Json.string value "description";
            related_story_id = Json.string_opt value "relatedStoryID";
            related_stage_id = Json.string_opt value "relatedStageID";
            references =
              references
              |> List.filter_map (fun (group_id, narrative_image_asset) ->
                  if String.equal id group_id then Some narrative_image_asset else None);
          })
      group_raws
  in
  Model.
    {
      id = base.id;
      name = base.name;
      description = base.description;
      parent = base.parent;
      groups;
    }

let decode_error label exception_ =
  `Unavailable (Printf.sprintf "cannot decode %s: %s" label (Printexc.to_string exception_))

let decode_result label callback =
  try Ok (callback ()) with exception_ -> Error (decode_error label exception_)

let sqlite_with_pool_observer ~on_acquire path =
  let pool_config = Caqti_pool_config.create ~max_size:10 () in
  match Caqti_lwt_unix.connect_pool ~pool_config (sqlite_uri path) with
  | Error error -> Error (Caqti_error.show error)
  | Ok pool ->
      let use callback =
        Caqti_lwt_unix.Pool.use
          (fun connection ->
            on_acquire ();
            callback connection)
          pool
        >|= function
        | Ok value -> Ok value
        | Error error -> Error (unavailable error)
      in
      let health () =
        use (fun (module Db) -> Db.find Query.ping ()) >|= function
        | Ok 1 -> Ok ()
        | Ok _ -> Error (`Unavailable "required SQLite schema is unavailable")
        | Error error -> Error error
      in
      let check () =
        use (fun (module Db) -> Db.find Query.schema_version ()) >>= function
        | Error error -> Lwt.return (Error error)
        | Ok version when version <> 2 ->
            Lwt.return
              (Error
                 (`Unavailable
                   (Printf.sprintf "unsupported SQLite schema version %d" version)))
        | Ok _ -> health ()
      in
      let sitemap_data () =
        use (fun (module Db) ->
            Db.collect_list Query.sitemap_movements () >>= function
            | Error error -> Lwt.return (Error error)
            | Ok movements ->
                Db.collect_list Query.sitemap_sections ()
                >>= ( function
                | Error error -> Lwt.return (Error error)
                | Ok sections ->
                    Db.collect_list Query.sitemap_archive_groups ()
                    >>= ( function
                    | Error error -> Lwt.return (Error error)
                    | Ok archive_groups ->
                        Db.collect_list Query.sitemap_galleries ()
                        >|= Result.map (fun galleries ->
                                ( movements,
                                  sections,
                                  archive_groups,
                                  galleries )) ) ))
        >|= Result.map (fun (movements, sections, archives, galleries) ->
                {
                  movements;
                  sections =
                    List.map
                      (fun (locale, (movement_id, section_id)) ->
                        (locale, movement_id, section_id))
                      sections;
                  archive_groups =
                    List.map
                      (fun (locale, (kind, id)) -> (locale, kind, id))
                      archives;
                  galleries;
                })
      in
      let narrative_image_asset category id =
        use (fun (module Db) -> Db.collect_list Query.narrative_image_asset (category, id))
        >|= function
        | Error error -> Error error
        | Ok [] -> Error `Not_found
        | Ok
            ((category, (object_key, (size, (width, (height, _))))) :: _ as
             rows) ->
            let material_assets =
              rows
              |> List.filter_map
                   (fun (_, (_, (_, (_, (_, (material_category, source_id)))))) ->
                     match (material_category, source_id) with
                     | Some category, Some id ->
                         Some
                           (Model.{ namespace = "material"; id; category } :
                              Model.asset_reference)
                     | _ -> None)
            in
            Ok
              Model.
                {
                  id;
                  category;
                  image = { object_key; size; width; height };
                  material_assets;
                }
      in
      let material_asset category id =
        use (fun (module Db) ->
            Db.find_opt Query.material_asset (category, id) >>= function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Ok None)
            | Ok (Some material) ->
                Db.collect_list Query.material_asset_uses (category, id)
                >|= Result.map (fun narrative_image_asset_references -> Some (material, narrative_image_asset_references)))
        >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok
            (Some
               ( ( kind,
                   ( category,
                     ( character_id,
                       ( role,
                         ( variant,
                           (object_key, (size, (width, height))) ) ) ) ) ),
                 narrative_image_asset_references )) ->
            Ok
              Model.
                {
                  id;
                  category;
                  kind;
                  character_id;
                  role;
                  variant;
                  image = { object_key; size; width; height };
                  narrative_image_asset_references =
                    List.map
                      (fun (category, id) ->
                        (Model.{ namespace = "narrative"; category; id } :
                           Model.asset_reference))
                      narrative_image_asset_references;
                }
      in
      let narrative_media_asset kind id =
        use (fun (module Db) ->
            Db.find_opt Query.narrative_media_asset (kind, id))
        >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok (Some raw) ->
            decode_result "Narrative Media Asset" (fun () ->
                let value = Json.parse raw in
                Model.
                  {
                    id = Json.string value "id";
                    kind = Json.string value "kind";
                    object_key = Json.string value "objectKey";
                    mime = Json.string value "contentType";
                    size = Json.int64 value "byteSize";
                    duration = Json.float_opt value "duration";
                    sample_rate = Json.int_opt value "sampleRate";
                    width = Json.int_opt value "width";
                    height = Json.int_opt value "height";
                    frame_rate = Json.float_opt value "frameRate";
                    frame_count = Json.int_opt value "frameCount";
                  })
      in
      let orphan_narrative_image_assets locale =
        use (fun (module Db) -> Db.collect_list Query.orphan_narrative_image_assets locale)
        >|= Result.map (fun rows ->
                List.map
                  (fun
                    ( category,
                      (id, (asset_object_key, (size, (width, height)))) ) ->
                    Model.{ id; category; asset_object_key; size; width; height })
                  rows)
      in
      let orphan_narrative_media_assets locale =
        use (fun (module Db) -> Db.collect_list Query.orphan_narrative_media_assets locale)
        >|= Result.map (fun rows ->
                List.map
                  (fun (kind, (id, (mime, (size, object_key)))) ->
                    Model.{ id; kind; object_key; mime; size })
                  rows)
      in
      let narrative_image_asset_reverse_references locale category id =
        use (fun (module Db) ->
            Db.find_opt Query.narrative_image_asset_reverse_references_exists (category, id) >>= function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Ok None)
            | Ok (Some _) ->
                Db.collect_list Query.narrative_image_asset_reverse_references_occurrences
                  (locale, (category, id))
                >>= ( function
                | Error error -> Lwt.return (Error error)
                | Ok occurrences ->
                    (if String.equal category "character" then
                       let prefix = character_prefix id in
                       Db.collect_list Query.narrative_image_asset_reverse_references_character_variants
                         (locale, (id, (prefix, (prefix, prefix))))
                     else Lwt.return (Ok []))
                    >>= ( function
                    | Error error -> Lwt.return (Error error)
                    | Ok character_variants ->
                        Db.collect_list Query.narrative_image_asset_reverse_references_textures (id, id)
                        >>= ( function
                        | Error error -> Lwt.return (Error error)
                        | Ok textures ->
                            Db.collect_list Query.narrative_image_asset_reverse_references_galleries
                              (locale, (category, id))
                            >|= Result.map (fun galleries ->
                                    Some
                                      ( occurrences,
                                        character_variants,
                                        textures,
                                        galleries )) ) ) ))
        >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok
            (Some
              ( occurrence_raws,
                variant_raws,
                texture_rows,
                gallery_raws )) ->
            decode_result "Narrative Image Asset Reverse References" (fun () ->
                let occurrence_values = List.map Json.parse occurrence_raws in
                let names =
                  occurrence_values
                  |> List.concat_map (fun value -> Json.names value "names")
                  |> unique_strings
                in
                let seen_stories = Hashtbl.create (List.length occurrence_values) in
                let occurrences =
                  occurrence_values
                  |> List.filter_map (fun value ->
                         let story_id = Json.string value "storyID" in
                         if Hashtbl.mem seen_stories story_id then None
                         else (
                           Hashtbl.add seen_stories story_id ();
                           Some
                             Model.
                               {
                                 parent = decode_parent value;
                                 story_id;
                                 story_name = Json.string value "storyName";
                                 story_code = Json.string value "storyCode";
                                 story_tag_text =
                                   Json.string value "storyTagText";
                               }))
                in
                let rec decode_character_variants values = function
                  | [] -> List.rev values
                  | raw :: rest ->
                      let value = Json.parse raw in
                      let asset_id = Json.string value "artworkID" in
                      let object_key = Json.string value "objectKey" in
                      let rec gather names = function
                        | next :: tail ->
                            let next_value = Json.parse next in
                            if String.equal asset_id (Json.string next_value "artworkID")
                            then
                              gather
                                (Json.names next_value "names" @ names)
                                tail
                            else (names, next :: tail)
                        | [] -> (names, [])
                      in
                      let variant_names, remaining =
                        gather (Json.names value "names") rest
                      in
                      decode_character_variants
                        (Model.
                           {
                             asset_id;
                             names = unique_strings variant_names;
                             asset_object_key = object_key;
                           }
                        :: values)
                        remaining
                in
                Model.
                  {
                    names;
                    character_variants = decode_character_variants [] variant_raws;
                    textures =
                      List.map
                        (fun (asset_id, asset_object_key) ->
                          Model.
                            { asset_id; names = []; asset_object_key })
                        texture_rows;
                    occurrences;
                    galleries =
                      List.map
                        (fun raw ->
                          let value = Json.parse raw in
                          Model.
                            {
                              gallery_id = Json.string value "galleryID";
                              gallery_name = Json.string value "galleryName";
                              gallery_description =
                                Json.string value "galleryDescription";
                              group_id = Json.string value "groupID";
                              group_name = Json.string value "groupName";
                              group_description =
                                Json.string value "groupDescription";
                              cg_id = Json.string value "cgID";
                            })
                        gallery_raws;
                  })
      in
      let narrative_media_asset_reverse_references locale kind id =
        use (fun (module Db) ->
            Db.find_opt Query.narrative_media_asset_reverse_references_exists (kind, id) >>= function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Ok None)
            | Ok (Some _) ->
                Db.collect_list Query.narrative_media_asset_reverse_references_occurrences
                  (locale, (kind, id))
                >>= function
                | Error error -> Lwt.return (Error error)
                | Ok occurrences ->
                    Db.collect_list Query.narrative_media_asset_reverse_references_sections
                      (locale, (kind, id))
                    >>= function
                    | Error error -> Lwt.return (Error error)
                    | Ok sections ->
                        Db.collect_list Query.narrative_media_asset_reverse_references_archives
                          (locale, (kind, id))
                        >|= Result.map (fun archives ->
                                Some (occurrences, sections @ archives)))
        >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok (Some (occurrence_raws, collection_raws)) ->
            decode_result "Media Reverse References" (fun () ->
                let seen_stories = Hashtbl.create (List.length occurrence_raws) in
                let occurrences =
                  occurrence_raws
                  |> List.filter_map (fun raw ->
                         let value = Json.parse raw in
                         let story_id = Json.string value "storyID" in
                         if Hashtbl.mem seen_stories story_id then None
                         else (
                           Hashtbl.add seen_stories story_id ();
                           Some
                             Model.
                               {
                                 parent = decode_parent value;
                                 story_id;
                                 story_name = Json.string value "storyName";
                                 story_code = Json.string value "storyCode";
                                 story_tag_text =
                                   Json.string value "storyTagText";
                               }))
                in
                Model.
                  {
                    occurrences;
                    collections =
                      List.map (fun raw -> decode_parent (Json.parse raw))
                        collection_raws;
                  })
      in
      let movements locale =
        use (fun (module Db) -> Db.collect_list Query.movements locale)
        >|= function
        | Error error -> Error error
        | Ok raws -> decode_result "movements" (fun () -> List.map decode_movement raws)
      in
      let movement locale id =
        movements locale >>= function
        | Error error -> Lwt.return (Error error)
        | Ok values -> (
            match
              List.find_opt
                (fun (movement : Model.movement) -> String.equal movement.id id)
                values
            with
            | None -> Lwt.return (Error `Not_found)
            | Some selected ->
                use (fun (module Db) ->
                    Db.collect_list Query.sections_by_movement (locale, id)
                    >>= ( function
                    | Error error -> Lwt.return (Error error)
                    | Ok sections ->
                        Db.collect_list Query.movement_dividers (locale, id)
                        >|= Result.map (fun dividers -> (sections, dividers)) ))
                >|= function
                | Error error -> Error error
                | Ok (section_raws, divider_raws) ->
                    decode_result "movement" (fun () ->
                        let section_items =
                          section_raws
                          |> List.map (fun raw ->
                                 let section, _, _ = decode_section raw in
                                 Model.Section
                                   { position = section.position; section })
                        in
                        let divider_items =
                          divider_raws
                          |> List.map (fun raw ->
                                 Model.Divider (decode_divider raw))
                        in
                        let position = function
                          | Model.Divider divider -> divider.position
                          | Model.Section { position; _ } -> position
                        in
                        Model.
                          {
                            movement = selected;
                            items =
                              List.sort
                                (fun left right ->
                                  Int.compare (position left) (position right))
                                (section_items @ divider_items);
                          }))
      in
      let gallery locale id =
        use (fun (module Db) ->
            Db.find_opt Query.gallery_base (locale, id) >>= function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Ok None)
            | Ok (Some base) ->
                Db.collect_list Query.gallery_groups (locale, id)
                >>= ( function
                | Error error -> Lwt.return (Error error)
                | Ok groups ->
                    Db.collect_list Query.gallery_references (locale, id)
                    >|= Result.map (fun references -> Some (base, groups, references)) ))
        >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok (Some (base, groups, references)) ->
            decode_result "gallery" (fun () ->
                decode_gallery base groups references)
      in
      let search locale query =
        let query = String.trim query in
        if String.equal query "" then Lwt.return (Ok [])
        else
          use (fun (module Db) ->
              Db.collect_list Query.search (query, locale))
          >|= function
          | Error error -> Error error
          | Ok raws -> decode_result "search results" (fun () -> List.map decode_search_result raws)
      in
      let presentation_assets locale =
        use (fun (module Db) ->
            Db.collect_list Query.presentation_assets (locale, "", ""))
        >|= function
        | Error error -> Error error
        | Ok raws ->
            decode_result "presentation assets" (fun () ->
                List.map decode_presentation_asset raws)
      in
      let presentation_asset locale category id =
        use (fun (module Db) ->
            Db.collect_list Query.presentation_assets (locale, category, id))
        >>= function
        | Error error -> Lwt.return (Error error)
        | Ok [] -> Lwt.return (Error `Not_found)
        | Ok (raw :: _) ->
            (match decode_result "presentation asset" (fun () -> decode_presentation_asset raw) with
            | Error error -> Lwt.return (Error error)
            | Ok asset ->
                use (fun (module Db) ->
                    Db.collect_list Query.presentation_reverse_references
                      (locale, (category, id)))
                >|= function
                | Error error -> Error error
                | Ok raws ->
                    decode_result "presentation reverse references" (fun () ->
                        Model.
                          {
                            asset;
                            reverse_references =
                              List.map
                                decode_presentation_reverse_reference raws;
                          }))
      in
      let gallery_by_collection locale collection_id =
        use (fun (module Db) ->
            Db.find_opt Query.gallery_by_collection (locale, collection_id))
        >>= function
        | Error error -> Lwt.return (Error error)
        | Ok None -> Lwt.return (Ok None)
        | Ok (Some id) ->
            gallery locale id >|= Result.map (fun value -> Some value)
      in
      let galleries locale =
        use (fun (module Db) ->
            Db.collect_list Query.gallery_bases locale >>= function
            | Error error -> Lwt.return (Error error)
            | Ok bases ->
                Db.collect_list Query.gallery_previews (locale, locale)
                >|= Result.map (fun previews -> (bases, previews)))
        >|= function
        | Error error -> Error error
        | Ok (base_raws, preview_rows) ->
            decode_result "gallery summaries" (fun () ->
                List.map
                  (fun raw ->
                    let base = decode_gallery_base raw in
                    let preview_asset_object_keys =
                      preview_rows
                      |> List.filter_map (fun (gallery_id, object_key) ->
                             if String.equal base.id gallery_id then object_key
                             else None)
                      |> unique_strings |> List.take 3
                    in
                    Model.
                      {
                        gallery =
                          {
                            id = base.id;
                            name = base.name;
                            description = base.description;
                            parent = base.parent;
                            groups = [];
                          };
                        preview_asset_object_keys;
                      })
                  base_raws)
      in
      let section locale movement_id section_id =
        use (fun (module Db) ->
            Db.find_opt Query.section (locale, (movement_id, section_id))
            >>= function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Ok None)
            | Ok (Some section_raw) ->
                let _, collection_id, _ = decode_section section_raw in
                Db.collect_list Query.collection_stories (locale, collection_id)
                >>= function
                | Error error -> Lwt.return (Error error)
                | Ok stories ->
                    Db.collect_list Query.collection_story_references
                      (locale, collection_id)
                    >>= function
                    | Error error -> Lwt.return (Error error)
                    | Ok references ->
                        Db.collect_list Query.collection_story_narrative_media_references
                          (locale, collection_id)
                        >|= Result.map (fun media ->
                                Some
                                  ( section_raw,
                                    collection_id,
                                    stories,
                                    references,
                                    media )))
        >>= function
        | Error error -> Lwt.return (Error error)
        | Ok None -> Lwt.return (Error `Not_found)
        | Ok
            (Some
              ( section_raw,
                collection_id,
                story_raws,
                reference_raws,
                media_raws )) ->
            gallery_by_collection locale collection_id >|= ( function
            | Error error -> Error error
            | Ok gallery ->
                decode_result "Section" (fun () ->
                    let section, _, active_background_video =
                      decode_section section_raw
                    in
                    let _, stories, narrative_image_asset_references =
                      story_data story_raws reference_raws
                    in
                    Model.
                      {
                        section;
                        active_background_video;
                        stories;
                        media_references =
                          media_raws
                          |> List.map (fun raw ->
                                 decode_story_narrative_media_reference (Json.parse raw))
                          |> unique_story_narrative_media_references;
                        narrative_image_asset_references =
                          unique_story_narrative_image_references narrative_image_asset_references;
                        gallery;
                      }) )
      in
      let story_detail_for_collection locale collection_id parent story_id =
        use (fun (module Db) ->
            Db.find_opt Query.story_detail
              (locale, (collection_id, story_id))
            >>= function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Ok None)
            | Ok (Some story) ->
                Db.collect_list Query.story_references (locale, story_id)
                >|= Result.map (fun references -> Some (story, references)))
        >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok (Some (story_raw, reference_raws)) ->
            decode_result "story" (fun () ->
                let story = decode_story_detail story_raw in
                let references =
                  List.map decode_story_reference reference_raws
                  |> List.filter_map (fun (candidate, reference) ->
                         if String.equal candidate story_id then Some reference
                         else None)
                in
                Some
                  Model.
                    {
                      story = { story with narrative_image_asset_references = references };
                      parent;
                    })
            |> (function
                 | Ok (Some detail) -> Ok detail
                 | Ok None -> Error `Not_found
                 | Error error -> Error error)
      in
      let score_story locale movement_id section_id story_id =
        movements locale >>= function
        | Error error -> Lwt.return (Error error)
        | Ok movement_values -> (
            match
              List.find_opt
                (fun (movement : Model.movement) ->
                  String.equal movement.id movement_id)
                movement_values
            with
            | None -> Lwt.return (Error `Not_found)
            | Some selected_movement ->
                use (fun (module Db) ->
                    Db.find_opt Query.section
                      (locale, (movement_id, section_id)))
                >>= ( function
                | Error error -> Lwt.return (Error error)
                | Ok None -> Lwt.return (Error `Not_found)
                | Ok (Some raw) ->
                    let section, collection_id, _ = decode_section raw in
                    let parent =
                      Model.Score_parent
                        {
                          movement_id;
                          movement_name = selected_movement.name;
                          section_id;
                          section_name = section.name;
                        }
                    in
                    story_detail_for_collection locale collection_id parent
                      story_id ))
      in
      let archive_index locale =
        use (fun (module Db) -> Db.collect_list Query.archive_index locale)
        >|= Result.map (fun rows ->
                List.map
                  (fun (category, group_count) ->
                    Model.
                      {
                        category = archive_route_of_category category;
                        group_count;
                      })
                  rows)
      in
      let archive_groups locale route_category =
        match archive_category_of_route route_category with
        | None -> Lwt.return (Error `Not_found)
        | Some archive_category ->
            use (fun (module Db) ->
                Db.collect_list Query.archive_groups (locale, archive_category)
                >>= function
                | Error error -> Lwt.return (Error error)
                | Ok groups ->
                    Db.collect_list Query.archive_group_references
                      (locale, archive_category)
                    >|= Result.map (fun references -> (groups, references)))
            >|= function
            | Error error -> Error error
            | Ok (group_raws, reference_raws) ->
                decode_result "archive group summaries" (fun () ->
                    let references =
                      reference_raws
                      |> List.map (fun raw ->
                             let value = Json.parse raw in
                             ( Json.string value "groupID",
                               snd (decode_story_reference raw) ))
                    in
                    List.map
                      (fun raw ->
                        let group, _ = decode_archive_group raw in
                        let preview_narrative_image_asset_references =
                          references
                          |> List.filter_map (fun (group_id, reference) ->
                                 if String.equal group.id group_id then
                                   Some reference
                                 else None)
                          |> preview_references
                        in
                        Model.
                          {
                            group;
                            representative_narrative_image_asset_reference =
                              representative_story_narrative_image_reference
                                preview_narrative_image_asset_references;
                            preview_narrative_image_asset_references;
                          })
                      group_raws)
      in
      let archive_group locale route_category id =
        match archive_category_of_route route_category with
        | None -> Lwt.return (Error `Not_found)
        | Some archive_category ->
            use (fun (module Db) ->
                Db.find_opt Query.archive_group (locale, (archive_category, id))
                >>= function
                | Error error -> Lwt.return (Error error)
                | Ok None -> Lwt.return (Ok None)
                | Ok (Some group_raw) ->
                    let _, collection_id = decode_archive_group group_raw in
                    Db.collect_list Query.collection_stories
                      (locale, collection_id)
                    >>= function
                    | Error error -> Lwt.return (Error error)
                    | Ok stories ->
                        Db.collect_list Query.collection_story_references
                          (locale, collection_id)
                        >>= function
                        | Error error -> Lwt.return (Error error)
                        | Ok references ->
                            Db.collect_list Query.collection_story_narrative_media_references
                              (locale, collection_id)
                            >>= function
                            | Error error -> Lwt.return (Error error)
                            | Ok media ->
                                Db.collect_list Query.archive_entry_media
                                  (locale, (id, id))
                                >|= Result.map (fun opening_media ->
                                        Some
                                          ( group_raw,
                                            collection_id,
                                            stories,
                                            references,
                                            media,
                                            opening_media )) )
            >>= ( function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Error `Not_found)
            | Ok
                (Some
                  ( group_raw,
                    collection_id,
                    story_raws,
                    reference_raws,
                    media_raws,
                    opening_media_raws )) ->
                gallery_by_collection locale collection_id >|= ( function
                | Error error -> Error error
                | Ok gallery ->
                    decode_result "archive group" (fun () ->
                        let group, _ = decode_archive_group group_raw in
                        let _, stories, narrative_image_asset_references =
                          story_data story_raws reference_raws
                        in
                        let narrative_image_asset_references =
                          unique_story_narrative_image_references narrative_image_asset_references
                        in
                        let preview_narrative_image_asset_references =
                          preview_references narrative_image_asset_references
                        in
                        Model.
                          {
                            group;
                            stories;
                            representative_narrative_image_asset_reference =
                              representative_story_narrative_image_reference
                                preview_narrative_image_asset_references;
                            preview_narrative_image_asset_references;
                            media_references =
                              media_raws
                              |> List.map (fun raw ->
                                     decode_story_narrative_media_reference (Json.parse raw))
                              |> unique_story_narrative_media_references;
                            narrative_image_asset_references;
                            opening_media_references =
                              List.map
                                (fun raw ->
                                  decode_story_narrative_media_reference (Json.parse raw))
                                opening_media_raws;
                            gallery;
                          }) ) )
      in
      let archive_story locale route_category group_id story_id =
        match archive_category_of_route route_category with
        | None -> Lwt.return (Error `Not_found)
        | Some archive_category ->
            use (fun (module Db) ->
                Db.find_opt Query.archive_group
                  (locale, (archive_category, group_id)))
            >>= ( function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Error `Not_found)
            | Ok (Some raw) ->
                let group, collection_id = decode_archive_group raw in
                let parent =
                  Model.Archive_parent
                    {
                      archive_category = group.category;
                      group_id = group.id;
                      group_name = group.name;
                    }
                in
                story_detail_for_collection locale collection_id parent story_id )
      in
      Ok
        {
          close = idempotent_close (fun () -> Caqti_lwt_unix.Pool.drain pool);
          check;
          health;
          sitemap_data;
          narrative_image_asset;
          material_asset;
          narrative_media_asset;
          orphan_narrative_image_assets;
          orphan_narrative_media_assets;
          narrative_image_asset_reverse_references;
          narrative_media_asset_reverse_references;
          movements;
          movement;
          section;
          score_story;
          archive_index;
          archive_groups;
          archive_group;
          archive_story;
          galleries;
          gallery;
          presentation_assets;
          presentation_asset;
          search;
        }

let sqlite path = sqlite_with_pool_observer ~on_acquire:(fun () -> ()) path
let remove_if_exists path = try Sys.remove path with Sys_error _ -> ()

let rec make_directory path =
  if Sys.file_exists path then ()
  else
    let parent = Filename.dirname path in
    if String.equal parent path then
      raise (Sys_error ("cannot create database cache directory: " ^ path))
    else (
      make_directory parent;
      Unix.mkdir path 0o750)

let clean_database_cache path =
  Sys.readdir path
  |> Array.iter (fun name ->
         if
           String.starts_with ~prefix:"arkwaifu-" name
           && (String.ends_with ~suffix:".sqlite3" name
              || String.ends_with ~suffix:".sqlite3.part" name)
         then remove_if_exists (Filename.concat path name))

type generation = { database : t; path : string }

type fetch_result =
  [ `Not_modified | `Fetched of string option | `Failed of string ]

let http_fetch ~url ~etag ~destination =
  let headers =
    match etag with
    | None -> Cohttp.Header.init ()
    | Some value -> Cohttp.Header.init_with "if-none-match" value
  in
  Cohttp_lwt_unix.Client.get ~headers url >>= fun (response, body) ->
  match Cohttp.Response.status response with
  | `Not_modified -> Cohttp_lwt.Body.drain_body body >|= fun () -> `Not_modified
  | `OK ->
      Lwt_io.with_file ~mode:Lwt_io.Output destination (fun channel ->
          Cohttp_lwt.Body.to_stream body
          |> Lwt_stream.iter_s (Lwt_io.write channel))
      >|= fun () ->
      `Fetched (Cohttp.Header.get (Cohttp.Response.headers response) "etag")
  | status ->
      Cohttp_lwt.Body.drain_body body >|= fun () ->
      `Failed
        (Printf.sprintf "database download returned HTTP %s"
           (Cohttp.Code.string_of_status status))

let download_generation ~fetch ~cache_dir ~counter ~etag ~timeout_seconds =
  let name = Printf.sprintf "arkwaifu-%d-%d.sqlite3" (Unix.getpid ()) counter in
  let path = Filename.concat cache_dir name in
  let part = path ^ ".part" in
  let candidate = ref None in
  let cleanup message =
    let close =
      match !candidate with
      | None -> Lwt.return_unit
      | Some database ->
          candidate := None;
          database.close ()
    in
    close >|= fun () ->
    remove_if_exists part;
    remove_if_exists path;
    `Failed message
  in
  let download () =
    fetch ~etag ~destination:part >>= function
    | `Not_modified -> Lwt.return `Not_modified
    | `Failed error -> cleanup error
    | `Fetched response_etag -> (
        Sys.rename part path;
        match sqlite path with
        | Error error -> cleanup ("cannot open downloaded database: " ^ error)
        | Ok database -> (
            candidate := Some database;
            database.check () >>= function
            | Error (`Unavailable error) -> cleanup error
            | Error `Not_found -> cleanup "database health check failed"
            | Ok () ->
                candidate := None;
                Lwt.return (`Fetched ({ database; path }, response_etag))))
  in
  Lwt.catch
    (fun () -> Lwt_unix.with_timeout timeout_seconds download)
    (function
      | Lwt_unix.Timeout ->
          cleanup
            (Printf.sprintf "database download timed out after %.0f seconds"
               timeout_seconds)
      | exception_ -> cleanup (Printexc.to_string exception_))

type live_state = {
  current : generation ref;
  etag : string option ref;
  counter : int ref;
  mutable closed : bool;
  refresh_lock : Lwt_mutex.t;
}

let retire generation =
  generation.database.close () >|= fun () -> remove_if_exists generation.path

let refresh_once ~fetch ~cache_dir ~download_timeout_seconds state =
  Lwt_mutex.with_lock state.refresh_lock (fun () ->
      if state.closed then Lwt.return (`Failed "database is closed")
      else
        let next = !(state.counter) in
        incr state.counter;
        download_generation ~fetch ~cache_dir ~counter:next ~etag:!(state.etag)
          ~timeout_seconds:download_timeout_seconds
        >>= function
        | `Not_modified -> Lwt.return `Not_modified
        | `Failed error -> Lwt.return (`Failed error)
        | `Fetched (fresh, fresh_etag) ->
            if state.closed then
              retire fresh >|= fun () -> `Failed "database is closed"
            else
              let previous = !(state.current) in
              state.current := fresh;
              state.etag := fresh_etag;
              retire previous >|= fun () -> `Replaced)

let start_live ~fetch ~cache_dir ~download_timeout_seconds =
  try
    make_directory cache_dir;
    clean_database_cache cache_dir;
    download_generation ~fetch ~cache_dir ~counter:0 ~etag:None
      ~timeout_seconds:download_timeout_seconds
    >>= function
    | `Not_modified ->
        Lwt.return (Error "database was not downloaded at startup")
    | `Failed error -> Lwt.return (Error error)
    | `Fetched (first, first_etag) ->
        let state =
          {
            current = ref first;
            etag = ref first_etag;
            counter = ref 1;
            closed = false;
            refresh_lock = Lwt_mutex.create ();
          }
        in
        let with_current callback = callback !(state.current).database in
        let close_task = ref None in
        let close () =
          match !close_task with
          | Some task -> task
          | None ->
              state.closed <- true;
              let task =
                Lwt_mutex.with_lock state.refresh_lock (fun () ->
                    retire !(state.current))
              in
              close_task := Some task;
              task
        in
        let database =
          {
            close;
            check = (fun () -> with_current (fun value -> value.check ()));
            health = (fun () -> with_current (fun value -> value.health ()));
            sitemap_data =
              (fun () -> with_current (fun value -> value.sitemap_data ()));
            narrative_image_asset =
              (fun category id ->
                with_current (fun value -> value.narrative_image_asset category id));
            material_asset =
              (fun category id ->
                with_current (fun value -> value.material_asset category id));
            narrative_media_asset =
              (fun kind id ->
                with_current (fun value -> value.narrative_media_asset kind id));
            orphan_narrative_image_assets =
              (fun locale ->
                with_current (fun value -> value.orphan_narrative_image_assets locale));
            orphan_narrative_media_assets =
              (fun locale ->
                with_current (fun value -> value.orphan_narrative_media_assets locale));
            narrative_image_asset_reverse_references =
              (fun locale category id ->
                with_current (fun value -> value.narrative_image_asset_reverse_references locale category id));
            narrative_media_asset_reverse_references =
              (fun locale kind id ->
                with_current (fun value -> value.narrative_media_asset_reverse_references locale kind id));
            movements =
              (fun locale -> with_current (fun value -> value.movements locale));
            movement =
              (fun locale id ->
                with_current (fun value -> value.movement locale id));
            section =
              (fun locale movement_id section_id ->
                with_current (fun value ->
                    value.section locale movement_id section_id));
            score_story =
              (fun locale movement_id section_id story_id ->
                with_current (fun value ->
                    value.score_story locale movement_id section_id story_id));
            archive_index =
              (fun locale ->
                with_current (fun value -> value.archive_index locale));
            archive_groups =
              (fun locale category ->
                with_current (fun value -> value.archive_groups locale category));
            archive_group =
              (fun locale category id ->
                with_current (fun value -> value.archive_group locale category id));
            archive_story =
              (fun locale category group_id story_id ->
                with_current (fun value ->
                    value.archive_story locale category group_id story_id));
            galleries =
              (fun locale -> with_current (fun value -> value.galleries locale));
            gallery =
              (fun locale id ->
                with_current (fun value -> value.gallery locale id));
            presentation_assets =
              (fun locale ->
                with_current (fun value -> value.presentation_assets locale));
            presentation_asset =
              (fun locale category id ->
                with_current (fun value ->
                    value.presentation_asset locale category id));
            search =
              (fun locale query ->
                with_current (fun value -> value.search locale query));
          }
        in
        Lwt.return (Ok (database, state))
  with
  | Sys_error error -> Lwt.return (Error error)
  | Unix.Unix_error (error, operation, argument) ->
      Lwt.return
        (Error
           (Printf.sprintf "%s(%S): %s" operation argument
              (Unix.error_message error)))

let live ~url ~cache_dir ~poll_seconds ~download_timeout_seconds =
  let fetch = http_fetch ~url in
  start_live ~fetch ~cache_dir ~download_timeout_seconds >>= function
  | Error error -> Lwt.return (Error error)
  | Ok (database, state) ->
      let rec poll () =
        if state.closed then Lwt.return_unit
        else
          Lwt_unix.sleep poll_seconds >>= fun () ->
          refresh_once ~fetch ~cache_dir ~download_timeout_seconds state
          >>= ( function
          | `Failed error ->
              if not state.closed then
                Printf.eprintf "database refresh failed: %s\n%!" error;
              Lwt.return_unit
          | `Not_modified | `Replaced -> Lwt.return_unit )
          >>= poll
      in
      let poll_task = poll () in
      Lwt.async (fun () -> poll_task);
      let close = database.close in
      let close_task = ref None in
      let close_with_poll () =
        match !close_task with
        | Some task -> task
        | None ->
            state.closed <- true;
            Lwt.cancel poll_task;
            let task =
              Lwt.catch
                (fun () -> poll_task)
                (function
                  | Lwt.Canceled -> Lwt.return_unit | error -> Lwt.fail error)
              >>= close
            in
            close_task := Some task;
            task
      in
      Lwt.return (Ok { database with close = close_with_poll })

module For_test = struct
  type nonrec fetch_result = fetch_result
  type refresh_result = [ `Not_modified | `Replaced | `Failed of string ]

  type controlled_live = {
    database : t;
    refresh_once : unit -> refresh_result Lwt.t;
  }

  let live ~fetch ~cache_dir ~download_timeout_seconds =
    start_live ~fetch ~cache_dir ~download_timeout_seconds
    >|= Result.map (fun (database, state) ->
            {
              database;
              refresh_once =
                (fun () ->
                  refresh_once ~fetch ~cache_dir ~download_timeout_seconds state);
            })

  let sqlite_with_pool_observer = sqlite_with_pool_observer
end

let close (database : t) = database.close ()
let health (database : t) = database.health ()
let sitemap_data (database : t) = database.sitemap_data ()
let narrative_image_asset (database : t) category id = database.narrative_image_asset category id

let material_asset (database : t) category id =
  database.material_asset category id

let narrative_media_asset (database : t) kind id =
  database.narrative_media_asset kind id

let orphan_narrative_image_assets (database : t) locale = database.orphan_narrative_image_assets locale

let orphan_narrative_media_assets (database : t) locale = database.orphan_narrative_media_assets locale

let narrative_image_asset_reverse_references (database : t) locale category id =
  database.narrative_image_asset_reverse_references locale category id

let narrative_media_asset_reverse_references (database : t) locale kind id =
  database.narrative_media_asset_reverse_references locale kind id

let movements (database : t) locale = database.movements locale
let movement (database : t) locale id = database.movement locale id

let section (database : t) locale movement_id section_id =
  database.section locale movement_id section_id

let score_story (database : t) locale movement_id section_id story_id =
  database.score_story locale movement_id section_id story_id

let archive_index (database : t) locale = database.archive_index locale

let archive_groups (database : t) locale category =
  database.archive_groups locale category

let archive_group (database : t) locale category id =
  database.archive_group locale category id

let archive_story (database : t) locale category group_id story_id =
  database.archive_story locale category group_id story_id

let galleries (database : t) locale = database.galleries locale
let gallery (database : t) locale id = database.gallery locale id
let presentation_assets (database : t) locale = database.presentation_assets locale

let presentation_asset (database : t) locale category id =
  database.presentation_asset locale category id

let search (database : t) locale query = database.search locale query
