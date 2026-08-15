(** SQLite readers and the remote-generation replacement implementation. *)

open Lwt.Infix

type error = [ `Not_found | `Unavailable of string ]

type sitemap_data = {
  movements : (string * string) list;
  movement_sections : (string * string * string) list;
  archive_groups : (string * string * string) list;
  galleries : (string * string) list;
}

type t = {
  close : unit -> unit Lwt.t;
  check : unit -> (unit, error) result Lwt.t;
  health : unit -> (unit, error) result Lwt.t;
  sitemap_data : unit -> (sitemap_data, error) result Lwt.t;
  art : string -> string -> (Model.art, error) result Lwt.t;
  source_art : string -> string -> (Model.source_art, error) result Lwt.t;
  unreferenced_arts : unit -> (Model.unreferenced_art list, error) result Lwt.t;
  art_context :
    string -> string -> string -> (Model.art_context, error) result Lwt.t;
  movements : string -> (Model.movement list, error) result Lwt.t;
  movement : string -> string -> (Model.movement_detail, error) result Lwt.t;
  movement_section :
    string ->
    string ->
    string ->
    (Model.movement_section_detail, error) result Lwt.t;
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
}

let unique_story_art_references references =
  let seen = Hashtbl.create (List.length references) in
  List.filter
    (fun (reference : Model.story_art_reference) ->
      let key = (reference.category, reference.art_id) in
      if Hashtbl.mem seen key then false
      else (
        Hashtbl.add seen key ();
        true))
    references

let representative_story_art_reference = function
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

let character_prefix art_id =
  match String.index_opt art_id '#' with
  | Some position -> String.sub art_id 0 position
  | None -> art_id

let archive_kind_of_route = function
  | "events" -> Some "events"
  | "operator-record" -> Some "operator_record"
  | "integrated-strategies" -> Some "integrated_strategies"
  | "reclamation-algorithm" -> Some "reclamation_algorithm"
  | "others" -> Some "others"
  | _ -> None

let archive_route_of_kind = function
  | "events" -> "events"
  | "operator_record" -> "operator-record"
  | "integrated_strategies" -> "integrated-strategies"
  | "reclamation_algorithm" -> "reclamation-algorithm"
  | "others" -> "others"
  | value -> invalid_arg ("unknown archive kind: " ^ value)

module Query = struct
  open Caqti_type.Std
  open Caqti_request.Infix

  let schema_version = (unit ->! int) "PRAGMA user_version"
  let ping = (unit ->! int) "SELECT 1"

  let sitemap_movements =
    (unit ->* t2 string string)
      "SELECT locale, movement_id FROM movements ORDER BY locale, position"

  let sitemap_movement_sections =
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
        SELECT locale, archive_kind, archive_id
        FROM archive_groups
        ORDER BY locale, position
      |}

  let sitemap_galleries =
    (unit ->* t2 string string)
      "SELECT locale, gallery_id FROM gallery_groups ORDER BY locale, position"

  let art =
    let row =
      t2 string
        (t2 string
           (t2 int64
              (t2 int
                 (t2 int (t2 (option string) (option string))))))
    in
    (t2 string string ->* row)
      {|
        SELECT art.category, art.object_key, art.byte_size, art.width,
               art.height, reference.source_category, reference.source_art_id
        FROM arts AS art
        LEFT JOIN art_source_refs AS reference
          ON reference.category = art.category
         AND reference.art_id = art.art_id
        WHERE art.category = ? AND art.art_id = ?
        ORDER BY reference.position
      |}

  let source_art =
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
        SELECT kind, category, character_id, role, variant, object_key,
               byte_size, width, height
        FROM source_arts
        WHERE category = ? AND source_art_id = ?
      |}

  let unreferenced_arts =
    (unit ->* t2 string (t2 string string))
      {|
        SELECT art.category, art.art_id, art.object_key
        FROM arts AS art
        WHERE NOT EXISTS (
          SELECT 1
          FROM story_art_references AS reference
          WHERE reference.locale IN ('CN', 'EN', 'JP', 'KR', 'TW')
            AND reference.art_id = art.art_id
            AND reference.category = art.category
        )
          AND NOT EXISTS (
            SELECT 1
            FROM gallery_display_artworks AS artwork
            WHERE artwork.category = art.category
              AND artwork.art_id = art.art_id
          )
          AND NOT EXISTS (
            SELECT 1
            FROM art_source_refs AS reference
            WHERE reference.source_category = art.category
              AND reference.source_art_id = art.art_id
          )
        ORDER BY CASE art.category
                   WHEN 'image' THEN 0
                   WHEN 'background' THEN 1
                   WHEN 'item' THEN 2
                   WHEN 'character' THEN 3
                   ELSE 4
                 END,
                 art.art_id
      |}

  let art_context_exists =
    (t2 string string ->? int)
      "SELECT 1 FROM arts WHERE category = ? AND art_id = ?"

  let art_context_occurrences =
    (t2 string (t2 string string) ->* string)
      {|
        SELECT json_object(
          'parentKind', collection.collection_kind,
          'movementID', movement.movement_id,
          'movementName', movement.name,
          'sectionID', section.section_id,
          'sectionName', section.name,
          'archiveKind', archive.archive_kind,
          'groupID', archive.archive_id,
          'groupName', archive.name,
          'storyID', story.story_id,
          'storyName', story.name,
          'storyCode', story.code,
          'storyTagText', story.tag_text,
          'names', reference.names_json
        )
        FROM story_art_references AS reference
        JOIN stories AS story
          ON story.locale = reference.locale
         AND story.story_id = reference.story_id
        JOIN story_collections AS collection
          ON collection.locale = story.locale
         AND collection.collection_id = story.collection_id
        LEFT JOIN movement_sections AS section
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
          AND reference.art_id = ?
        ORDER BY COALESCE(movement.position, archive.position), story.position,
                 reference.position
      |}

  let art_context_siblings =
    (t2 string (t2 string (t2 string (t2 string string))) ->* string)
      {|
        SELECT json_object(
          'artID', art.art_id,
          'objectKey', art.object_key,
          'names', reference.names_json
        )
        FROM arts AS art
        LEFT JOIN story_art_references AS reference
          ON reference.locale = ?
         AND reference.category = art.category
         AND reference.art_id = art.art_id
        WHERE art.category = 'character' AND art.art_id <> ?
          AND (
            art.art_id = ?
            OR substr(art.art_id, 1, length(?) + 1) = ? || '#'
          )
        ORDER BY art.art_id, reference.story_id, reference.position
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
          'iconByteSize', icon.byte_size,
          'iconWidth', icon.width,
          'iconHeight', icon.height,
          'logoID', movement.logo_asset_id,
          'logoObjectKey', logo.object_key,
          'logoByteSize', logo.byte_size,
          'logoWidth', logo.width,
          'logoHeight', logo.height,
          'backgroundID', movement.background_asset_id,
          'backgroundObjectKey', background.object_key,
          'backgroundByteSize', background.byte_size,
          'backgroundWidth', background.width,
          'backgroundHeight', background.height,
          'videoID', video_location.video_id,
          'videoObjectKey', video.object_key,
          'videoByteSize', video.byte_size,
          'videoWidth', video.width,
          'videoHeight', video.height,
          'videoRateNumerator', video.frame_rate_numerator,
          'videoRateDenominator', video.frame_rate_denominator,
          'videoFrameCount', video.frame_count
        )
        FROM movements AS movement
        LEFT JOIN score_assets AS icon
          ON icon.asset_kind = 'icon'
         AND icon.asset_id = movement.icon_asset_id
        LEFT JOIN score_assets AS logo
          ON logo.asset_kind = 'logo'
         AND logo.asset_id = movement.logo_asset_id
        LEFT JOIN score_assets AS background
          ON background.asset_kind = 'background'
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
                      WHEN 'mainline_split' THEN 1
                      ELSE 2
                    END,
                    candidate.position
           LIMIT 1
         )
        LEFT JOIN score_videos AS video
          ON video.video_id = video_location.video_id
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
          'keyVisualByteSize', key_visual.byte_size,
          'keyVisualWidth', key_visual.width,
          'keyVisualHeight', key_visual.height,
          'titleID', section.title_asset_id,
          'titleObjectKey', title.object_key,
          'titleByteSize', title.byte_size,
          'titleWidth', title.width,
          'titleHeight', title.height,
          'backgroundID', section.background_asset_id,
          'backgroundObjectKey', background.object_key,
          'backgroundByteSize', background.byte_size,
          'backgroundWidth', background.width,
          'backgroundHeight', background.height,
          'decorationID', section.decoration_asset_id,
          'decorationObjectKey', decoration.object_key,
          'decorationByteSize', decoration.byte_size,
          'decorationWidth', decoration.width,
          'decorationHeight', decoration.height,
          'retroBackgroundID', section.retro_background_asset_id,
          'retroBackgroundObjectKey', retro_background.object_key,
          'retroBackgroundByteSize', retro_background.byte_size,
          'retroBackgroundWidth', retro_background.width,
          'retroBackgroundHeight', retro_background.height,
          'videoID', location.video_id,
          'videoObjectKey', video.object_key,
          'videoByteSize', video.byte_size,
          'videoWidth', video.width,
          'videoHeight', video.height,
          'videoRateNumerator', video.frame_rate_numerator,
          'videoRateDenominator', video.frame_rate_denominator,
          'videoFrameCount', video.frame_count
        )
        FROM movement_locations AS location
        JOIN movement_sections AS section
          ON section.locale = location.locale
         AND section.section_id = location.section_id
        LEFT JOIN score_assets AS key_visual
          ON key_visual.asset_kind = 'key_visual'
         AND key_visual.asset_id = section.key_visual_asset_id
        LEFT JOIN score_assets AS title
          ON title.asset_kind = 'title'
         AND title.asset_id = section.title_asset_id
        LEFT JOIN score_assets AS background
          ON background.asset_kind = 'background'
         AND background.asset_id = section.background_asset_id
        LEFT JOIN score_assets AS decoration
          ON decoration.asset_kind = 'decoration'
         AND decoration.asset_id = section.decoration_asset_id
        LEFT JOIN score_assets AS retro_background
          ON retro_background.asset_kind = 'retro_background'
         AND retro_background.asset_id = section.retro_background_asset_id
        LEFT JOIN score_videos AS video
          ON video.video_id = location.video_id
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
          'keyVisualByteSize', key_visual.byte_size,
          'keyVisualWidth', key_visual.width,
          'keyVisualHeight', key_visual.height,
          'titleID', section.title_asset_id,
          'titleObjectKey', title.object_key,
          'titleByteSize', title.byte_size,
          'titleWidth', title.width,
          'titleHeight', title.height,
          'backgroundID', section.background_asset_id,
          'backgroundObjectKey', background.object_key,
          'backgroundByteSize', background.byte_size,
          'backgroundWidth', background.width,
          'backgroundHeight', background.height,
          'decorationID', section.decoration_asset_id,
          'decorationObjectKey', decoration.object_key,
          'decorationByteSize', decoration.byte_size,
          'decorationWidth', decoration.width,
          'decorationHeight', decoration.height,
          'retroBackgroundID', section.retro_background_asset_id,
          'retroBackgroundObjectKey', retro_background.object_key,
          'retroBackgroundByteSize', retro_background.byte_size,
          'retroBackgroundWidth', retro_background.width,
          'retroBackgroundHeight', retro_background.height,
          'videoID', active_video_location.video_id,
          'videoObjectKey', video.object_key,
          'videoByteSize', video.byte_size,
          'videoWidth', video.width,
          'videoHeight', video.height,
          'videoRateNumerator', video.frame_rate_numerator,
          'videoRateDenominator', video.frame_rate_denominator,
          'videoFrameCount', video.frame_count
        )
        FROM movement_locations AS location
        JOIN movement_sections AS section
          ON section.locale = location.locale
         AND section.section_id = location.section_id
        LEFT JOIN score_assets AS key_visual
          ON key_visual.asset_kind = 'key_visual'
         AND key_visual.asset_id = section.key_visual_asset_id
        LEFT JOIN score_assets AS title
          ON title.asset_kind = 'title'
         AND title.asset_id = section.title_asset_id
        LEFT JOIN score_assets AS background
          ON background.asset_kind = 'background'
         AND background.asset_id = section.background_asset_id
        LEFT JOIN score_assets AS decoration
          ON decoration.asset_kind = 'decoration'
         AND decoration.asset_id = section.decoration_asset_id
        LEFT JOIN score_assets AS retro_background
          ON retro_background.asset_kind = 'retro_background'
         AND retro_background.asset_id = section.retro_background_asset_id
        LEFT JOIN movement_locations AS active_video_location
          ON active_video_location.locale = location.locale
         AND active_video_location.movement_id = location.movement_id
         AND active_video_location.location_id = (
           SELECT candidate.location_id
           FROM movement_locations AS candidate
           WHERE candidate.locale = location.locale
             AND candidate.movement_id = location.movement_id
             AND candidate.location_type = 'mainline_split'
             AND candidate.video_id IS NOT NULL
             AND candidate.position <= location.position
           ORDER BY candidate.position DESC
           LIMIT 1
         )
        LEFT JOIN score_videos AS video
          ON video.video_id = active_video_location.video_id
        WHERE location.locale = ? AND location.movement_id = ?
          AND location.section_id = ? AND location.location_type = 'story_set'
      |}

  let movement_splits =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'id', location.location_id,
          'position', location.position,
          'subName', location.split_sub_name,
          'iconID', location.split_icon_asset_id,
          'iconObjectKey', icon.object_key,
          'iconByteSize', icon.byte_size,
          'iconWidth', icon.width,
          'iconHeight', icon.height,
          'videoID', location.video_id,
          'videoObjectKey', video.object_key,
          'videoByteSize', video.byte_size,
          'videoWidth', video.width,
          'videoHeight', video.height,
          'videoRateNumerator', video.frame_rate_numerator,
          'videoRateDenominator', video.frame_rate_denominator,
          'videoFrameCount', video.frame_count
        )
        FROM movement_locations AS location
        LEFT JOIN score_assets AS icon
          ON icon.asset_kind = 'split'
         AND icon.asset_id = location.split_icon_asset_id
        LEFT JOIN score_videos AS video
          ON video.video_id = location.video_id
        WHERE location.locale = ? AND location.movement_id = ?
          AND location.location_type = 'mainline_split'
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

  let collection_story_references =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'storyID', story.story_id, 'artID', reference.art_id,
          'kind', reference.kind, 'category', reference.category,
          'title', reference.title, 'subtitle', reference.subtitle,
          'names', json(reference.names_json), 'objectKey', art.object_key
        )
        FROM stories AS story
        JOIN story_art_references AS reference
          ON reference.locale = story.locale
         AND reference.story_id = story.story_id
        LEFT JOIN arts AS art
          ON art.category = reference.category
         AND art.art_id = reference.art_id
        WHERE story.locale = ? AND story.collection_id = ?
        ORDER BY story.position, reference.position
      |}

  let archive_index =
    (string ->* t2 string int)
      {|
        WITH kinds(kind, position) AS (
          VALUES ('events', 0), ('operator_record', 1),
                 ('integrated_strategies', 2),
                 ('reclamation_algorithm', 3), ('others', 4)
        )
        SELECT kinds.kind, COUNT(archive.archive_id)
        FROM kinds
        LEFT JOIN archive_groups AS archive
          ON archive.locale = ? AND archive.archive_kind = kinds.kind
        GROUP BY kinds.kind, kinds.position
        ORDER BY kinds.position
      |}

  let archive_groups =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'id', archive_id, 'collectionID', collection_id, 'name', name,
          'archiveKind', archive_kind, 'storyType', story_type
        )
        FROM archive_groups
        WHERE locale = ? AND archive_kind = ?
        ORDER BY position
      |}

  let archive_group_references =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'groupID', archive.archive_id, 'storyID', story.story_id,
          'artID', reference.art_id, 'kind', reference.kind,
          'category', reference.category, 'title', reference.title,
          'subtitle', reference.subtitle, 'names', json(reference.names_json),
          'objectKey', art.object_key
        )
        FROM archive_groups AS archive
        JOIN stories AS story
          ON story.locale = archive.locale
         AND story.collection_id = archive.collection_id
        JOIN story_art_references AS reference
          ON reference.locale = story.locale
         AND reference.story_id = story.story_id
        LEFT JOIN arts AS art
          ON art.category = reference.category AND art.art_id = reference.art_id
        WHERE archive.locale = ? AND archive.archive_kind = ?
        ORDER BY archive.position, story.position, reference.position
      |}

  let archive_group =
    (t2 string (t2 string string) ->? string)
      {|
        SELECT json_object(
          'id', archive_id, 'collectionID', collection_id, 'name', name,
          'archiveKind', archive_kind, 'storyType', story_type
        )
        FROM archive_groups
        WHERE locale = ? AND archive_kind = ? AND archive_id = ?
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
          'archiveKind', archive.archive_kind, 'groupID', archive.archive_id,
          'groupName', archive.name
        )
        FROM gallery_groups AS gallery
        JOIN story_collections AS collection
          ON collection.locale = gallery.locale
         AND collection.collection_id = gallery.collection_id
        LEFT JOIN movement_sections AS section
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
          'archiveKind', archive.archive_kind, 'groupID', archive.archive_id,
          'groupName', archive.name
        )
        FROM gallery_groups AS gallery
        JOIN story_collections AS collection
          ON collection.locale = gallery.locale
         AND collection.collection_id = gallery.collection_id
        LEFT JOIN movement_sections AS section
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
        SELECT gallery_id FROM gallery_groups
        WHERE locale = ? AND collection_id = ?
        ORDER BY position LIMIT 1
      |}

  let gallery_displays =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'id', display_id, 'position', position, 'name', name,
          'description', description, 'relatedStoryID', related_story_id,
          'relatedStageID', related_stage_id
        )
        FROM gallery_displays
        WHERE locale = ? AND gallery_id = ?
        ORDER BY position
      |}

  let gallery_artworks =
    (t2 string string ->* string)
      {|
        SELECT json_object(
          'displayID', artwork.display_id, 'position', artwork.position,
          'cgID', artwork.cg_id, 'artID', artwork.art_id,
          'category', artwork.category, 'objectKey', art.object_key
        )
        FROM gallery_display_artworks AS artwork
        LEFT JOIN arts AS art
          ON art.category = artwork.category AND art.art_id = artwork.art_id
        WHERE artwork.locale = ? AND artwork.gallery_id = ?
        ORDER BY artwork.display_id, artwork.position
      |}

  let gallery_previews =
    (t2 string string ->* t2 string (option string))
      {|
        WITH first_members AS (
          SELECT artwork.locale, artwork.gallery_id, artwork.display_id,
                 artwork.category, artwork.art_id,
                 ROW_NUMBER() OVER (
                   PARTITION BY artwork.locale, artwork.gallery_id,
                                artwork.display_id
                   ORDER BY artwork.position
                 ) AS member_rank
          FROM gallery_display_artworks AS artwork
          WHERE artwork.locale = ?
        )
        SELECT gallery.gallery_id, art.object_key
        FROM gallery_groups AS gallery
        JOIN gallery_displays AS display
          ON display.locale = gallery.locale
         AND display.gallery_id = gallery.gallery_id
        LEFT JOIN first_members AS member
          ON member.locale = display.locale
         AND member.gallery_id = display.gallery_id
         AND member.display_id = display.display_id
         AND member.member_rank = 1
        LEFT JOIN arts AS art
          ON art.category = member.category AND art.art_id = member.art_id
        WHERE gallery.locale = ?
        ORDER BY gallery.position, display.position
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

  let names_value = function
    | `List values -> List.filter_map to_string_option values
    | `String raw ->
        Yojson.Safe.from_string raw |> to_list |> List.filter_map to_string_option
    | `Null -> []
    | _ -> invalid_arg "expected names array"

  let names value key = value |> member key |> names_value
end

let decode_image_reference prefix value =
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
                  byte_size =
                    Option.get (Json.int64_opt value (prefix ^ "ByteSize"));
                  width = Option.get (Json.int_opt value (prefix ^ "Width"));
                  height = Option.get (Json.int_opt value (prefix ^ "Height"));
                }
      in
      Some Model.{ id; image }

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
                  byte_size = Json.int64 value "videoByteSize";
                  width = Json.int value "videoWidth";
                  height = Json.int value "videoHeight";
                  frame_rate =
                    Float.of_int numerator /. Float.of_int denominator;
                  frame_count = Json.int value "videoFrameCount";
                }
      in
      Some Model.{ id; video }

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
      icon = decode_image_reference "icon" value;
      logo = decode_image_reference "logo" value;
      background = decode_image_reference "background" value;
      background_video = decode_video_reference value;
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
        key_visual = decode_image_reference "keyVisual" value;
        title_image = decode_image_reference "title" value;
        background = decode_image_reference "background" value;
        decoration = decode_image_reference "decoration" value;
        retro_background = decode_image_reference "retroBackground" value;
        story_count = Json.int value "storyCount";
      }
  in
  (section, Json.string value "collectionID", decode_video_reference value)

let decode_split raw =
  let value = Json.parse raw in
  Model.
    {
      id = Json.string value "id";
      position = Json.int value "position";
      sub_name = Json.string value "subName";
      icon = decode_image_reference "icon" value;
      video = decode_video_reference value;
    }

let decode_story raw =
  let value = Json.parse raw in
  Model.
    {
      id = Json.string value "id";
      tag = Json.string value "tag";
      tag_text = Json.string value "tagText";
      code = Json.string value "code";
      name = Json.string value "name";
      info = Json.string value "info";
      art_references = [];
    }

let decode_story_reference raw =
  let value = Json.parse raw in
  ( Json.string value "storyID",
    Model.
      {
        art_id = Json.string value "artID";
        kind = Json.string value "kind";
        category = Json.string value "category";
        title = Json.string_opt value "title";
        subtitle = Json.string_opt value "subtitle";
        names = Json.names value "names";
        composition_object_key = Json.string_opt value "objectKey";
      } )

let preview_references references =
  let available =
    references
    |> List.filter (fun (reference : Model.story_art_reference) ->
        Option.is_some reference.composition_object_key
        && (String.equal reference.category "image"
           || String.equal reference.category "background"))
    |> unique_story_art_references
  in
  let images =
    List.filter
      (fun (reference : Model.story_art_reference) ->
        String.equal reference.category "image")
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
        let preview_art_references = for_story story.id |> preview_references in
        Model.
          {
            story;
            representative_art_reference =
              representative_story_art_reference preview_art_references;
            preview_art_references;
          })
      stories
  in
  let all_references = references |> List.map snd in
  (stories, summaries, all_references)

let decode_parent value =
  match Json.string value "parentKind" with
  | "movement_section" ->
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
          archive_kind =
            Json.string value "archiveKind" |> archive_route_of_kind;
          group_id = Json.string value "groupID";
          group_name = Json.string value "groupName";
        }
  | kind -> invalid_arg ("unknown collection parent: " ^ kind)

let decode_archive_group raw =
  let value = Json.parse raw in
  let archive_kind = Json.string value "archiveKind" in
  let group_type =
    Json.string_opt value "storyType" |> Option.value ~default:archive_kind
  in
  ( Model.
      {
        id = Json.string value "id";
        name = Json.string value "name";
        kind = archive_route_of_kind archive_kind;
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

let decode_gallery_artwork raw =
  let value = Json.parse raw in
  ( Json.string value "displayID",
    Model.
      {
        position = Json.int value "position";
        cg_id = Json.string value "cgID";
        art_id = Json.string value "artID";
        category = Json.string value "category";
        composition_object_key = Json.string_opt value "objectKey";
      } )

let decode_gallery base_raw display_raws artwork_raws =
  let base = decode_gallery_base base_raw in
  let artworks = List.map decode_gallery_artwork artwork_raws in
  let displays =
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
            artworks =
              artworks
              |> List.filter_map (fun (display_id, artwork) ->
                  if String.equal id display_id then Some artwork else None);
          })
      display_raws
  in
  Model.
    {
      id = base.id;
      name = base.name;
      description = base.description;
      parent = base.parent;
      displays;
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
      let check () =
        use (fun (module Db) -> Db.find Query.schema_version ()) >|= function
        | Error error -> Error error
        | Ok version when version <> 2 ->
            Error
              (`Unavailable
                 (Printf.sprintf "unsupported SQLite schema version %d" version))
        | Ok _ -> Ok ()
      in
      let health () =
        use (fun (module Db) -> Db.find Query.ping ()) >|= function
        | Ok 1 -> Ok ()
        | Ok _ -> Error (`Unavailable "unexpected SQLite health-check result")
        | Error error -> Error error
      in
      let sitemap_data () =
        use (fun (module Db) ->
            Db.collect_list Query.sitemap_movements () >>= function
            | Error error -> Lwt.return (Error error)
            | Ok movements ->
                Db.collect_list Query.sitemap_movement_sections ()
                >>= ( function
                | Error error -> Lwt.return (Error error)
                | Ok movement_sections ->
                    Db.collect_list Query.sitemap_archive_groups ()
                    >>= ( function
                    | Error error -> Lwt.return (Error error)
                    | Ok archive_groups ->
                        Db.collect_list Query.sitemap_galleries ()
                        >|= Result.map (fun galleries ->
                                ( movements,
                                  movement_sections,
                                  archive_groups,
                                  galleries )) ) ))
        >|= Result.map (fun (movements, sections, archives, galleries) ->
                {
                  movements;
                  movement_sections =
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
      let art category id =
        use (fun (module Db) -> Db.collect_list Query.art (category, id))
        >|= function
        | Error error -> Error error
        | Ok [] -> Error `Not_found
        | Ok
            ((category, (object_key, (byte_size, (width, (height, _))))) :: _ as
             rows) ->
            let source_arts =
              rows
              |> List.filter_map
                   (fun (_, (_, (_, (_, (_, (source_category, source_id)))))) ->
                     match (source_category, source_id) with
                     | Some category, Some id -> Some Model.{ id; category }
                     | _ -> None)
            in
            Ok
              Model.
                {
                  id;
                  category;
                  image = { object_key; byte_size; width; height };
                  source_arts;
                }
      in
      let source_art category id =
        use (fun (module Db) ->
            Db.find_opt Query.source_art (category, id))
        >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok
            (Some
               ( kind,
                 ( category,
                   ( character_id,
                     ( role,
                       ( variant,
                         (object_key, (byte_size, (width, height))) ) ) ) ) )) ->
            Ok
              Model.
                {
                  id;
                  category;
                  kind;
                  character_id;
                  role;
                  variant;
                  image = { object_key; byte_size; width; height };
                }
      in
      let unreferenced_arts () =
        use (fun (module Db) -> Db.collect_list Query.unreferenced_arts ())
        >|= Result.map (fun rows ->
                List.map
                  (fun (category, (id, composition_object_key)) ->
                    Model.{ id; category; composition_object_key })
                  rows)
      in
      let art_context locale category id =
        use (fun (module Db) ->
            Db.find_opt Query.art_context_exists (category, id) >>= function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Ok None)
            | Ok (Some _) ->
                Db.collect_list Query.art_context_occurrences
                  (locale, (category, id))
                >>= ( function
                | Error error -> Lwt.return (Error error)
                | Ok occurrences ->
                    (if String.equal category "character" then
                       let prefix = character_prefix id in
                       Db.collect_list Query.art_context_siblings
                         (locale, (id, (prefix, (prefix, prefix))))
                     else Lwt.return (Ok []))
                    >|= Result.map (fun siblings ->
                            Some (occurrences, siblings)) ))
        >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok (Some (occurrence_raws, sibling_raws)) ->
            decode_result "art context" (fun () ->
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
                let rec decode_siblings values = function
                  | [] -> List.rev values
                  | raw :: rest ->
                      let value = Json.parse raw in
                      let art_id = Json.string value "artID" in
                      let object_key = Json.string value "objectKey" in
                      let rec gather names = function
                        | next :: tail ->
                            let next_value = Json.parse next in
                            if String.equal art_id (Json.string next_value "artID")
                            then
                              gather
                                (Json.names next_value "names" @ names)
                                tail
                            else (names, next :: tail)
                        | [] -> (names, [])
                      in
                      let sibling_names, remaining =
                        gather (Json.names value "names") rest
                      in
                      decode_siblings
                        (Model.
                           {
                             art_id;
                             names = unique_strings sibling_names;
                             composition_object_key = object_key;
                           }
                        :: values)
                        remaining
                in
                Model.
                  {
                    names;
                    siblings = decode_siblings [] sibling_raws;
                    occurrences;
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
                        Db.collect_list Query.movement_splits (locale, id)
                        >|= Result.map (fun splits -> (sections, splits)) ))
                >|= function
                | Error error -> Error error
                | Ok (section_raws, split_raws) ->
                    decode_result "movement" (fun () ->
                        let section_items =
                          section_raws
                          |> List.map (fun raw ->
                                 let section, _, _ = decode_section raw in
                                 Model.Movement_section
                                   { position = section.position; section })
                        in
                        let split_items =
                          split_raws
                          |> List.map (fun raw ->
                                 Model.Movement_split (decode_split raw))
                        in
                        let position = function
                          | Model.Movement_split split -> split.position
                          | Model.Movement_section { position; _ } -> position
                        in
                        Model.
                          {
                            movement = selected;
                            items =
                              List.sort
                                (fun left right ->
                                  Int.compare (position left) (position right))
                                (section_items @ split_items);
                          }))
      in
      let gallery locale id =
        use (fun (module Db) ->
            Db.find_opt Query.gallery_base (locale, id) >>= function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Ok None)
            | Ok (Some base) ->
                Db.collect_list Query.gallery_displays (locale, id)
                >>= ( function
                | Error error -> Lwt.return (Error error)
                | Ok displays ->
                    Db.collect_list Query.gallery_artworks (locale, id)
                    >|= Result.map (fun artworks ->
                            Some (base, displays, artworks)) ))
        >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok (Some (base, displays, artworks)) ->
            decode_result "gallery" (fun () ->
                decode_gallery base displays artworks)
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
                    let preview_composition_object_keys =
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
                            displays = [];
                          };
                        preview_composition_object_keys;
                      })
                  base_raws)
      in
      let movement_section locale movement_id section_id =
        use (fun (module Db) ->
            Db.find_opt Query.section (locale, (movement_id, section_id))
            >>= function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Ok None)
            | Ok (Some section_raw) ->
                let _, collection_id, _ = decode_section section_raw in
                Db.collect_list Query.collection_stories (locale, collection_id)
                >>= ( function
                | Error error -> Lwt.return (Error error)
                | Ok stories ->
                    Db.collect_list Query.collection_story_references
                      (locale, collection_id)
                    >|= Result.map (fun references ->
                            Some
                              ( section_raw,
                                collection_id,
                                stories,
                                references )) ))
        >>= function
        | Error error -> Lwt.return (Error error)
        | Ok None -> Lwt.return (Error `Not_found)
        | Ok (Some (section_raw, collection_id, story_raws, reference_raws)) ->
            gallery_by_collection locale collection_id >|= ( function
            | Error error -> Error error
            | Ok gallery ->
                decode_result "movement section" (fun () ->
                    let section, _, active_background_video =
                      decode_section section_raw
                    in
                    let _, stories, art_references =
                      story_data story_raws reference_raws
                    in
                    Model.
                      {
                        section;
                        active_background_video;
                        stories;
                        art_references =
                          unique_story_art_references art_references;
                        gallery;
                      }) )
      in
      let story_detail_for_collection locale collection_id parent story_id =
        use (fun (module Db) ->
            Db.collect_list Query.collection_stories (locale, collection_id)
            >>= function
            | Error error -> Lwt.return (Error error)
            | Ok stories ->
                Db.collect_list Query.collection_story_references
                  (locale, collection_id)
                >|= Result.map (fun references -> (stories, references)))
        >|= function
        | Error error -> Error error
        | Ok (story_raws, reference_raws) ->
            decode_result "story" (fun () ->
                let stories, _, _ = story_data story_raws reference_raws in
                match
                  List.find_opt
                    (fun (story : Model.story) -> String.equal story.id story_id)
                    stories
                with
                | None -> None
                | Some story ->
                    let references =
                      List.map decode_story_reference reference_raws
                      |> List.filter_map (fun (candidate, reference) ->
                             if String.equal candidate story_id then
                               Some reference
                             else None)
                    in
                    Some
                      Model.
                        {
                          story = { story with art_references = references };
                          parent;
                        })
            |> (function
                 | Ok None -> Error `Not_found
                 | Ok (Some detail) -> Ok detail
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
                  (fun (kind, group_count) ->
                    Model.
                      {
                        kind = archive_route_of_kind kind;
                        group_count;
                      })
                  rows)
      in
      let archive_groups locale route_kind =
        match archive_kind_of_route route_kind with
        | None -> Lwt.return (Error `Not_found)
        | Some archive_kind ->
            use (fun (module Db) ->
                Db.collect_list Query.archive_groups (locale, archive_kind)
                >>= function
                | Error error -> Lwt.return (Error error)
                | Ok groups ->
                    Db.collect_list Query.archive_group_references
                      (locale, archive_kind)
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
                        let preview_art_references =
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
                            representative_art_reference =
                              representative_story_art_reference
                                preview_art_references;
                            preview_art_references;
                          })
                      group_raws)
      in
      let archive_group locale route_kind id =
        match archive_kind_of_route route_kind with
        | None -> Lwt.return (Error `Not_found)
        | Some archive_kind ->
            use (fun (module Db) ->
                Db.find_opt Query.archive_group (locale, (archive_kind, id))
                >>= function
                | Error error -> Lwt.return (Error error)
                | Ok None -> Lwt.return (Ok None)
                | Ok (Some group_raw) ->
                    let _, collection_id = decode_archive_group group_raw in
                    Db.collect_list Query.collection_stories
                      (locale, collection_id)
                    >>= ( function
                    | Error error -> Lwt.return (Error error)
                    | Ok stories ->
                        Db.collect_list Query.collection_story_references
                          (locale, collection_id)
                        >|= Result.map (fun references ->
                                Some
                                  ( group_raw,
                                    collection_id,
                                    stories,
                                    references )) ))
            >>= ( function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Error `Not_found)
            | Ok (Some (group_raw, collection_id, story_raws, reference_raws)) ->
                gallery_by_collection locale collection_id >|= ( function
                | Error error -> Error error
                | Ok gallery ->
                    decode_result "archive group" (fun () ->
                        let group, _ = decode_archive_group group_raw in
                        let _, stories, art_references =
                          story_data story_raws reference_raws
                        in
                        let art_references =
                          unique_story_art_references art_references
                        in
                        let preview_art_references =
                          preview_references art_references
                        in
                        Model.
                          {
                            group;
                            stories;
                            representative_art_reference =
                              representative_story_art_reference
                                preview_art_references;
                            preview_art_references;
                            art_references;
                            gallery;
                          }) ) )
      in
      let archive_story locale route_kind group_id story_id =
        match archive_kind_of_route route_kind with
        | None -> Lwt.return (Error `Not_found)
        | Some archive_kind ->
            use (fun (module Db) ->
                Db.find_opt Query.archive_group
                  (locale, (archive_kind, group_id)))
            >>= ( function
            | Error error -> Lwt.return (Error error)
            | Ok None -> Lwt.return (Error `Not_found)
            | Ok (Some raw) ->
                let group, collection_id = decode_archive_group raw in
                let parent =
                  Model.Archive_parent
                    {
                      archive_kind = group.kind;
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
          art;
          source_art;
          unreferenced_arts;
          art_context;
          movements;
          movement;
          movement_section;
          score_story;
          archive_index;
          archive_groups;
          archive_group;
          archive_story;
          galleries;
          gallery;
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
            art =
              (fun category id ->
                with_current (fun value -> value.art category id));
            source_art =
              (fun category id ->
                with_current (fun value -> value.source_art category id));
            unreferenced_arts =
              (fun () -> with_current (fun value -> value.unreferenced_arts ()));
            art_context =
              (fun locale category id ->
                with_current (fun value -> value.art_context locale category id));
            movements =
              (fun locale -> with_current (fun value -> value.movements locale));
            movement =
              (fun locale id ->
                with_current (fun value -> value.movement locale id));
            movement_section =
              (fun locale movement_id section_id ->
                with_current (fun value ->
                    value.movement_section locale movement_id section_id));
            score_story =
              (fun locale movement_id section_id story_id ->
                with_current (fun value ->
                    value.score_story locale movement_id section_id story_id));
            archive_index =
              (fun locale ->
                with_current (fun value -> value.archive_index locale));
            archive_groups =
              (fun locale kind ->
                with_current (fun value -> value.archive_groups locale kind));
            archive_group =
              (fun locale kind id ->
                with_current (fun value -> value.archive_group locale kind id));
            archive_story =
              (fun locale kind group_id story_id ->
                with_current (fun value ->
                    value.archive_story locale kind group_id story_id));
            galleries =
              (fun locale -> with_current (fun value -> value.galleries locale));
            gallery =
              (fun locale id ->
                with_current (fun value -> value.gallery locale id));
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
let art (database : t) category id = database.art category id

let source_art (database : t) category id =
  database.source_art category id

let unreferenced_arts (database : t) = database.unreferenced_arts ()

let art_context (database : t) locale category id =
  database.art_context locale category id

let movements (database : t) locale = database.movements locale
let movement (database : t) locale id = database.movement locale id

let movement_section (database : t) locale movement_id section_id =
  database.movement_section locale movement_id section_id

let score_story (database : t) locale movement_id section_id story_id =
  database.score_story locale movement_id section_id story_id

let archive_index (database : t) locale = database.archive_index locale

let archive_groups (database : t) locale kind =
  database.archive_groups locale kind

let archive_group (database : t) locale kind id =
  database.archive_group locale kind id

let archive_story (database : t) locale kind group_id story_id =
  database.archive_story locale kind group_id story_id

let galleries (database : t) locale = database.galleries locale
let gallery (database : t) locale id = database.gallery locale id
