open Arkwaifu_service
open Lwt.Infix

let require_ok label = function
  | Ok value -> value
  | Error `Not_found -> Alcotest.fail (label ^ ": not found")
  | Error (`Unavailable error) -> Alcotest.failf "%s: %s" label error

let with_environment variables callback =
  let previous =
    List.map (fun (name, _) -> (name, Sys.getenv_opt name)) variables
  in
  List.iter (fun (name, value) -> Unix.putenv name value) variables;
  Fun.protect
    ~finally:(fun () ->
      List.iter
        (fun (name, value) ->
          match value with
          | Some value -> Unix.putenv name value
          | None -> Unix.unsetenv name)
        previous)
    callback

let test_config_urls () =
  with_environment
    [
      ("ARKWAIFU_OBJECT_BASE_URL", "https://objects.example/bucket");
      ("ARKWAIFU_CN_OBJECT_BASE_URL", "https://cn-objects.example/bucket");
      ("ARKWAIFU_DATABASE_URL", "http://database.example/arkwaifu.sqlite3");
      ("ARKWAIFU_DATABASE_CACHE_DIR", "database-cache");
      ("ARKWAIFU_DATABASE_POLL_SECONDS", "30");
      ("ARKWAIFU_DATABASE_DOWNLOAD_TIMEOUT_SECONDS", "600");
      ("ARKWAIFU_INTERFACE", "127.0.0.1");
      ("ARKWAIFU_PORT", "8080");
    ]
  @@ fun () ->
  let config =
    match Config.load () with
    | Ok value -> value
    | Error error -> Alcotest.failf "valid URLs were rejected: %s" error
  in
  Alcotest.(check string)
    "database URL" "http://database.example/arkwaifu.sqlite3"
    (Uri.to_string config.database_url);
  Alcotest.(check (option string))
    "China object URL" (Some "https://cn-objects.example/bucket")
    config.china_object_base_url;
  Unix.unsetenv "ARKWAIFU_DATABASE_URL";
  let default =
    match Config.load () with
    | Ok value -> value
    | Error error -> Alcotest.failf "default URL rejected: %s" error
  in
  Alcotest.(check string)
    "derived database URL"
    "https://objects.example/bucket/arkwaifu.sqlite3"
    (Uri.to_string default.database_url);
  Unix.putenv "ARKWAIFU_DATABASE_URL" "ftp://database.example/archive.sqlite3";
  Alcotest.(check bool) "non-HTTP database URL rejected" true
    (Result.is_error (Config.load ()))

let execute database sql =
  match Sqlite3.exec database sql with
  | Sqlite3.Rc.OK -> ()
  | code ->
      Alcotest.failf "SQLite %s: %s" (Sqlite3.Rc.to_string code)
        (Sqlite3.errmsg database)

let fixture_schema =
  {|
    PRAGMA foreign_keys = ON;
    BEGIN;
    CREATE TABLE unit_versions (unit TEXT PRIMARY KEY, res_version TEXT NOT NULL);
    CREATE TABLE arts (art_id TEXT NOT NULL, category TEXT NOT NULL,
      object_key TEXT NOT NULL, byte_size INTEGER NOT NULL, width INTEGER NOT NULL,
      height INTEGER NOT NULL, PRIMARY KEY(category, art_id));
    CREATE TABLE source_arts (category TEXT NOT NULL, source_art_id TEXT NOT NULL,
      kind TEXT NOT NULL, character_id TEXT, role TEXT, variant TEXT,
      object_key TEXT NOT NULL, byte_size INTEGER NOT NULL, width INTEGER NOT NULL,
      height INTEGER NOT NULL, PRIMARY KEY(category, source_art_id));
    CREATE TABLE art_source_refs (category TEXT NOT NULL, art_id TEXT NOT NULL,
      position INTEGER NOT NULL, source_category TEXT NOT NULL,
      source_art_id TEXT NOT NULL, PRIMARY KEY(category, art_id, position));
    CREATE TABLE score_assets (asset_kind TEXT NOT NULL, asset_id TEXT NOT NULL,
      object_key TEXT NOT NULL, byte_size INTEGER NOT NULL, width INTEGER NOT NULL,
      height INTEGER NOT NULL, PRIMARY KEY(asset_kind, asset_id));
    CREATE TABLE score_videos (video_id TEXT PRIMARY KEY, object_key TEXT NOT NULL,
      byte_size INTEGER NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
      frame_rate_numerator INTEGER NOT NULL, frame_rate_denominator INTEGER NOT NULL,
      frame_count INTEGER NOT NULL);
    CREATE TABLE media_assets (
      media_kind TEXT NOT NULL, media_id TEXT NOT NULL,
      object_key TEXT NOT NULL, content_type TEXT NOT NULL,
      byte_size INTEGER NOT NULL, duration REAL, width INTEGER, height INTEGER,
      frame_rate_numerator INTEGER, frame_rate_denominator INTEGER,
      frame_count INTEGER, PRIMARY KEY(media_kind, media_id));
    CREATE TABLE story_collections (locale TEXT NOT NULL, collection_id TEXT NOT NULL,
      collection_kind TEXT NOT NULL, PRIMARY KEY(locale, collection_id));
    CREATE TABLE movements (locale TEXT NOT NULL, movement_id TEXT NOT NULL,
      position INTEGER NOT NULL, movement_type TEXT NOT NULL, name TEXT NOT NULL,
      icon_asset_id TEXT, logo_asset_id TEXT, background_asset_id TEXT,
      has_video INTEGER NOT NULL, start_time INTEGER NOT NULL,
      PRIMARY KEY(locale, movement_id));
    CREATE TABLE movement_sections (locale TEXT NOT NULL, section_id TEXT NOT NULL,
      collection_id TEXT NOT NULL, section_type TEXT NOT NULL, name TEXT NOT NULL,
      review_group_id TEXT, sort_by_year INTEGER NOT NULL,
      sort_within_year INTEGER NOT NULL, key_visual_asset_id TEXT,
      title_asset_id TEXT, background_asset_id TEXT, decoration_asset_id TEXT,
      retro_background_asset_id TEXT, description TEXT NOT NULL,
      has_video INTEGER NOT NULL, PRIMARY KEY(locale, section_id));
    CREATE TABLE movement_locations (locale TEXT NOT NULL, movement_id TEXT NOT NULL,
      location_id TEXT NOT NULL, position INTEGER NOT NULL, location_type TEXT NOT NULL,
      sort_id INTEGER NOT NULL, start_time INTEGER NOT NULL, present_stage_id TEXT,
      unlock_stage_id TEXT, section_id TEXT, split_icon_asset_id TEXT,
      split_sub_name TEXT, video_id TEXT,
      PRIMARY KEY(locale, movement_id, location_id));
    CREATE TABLE archive_groups (locale TEXT NOT NULL, archive_id TEXT NOT NULL,
      collection_id TEXT NOT NULL, position INTEGER NOT NULL, name TEXT NOT NULL,
      archive_kind TEXT NOT NULL, story_type TEXT, PRIMARY KEY(locale, archive_id));
    CREATE TABLE stories (locale TEXT NOT NULL, story_id TEXT NOT NULL,
      collection_id TEXT NOT NULL, tag TEXT NOT NULL, tag_text TEXT NOT NULL,
      code TEXT NOT NULL, name TEXT NOT NULL, info TEXT NOT NULL,
      text TEXT NOT NULL,
      position INTEGER NOT NULL, PRIMARY KEY(locale, story_id));
    CREATE TABLE story_art_references (locale TEXT NOT NULL, story_id TEXT NOT NULL,
      position INTEGER NOT NULL, art_id TEXT NOT NULL, kind TEXT NOT NULL,
      category TEXT NOT NULL, title TEXT, subtitle TEXT, names_json TEXT NOT NULL,
      PRIMARY KEY(locale, story_id, position));
    CREATE TABLE story_media_references (
      locale TEXT NOT NULL, story_id TEXT NOT NULL, position INTEGER NOT NULL,
      media_id TEXT NOT NULL, kind TEXT NOT NULL,
      PRIMARY KEY(locale, story_id, position));
    CREATE TABLE gallery_groups (locale TEXT NOT NULL, gallery_id TEXT NOT NULL,
      collection_id TEXT NOT NULL, position INTEGER NOT NULL, name TEXT NOT NULL,
      description TEXT NOT NULL, location_id TEXT,
      PRIMARY KEY(locale, gallery_id));
    CREATE TABLE gallery_displays (locale TEXT NOT NULL, gallery_id TEXT NOT NULL,
      display_id TEXT NOT NULL, position INTEGER NOT NULL, name TEXT NOT NULL,
      description TEXT NOT NULL, related_story_id TEXT, related_stage_id TEXT,
      PRIMARY KEY(locale, gallery_id, display_id));
    CREATE TABLE gallery_display_artworks (locale TEXT NOT NULL,
      gallery_id TEXT NOT NULL, display_id TEXT NOT NULL, position INTEGER NOT NULL,
      cg_id TEXT NOT NULL, art_id TEXT NOT NULL, category TEXT NOT NULL,
      composite_type TEXT NOT NULL,
      PRIMARY KEY(locale, gallery_id, display_id, position));
    CREATE TABLE gallery_display_artwork_panels (locale TEXT NOT NULL,
      gallery_id TEXT NOT NULL, display_id TEXT NOT NULL,
      artwork_position INTEGER NOT NULL, position INTEGER NOT NULL,
      panel_art_id TEXT NOT NULL CHECK(length(panel_art_id) > 0
        AND panel_art_id = lower(panel_art_id) AND instr(panel_art_id, '/') = 0),
      width INTEGER NOT NULL, height INTEGER NOT NULL,
      PRIMARY KEY(locale, gallery_id, display_id, artwork_position, position));
    CREATE TABLE search_entries (entry_key TEXT PRIMARY KEY,
      locale TEXT NOT NULL, kind TEXT NOT NULL, entry_id TEXT NOT NULL,
      category TEXT, collection_id TEXT, title TEXT NOT NULL, subtitle TEXT,
      search_text TEXT NOT NULL, parent_json TEXT, thumbnail_object_key TEXT);
    PRAGMA user_version = 2;
    COMMIT;
  |}

let fixture_rows =
  {|
    BEGIN;
    INSERT INTO unit_versions VALUES ('art', 'art-v1'), ('CN', 'cn-v1');
    INSERT INTO arts VALUES
      ('display-first', 'image', 'ART/art-v1/composition/image/display-first.png', 101, 100, 60),
      ('display-first/texture-a', 'image', 'ART/art-v1/composition/image/display-first%2Ftexture-a.png', 101, 100, 60),
      ('anime-poster', 'background', 'ART/art-v1/composition/background/anime-poster.png', 101, 1920, 1080),
      ('anime-poster/texture-a', 'image', 'ART/art-v1/composition/image/anime-poster%2Ftexture-a.png', 101, 1920, 1080),
      ('display-second', 'image', 'ART/art-v1/composition/image/display-second.png', 102, 100, 60),
      ('cg/part', 'image', 'ART/art-v1/composition/image/cg%2Fpart.png', 103, 70, 120),
      ('amiya', 'character', 'ART/art-v1/composition/character/amiya.png', 104, 80, 160),
      ('amiya#1', 'character', 'ART/art-v1/composition/character/amiya%231.png', 104, 80, 160),
      ('amiyaa#1', 'character', 'ART/art-v1/composition/character/amiyaa%231.png', 104, 80, 160),
      ('panel_source', 'image', 'ART/art-v1/composition/image/panel_source.png', 51, 70, 60),
      ('unused', 'image', 'ART/art-v1/composition/image/unused.png', 105, 80, 80);
    INSERT INTO source_arts VALUES
      ('character', 'amiya-body', 'character', 'amiya', 'body', 'default',
       'ART/art-v1/source/character/amiya-body.png', 50, 80, 160),
      ('image', 'panel_source', 'composite_panel', NULL, NULL, NULL,
       'ART/art-v1/source/image/panel_source.png', 51, 70, 60);
    INSERT INTO art_source_refs VALUES
      ('character', 'amiya', 0, 'character', 'amiya-body'),
      ('image', 'cg/part', 0, 'image', 'panel_source');
    INSERT INTO score_assets VALUES
      ('icon', 'icon-main', 'SCORE/icon/icon-main.png', 10, 64, 64),
      ('background', 'background-main', 'SCORE/background/background-main.png', 20, 1920, 1080),
      ('key_visual', 'kv-section', 'SCORE/key_visual/kv-section.png', 30, 800, 600),
      ('split', 'split-one', 'SCORE/split/split-one.png', 11, 64, 64);
    INSERT INTO score_videos VALUES
      ('video-one', 'SCORE/video/video-one.webm', 1000, 1920, 1080, 30000, 1001, 90);
    INSERT INTO media_assets VALUES
      ('audio', 'm_story', 'MEDIA/cn/audio/m_story.wav', 'audio/wav', 321, 4.5,
       NULL, NULL, NULL, NULL, NULL),
      ('video', 'video/story.mp4', 'MEDIA/cn/video/story.webm', 'video/webm', 654,
       8.25, 1920, 1080, 30000, 1001, 248);
    INSERT INTO story_collections VALUES
      ('CN', 'movement_section:section-a', 'movement_section'),
      ('CN', 'archive_group:event-a', 'archive_group'),
      ('CN', 'archive_group:encoded:组/100%', 'archive_group');
    INSERT INTO movements VALUES
      ('CN', 'movement-a', 0, 'continue', '为了明日', 'icon-main', 'missing-logo',
       'background-main', 1, 1700000000);
    INSERT INTO movement_sections VALUES
      ('CN', 'section-a', 'movement_section:section-a', 'main_theme', '方舟',
       'review-a', 0, 0, 'kv-section', NULL, NULL, NULL, NULL,
       'Main theme movement', 1);
    INSERT INTO movement_locations VALUES
      ('CN', 'movement-a', 'split-a', 0, 'mainline_split', 0, 1699999999,
       NULL, NULL, NULL, 'split-one', '序曲', 'video-one'),
      ('CN', 'movement-a', 'story-set-a', 1, 'story_set', 1, 1700000000,
       NULL, NULL, 'section-a', NULL, NULL, NULL);
    INSERT INTO archive_groups VALUES
      ('CN', 'event-a', 'archive_group:event-a', 0, '孤星', 'events', 'side_story'),
      ('CN', 'encoded:组/100%', 'archive_group:encoded:组/100%', 1,
       '编码', 'others', NULL);
    INSERT INTO stories VALUES
      ('CN', 'score-story', 'movement_section:section-a', 'before', '行动前',
       '0-1', '序幕', 'Score story', 'The opening story text.', 0),
      ('CN', 'archive-story', 'archive_group:event-a', 'after', '行动后',
       'CW-ST-1', '归航', 'Archive story', 'Archive story text.', 0),
      ('CN', 'others:activities:review-a:level_review-a_entry',
       'archive_group:encoded:组/100%',
       'before', '', '', '', '', '', 0),
      ('CN', 'others:activities:event-a:level_event-a_entry',
       'archive_group:encoded:组/100%',
       'before', '', '', '', '', '', 1);
    INSERT INTO story_art_references VALUES
      ('CN', 'score-story', 0, 'display-first', 'picture', 'image',
       'First', NULL, '["阿米娅"]'),
      ('CN', 'score-story', 1, 'amiya', 'character', 'character',
       NULL, NULL, '["阿米娅"]'),
      ('CN', 'score-story', 2, 'amiya#1', 'character', 'character',
       NULL, NULL, '["阿米娅"]'),
      ('CN', 'score-story', 3, 'amiyaa#1', 'character', 'character',
       NULL, NULL, '["错误前缀"]'),
      ('CN', 'score-story', 4, 'display-first/texture-a', 'picture', 'image',
       NULL, NULL, '[]'),
      ('CN', 'score-story', 5, 'anime-poster', 'picture', 'background',
       NULL, NULL, '[]'),
      ('CN', 'score-story', 6, 'anime-poster/texture-a', 'picture', 'image',
       NULL, NULL, '[]'),
      ('CN', 'archive-story', 0, 'missing-background', 'picture', 'background',
       NULL, NULL, '[]');
    INSERT INTO story_media_references VALUES
      ('CN', 'score-story', 0, 'm_story', 'sound'),
      ('CN', 'score-story', 1, 'video/story.mp4', 'video'),
      ('CN', 'archive-story', 0, 'missing-story-audio', 'music'),
      ('CN', 'others:activities:review-a:level_review-a_entry', 0,
       'video/story.mp4', 'video'),
      ('CN', 'others:activities:event-a:level_event-a_entry', 0,
       'video/story.mp4', 'video');
    INSERT INTO gallery_groups VALUES
      ('CN', 'score-gallery', 'movement_section:section-a', 0,
       '方舟画集', 'Score gallery', 'story-set-a'),
      ('CN', 'event-gallery', 'archive_group:event-a', 1,
       '孤星画集', 'Event gallery', NULL);
    INSERT INTO gallery_displays VALUES
      ('CN', 'score-gallery', 'display-one', 0, '牺牲火炬', 'Four siblings',
       'score-story', '0-1'),
      ('CN', 'score-gallery', 'display-two', 1, '组合画', 'Composite',
       NULL, NULL),
      ('CN', 'event-gallery', 'event-display', 0, '孤星', 'Event art',
       'archive-story', NULL);
    INSERT INTO gallery_display_artworks VALUES
      ('CN', 'score-gallery', 'display-one', 0, 'upstream-first',
       'display-first', 'image', 'none'),
      ('CN', 'score-gallery', 'display-one', 1, 'upstream-second',
       'display-second', 'image', 'none'),
      ('CN', 'score-gallery', 'display-two', 0, 'upstream-composite',
       'cg/part', 'image', 'vertical'),
      ('CN', 'event-gallery', 'event-display', 0, 'upstream-event',
       'display-second', 'image', 'none');
    INSERT INTO search_entries VALUES
      ('story:CN:score-story', 'CN', 'story', 'score-story', NULL,
       'movement_section:section-a', '序幕', '0-1', 'score-story 0-1 序幕 阿米娅 amiya',
       '{"parentKind":"movement_section","movementID":"movement-a","movementName":"为了明日","sectionID":"section-a","sectionName":"方舟"}',
       'ART/art-v1/composition/image/display-first.png'),
      ('story:CN:archive-story', 'CN', 'story', 'archive-story', NULL,
       'archive_group:event-a', '归航', 'CW-ST-1', 'archive-story CW-ST-1 归航',
       '{"parentKind":"archive_group","archiveKind":"events","groupID":"event-a","groupName":"孤星"}', NULL),
      ('movement:CN:movement-a', 'CN', 'movement', 'movement-a', NULL, NULL,
       '为了明日', 'continue', 'movement-a 为了明日 continue', NULL, NULL),
      ('section:CN:section-a', 'CN', 'section', 'section-a', NULL,
       'movement_section:section-a', '方舟', 'Main theme movement',
       'section-a 方舟 Main theme movement',
       '{"parentKind":"movement_section","movementID":"movement-a","movementName":"为了明日","sectionID":"section-a","sectionName":"方舟"}',
       'ART/art-v1/composition/image/display-first.png'),
      ('archive_group:CN:event-a', 'CN', 'archive_group', 'event-a', NULL,
       'archive_group:event-a', '孤星', 'events', 'event-a 孤星 events',
       '{"parentKind":"archive_group","archiveKind":"events","groupID":"event-a","groupName":"孤星"}', NULL),
      ('gallery:CN:score-gallery', 'CN', 'gallery', 'score-gallery', NULL,
       'movement_section:section-a', '方舟画集', 'Score gallery',
       'score-gallery 方舟画集 Score gallery',
       '{"parentKind":"movement_section","movementID":"movement-a","movementName":"为了明日","sectionID":"section-a","sectionName":"方舟"}',
       'ART/art-v1/composition/image/display-first.png'),
      ('art:CN:image:display-first', 'CN', 'art', 'display-first', 'image', NULL,
       '牺牲火炬', 'image', 'display-first image 牺牲火炬', NULL,
       'ART/art-v1/composition/image/display-first.png'),
      ('art:CN:character:amiya', 'CN', 'art', 'amiya', 'character', NULL,
       '阿米娅', 'character', 'amiya character 阿米娅', NULL,
       'ART/art-v1/composition/character/amiya.png');
    INSERT INTO gallery_display_artwork_panels VALUES
      ('CN', 'score-gallery', 'display-two', 0, 0, 'panel_source', 70, 60);
    COMMIT;
  |}

let schema () =
  match Sys.getenv_opt "ARKWAIFU_SCHEMA_PATH" with
  | None -> fixture_schema
  | Some path ->
      let channel = open_in_bin path in
      Fun.protect
        ~finally:(fun () -> close_in channel)
        (fun () -> really_input_string channel (in_channel_length channel))

let with_sqlite_fixture callback =
  let path = Filename.temp_file "arkwaifu-service-test-" ".sqlite3" in
  Fun.protect
    ~finally:(fun () -> try Sys.remove path with Sys_error _ -> ())
    (fun () ->
      let database = Sqlite3.db_open path in
      Fun.protect
        ~finally:(fun () -> ignore (Sqlite3.db_close database))
        (fun () ->
          execute database (schema ());
          execute database fixture_rows);
      callback path)

let with_database ?after callback =
  with_sqlite_fixture @@ fun path ->
  Option.iter
    (fun sql ->
      let raw = Sqlite3.db_open path in
      Fun.protect
        ~finally:(fun () -> ignore (Sqlite3.db_close raw))
        (fun () -> execute raw sql))
    after;
  match Database.sqlite path with
  | Error error -> Alcotest.failf "cannot open fixture: %s" error
  | Ok database ->
      Fun.protect
        ~finally:(fun () -> Lwt_main.run (Database.close database))
        (fun () -> callback database)

let test_art_json () =
  let art =
    Model.
      {
        id = "cg/part";
        category = "image";
        image =
          {
            object_key = "ART/v/composition/image/cg%2Fpart.png";
            byte_size = 5L;
            width = 10;
            height = 20;
          };
        source_arts = [ { id = "panel_source"; category = "image" } ];
      }
  in
  let open Yojson.Safe.Util in
  let json =
    Model.art_json ~object_base_url:"https://objects.example/bucket" art
  in
  Alcotest.(check string)
    "qualified source ID" "image"
    (json |> member "sourceArts" |> index 0 |> member "category" |> to_string);
  Alcotest.(check string)
    "composite thumbnail key"
    "https://objects.example/bucket/ART/v/thumbnail/image/cg%252Fpart.webp"
    (json |> member "thumbnailContentUrl" |> to_string)

let test_database_contract () =
  with_database @@ fun database ->
  let movements =
    Lwt_main.run (Database.movements database "CN")
    |> require_ok "movements"
  in
  let movement = List.hd movements in
  Alcotest.(check string) "movement type" "continue" movement.movement_type;
  Alcotest.(check int) "canonical section count" 1 movement.section_count;
  Alcotest.(check bool)
    "declared missing logo is retained" true
    (match movement.logo with
    | Some { id = "missing-logo"; image = None } -> true
    | _ -> false);
  let detail =
    Lwt_main.run (Database.movement database "CN" "movement-a")
    |> require_ok "movement"
  in
  Alcotest.(check int) "split and canonical section only" 2
    (List.length detail.items);
  let section_summary =
    List.find_map
      (function
        | Model.Movement_section { section; _ } -> Some section
        | Model.Movement_split _ -> None)
      detail.items
    |> Option.get
  in
  Alcotest.(check (list string)) "movement lists section entry media"
    [ "video/story.mp4" ]
    (List.map
       (fun (media : Model.story_media_reference) -> media.media_id)
       section_summary.opening_media_references);
  let section =
    Lwt_main.run
      (Database.movement_section database "CN" "movement-a" "section-a")
    |> require_ok "section"
  in
  Alcotest.(check bool)
    "latest preceding split supplies active video" true
    (match section.active_background_video with
    | Some { id = "video-one"; video = Some _ } -> true
    | _ -> false);
  Alcotest.(check (list string)) "section lists inferred entry media"
    [ "video/story.mp4" ]
    (List.map
       (fun (media : Model.story_media_reference) -> media.media_id)
       section.section.opening_media_references);
  Alcotest.(check bool)
    "section embeds gallery hierarchy" true
    (match section.gallery with
    | Some { displays = [ first; second ]; _ } ->
        List.length first.artworks = 2
        && List.length second.artworks = 1
        && (List.hd second.artworks).art_id = "cg/part"
    | _ -> false);
  let score_story =
    Lwt_main.run
      (Database.score_story database "CN" "movement-a" "section-a"
         "score-story")
    |> require_ok "score story"
  in
  Alcotest.(check string) "story text is retained" "The opening story text."
    score_story.story.text;
  Alcotest.(check (list string)) "story media keeps source order"
    [ "sound"; "video" ]
    (List.map
       (fun (media : Model.story_media_reference) -> media.kind)
       score_story.story.media_references);
  Alcotest.(check (option string)) "audio content type is decoded"
    (Some "audio/wav")
    (List.hd score_story.story.media_references).content_type;
  Alcotest.(check (option string)) "video object key is decoded"
    (Some "MEDIA/cn/video/story.webm")
    (List.nth score_story.story.media_references 1).object_key;
  let media =
    Lwt_main.run (Database.media database "video" "video/story.mp4")
    |> require_ok "media asset"
  in
  Alcotest.(check (option int)) "media width" (Some 1920) media.width;
  Alcotest.(check (option (float 0.001))) "media duration" (Some 8.25)
    media.duration;
  let archives =
    Lwt_main.run (Database.archive_index database "CN")
    |> require_ok "archive index"
  in
  Alcotest.(check int) "all archive kinds" 5 (List.length archives);
  let groups =
    Lwt_main.run (Database.archive_groups database "CN" "events")
    |> require_ok "events"
  in
  Alcotest.(check string) "event subtype" "side_story"
    (List.hd groups).group.group_type;
  let archive_group =
    Lwt_main.run (Database.archive_group database "CN" "events" "event-a")
    |> require_ok "archive group"
  in
  Alcotest.(check (list string)) "archive lists inferred entry media"
    [ "video/story.mp4" ]
    (List.map
       (fun (media : Model.story_media_reference) -> media.media_id)
       archive_group.opening_media_references);
  let source =
    Lwt_main.run (Database.source_art database "image" "panel_source")
    |> require_ok "composite source"
  in
  Alcotest.(check string) "source kind" "composite_panel" source.kind;
  let unreferenced =
    Lwt_main.run (Database.unreferenced_arts database)
    |> require_ok "unreferenced art"
  in
  Alcotest.(check (list string))
    "composition panels count as referenced" [ "unused" ]
    (List.map (fun (art : Model.unreferenced_art) -> art.id) unreferenced);
  let context =
    Lwt_main.run (Database.art_context database "CN" "character" "amiya")
    |> require_ok "character context"
  in
  Alcotest.(check (list string))
    "siblings require exact prefix before hash" [ "amiya#1" ]
    (List.map (fun (sibling : Model.art_sibling) -> sibling.art_id)
       context.siblings);
  let texture_context =
    Lwt_main.run (Database.art_context database "CN" "image" "display-first")
    |> require_ok "texture context"
  in
  Alcotest.(check (list string)) "bundle textures use the parent ID prefix"
    [ "display-first/texture-a" ]
    (List.map (fun (texture : Model.art_sibling) -> texture.art_id)
       texture_context.textures);
  Alcotest.(check bool)
    "route ownership is enforced" true
    (match
       Lwt_main.run
         (Database.archive_story database "CN" "events" "event-a"
            "score-story")
     with
    | Error `Not_found -> true
    | _ -> false);
  let search =
    Lwt_main.run (Database.search database "CN" "amiya")
    |> require_ok "search"
  in
  Alcotest.(check string) "exact artwork ID ranks first" "art"
    (List.hd search).kind;
  Alcotest.(check string) "exact artwork ID" "amiya"
    (List.hd search).id;
  Alcotest.(check bool) "story parent is decoded" true
    (match List.find_opt (fun (result : Model.search_result) -> result.kind = "story") search with
    | Some { parent = Some (Model.Score_parent { section_id = "section-a"; _ }); _ } -> true
    | _ -> false);
  let context_search =
    Lwt_main.run (Database.search database "CN" "opening story text")
    |> require_ok "story context search"
  in
  Alcotest.(check bool) "story context finds story" true
    (List.exists
       (fun (result : Model.search_result) ->
         result.kind = "story" && result.id = "score-story")
       context_search);
  Alcotest.(check bool) "story context finds artwork" true
    (List.exists
       (fun (result : Model.search_result) ->
         result.kind = "art" && result.id = "display-first")
       context_search)

let response handler target =
  Dream.test handler (Dream.request ~method_:`GET ~target "")

let head_response handler target =
  Dream.test handler (Dream.request ~method_:`HEAD ~target "")

let response_json response =
  Lwt_main.run (Dream.body response) |> Yojson.Safe.from_string

let contains text fragment =
  let length = String.length fragment in
  let rec loop position =
    if position + length > String.length text then false
    else if String.sub text position length = fragment then true
    else loop (position + 1)
  in
  length = 0 || loop 0

let test_http_contract () =
  with_database @@ fun database ->
  let handler =
    Http.routes ~database
      ~china_object_base_url:"https://cn-objects.example/bucket"
      ~object_base_url:"https://objects.example/bucket"
  in
  let scores = response handler "/api/CN/scores" in
  Alcotest.(check int) "scores status" 200
    (Dream.status scores |> Dream.status_to_int);
  Alcotest.(check (option string))
    "public CORS" (Some "*")
    (Dream.header scores "Access-Control-Allow-Origin");
  let scores_json = response_json scores in
  let open Yojson.Safe.Util in
  Alcotest.(check int)
    "score collection count" 1
    (scores_json |> index 0 |> member "sectionCount" |> to_int);
  let section =
    response handler "/api/CN/scores/movement-a/section-a"
    |> response_json
  in
  Alcotest.(check string)
    "section active video" "video-one"
    (section |> member "activeBackgroundVideo" |> member "id" |> to_string);
  Alcotest.(check string) "section entry video" "video/story.mp4"
    (section |> member "openingMedia" |> index 0 |> member "id" |> to_string);
  let anime_reference =
    section |> member "artReferences" |> to_list
    |> List.find (fun reference ->
           reference |> member "artID" |> to_string = "anime-poster")
  in
  Alcotest.(check bool) "Anime KV reference is explicit" true
    (anime_reference |> member "isAnimeKV" |> to_bool);
  let summary_story = section |> member "stories" |> to_list |> List.hd in
  Alcotest.(check bool) "story summary omits source text" true
    (summary_story |> member "text" = `Null);
  Alcotest.(check bool) "story summary omits media" true
    (summary_story |> member "media" = `Null);
  let story =
    response handler "/api/CN/scores/movement-a/section-a/score-story"
    |> response_json
  in
  Alcotest.(check string) "story detail text" "The opening story text."
    (story |> member "text" |> to_string);
  let media = story |> member "media" |> to_list in
  Alcotest.(check int) "story detail media count" 2 (List.length media);
  Alcotest.(check string) "story audio URL"
    "https://objects.example/bucket/MEDIA/cn/audio/m_story.wav"
    (List.hd media |> member "contentUrl" |> to_string);
  let media_asset =
    response handler "/api/media/video/video%2Fstory.mp4" |> response_json
  in
  Alcotest.(check string) "media detail kind" "video"
    (media_asset |> member "kind" |> to_string);
  Alcotest.(check int) "media detail width" 1920
    (media_asset |> member "width" |> to_int);
  Alcotest.(check string) "media detail URL"
    "https://objects.example/bucket/MEDIA/cn/video/story.webm"
    (media_asset |> member "contentUrl" |> to_string);
  let unresolved_story =
    response handler "/api/CN/archives/events/event-a/archive-story"
    |> response_json
  in
  Alcotest.(check bool) "unresolved story media URL is null" true
    (unresolved_story |> member "media" |> index 0 |> member "contentUrl" = `Null);
  Alcotest.(check bool) "unresolved story media type is null" true
    (unresolved_story |> member "media" |> index 0 |> member "contentType" = `Null);
  Alcotest.(check bool) "unresolved story media size is null" true
    (unresolved_story |> member "media" |> index 0 |> member "byteSize" = `Null);
  Alcotest.(check int)
    "embedded sibling displays" 2
    (section |> member "gallery" |> member "displays" |> to_list |> List.length);
  let archive =
    response handler "/api/CN/archives/events/event-a" |> response_json
  in
  Alcotest.(check string) "archive route kind" "events"
    (archive |> member "kind" |> to_string);
  Alcotest.(check string) "archive entry video" "video/story.mp4"
    (archive |> member "openingMedia" |> index 0 |> member "id" |> to_string);
  let texture_context =
    response handler "/api/CN/arts/image/display-first/context" |> response_json
  in
  Alcotest.(check string) "art context texture"
    "display-first/texture-a"
    (texture_context |> member "textures" |> index 0 |> member "artID"
   |> to_string);
  let gallery_index =
    response handler "/api/CN/galleries" |> response_json |> to_list
  in
  let score_gallery =
    List.find
      (fun value -> value |> member "id" |> to_string = "score-gallery")
      gallery_index
  in
  let previews =
    score_gallery |> member "previewThumbnailContentUrls" |> to_list
    |> List.map to_string
  in
  Alcotest.(check int) "one preview per distinct display" 2
    (List.length previews);
  Alcotest.(check bool) "first sibling selected" true
    (contains (List.hd previews) "display-first.webp");
  Alcotest.(check bool) "later sibling is not selected" false
    (List.exists (fun url -> contains url "display-second.webp") previews);
  let composite = response handler "/api/arts/image/cg%2Fpart" in
  Alcotest.(check int) "encoded composite art ID" 200
    (Dream.status composite |> Dream.status_to_int);
  let source = response handler "/api/source-arts/image/panel_source" in
  Alcotest.(check int) "category-qualified source art" 200
    (Dream.status source |> Dream.status_to_int);
  let search = response handler "/api/CN/search?q=amiya" |> response_json |> to_list in
  Alcotest.(check bool) "search returns ranked artwork" true
    (search |> List.hd |> member "kind" |> to_string = "art");
  Alcotest.(check string) "search result thumbnail"
    "https://objects.example/bucket/ART/art-v1/thumbnail/character/amiya.webp"
    (search |> List.hd |> member "thumbnailContentUrl" |> to_string);
  let mirror_art =
    Dream.test handler
      (Dream.request ~method_:`GET
         ~headers:[ ("X-Forwarded-Host", "api.cn.arkwaifu.cc") ]
         ~target:"/api/arts/character/amiya" "")
    |> response_json
  in
  Alcotest.(check string)
    "China mirror object origin"
    "https://cn-objects.example/bucket/ART/art-v1/composition/character/amiya.png"
    (mirror_art |> member "image" |> member "contentUrl" |> to_string);
  let preflight =
    Dream.test handler
      (Dream.request ~method_:`OPTIONS
         ~target:"/api/CN/scores/movement-a/section-a/score-story" "")
  in
  Alcotest.(check int) "preflight status" 204
    (Dream.status preflight |> Dream.status_to_int);
  List.iter
    (fun target ->
      Alcotest.(check int)
        ("legacy route absent: " ^ target) 404
        (Dream.status (response handler target) |> Dream.status_to_int))
    [
      "/api/CN/story-groups";
      "/api/CN/stories/score-story";
      "/api/source-arts/amiya-body";
    ];
  let sitemap_response = response handler "/sitemap.txt" in
  let sitemap = Lwt_main.run (Dream.body sitemap_response) in
  let sitemap_head = head_response handler "/sitemap.txt" in
  Alcotest.(check int) "sitemap HEAD status" 200
    (Dream.status sitemap_head |> Dream.status_to_int);
  Alcotest.(check (option string)) "sitemap HEAD content type"
    (Some "text/plain; charset=utf-8")
    (Dream.header sitemap_head "Content-Type");
  Alcotest.(check bool) "sitemap has Score section" true
    (contains sitemap "/CN/scores/movement-a/section-a");
  Alcotest.(check bool) "sitemap has Archive group" true
    (contains sitemap "/CN/archives/events/event-a");
  Alcotest.(check bool) "sitemap encodes one route segment" true
    (contains sitemap
       "/CN/archives/others/encoded%3A%E7%BB%84%2F100%25");
  Alcotest.(check bool) "sitemap has no legacy stories" false
    (contains sitemap "/stories/")

let test_http_invalid_composition_key () =
  with_database
    ~after:
      "UPDATE arts SET object_key = 'malformed.png' WHERE category = 'character' AND art_id = 'amiya'"
  @@ fun database ->
  let handler =
    Http.routes ~database ~object_base_url:"https://objects.example/bucket"
  in
  let result = response handler "/api/arts/character/amiya" in
  Alcotest.(check int) "invalid composition key status" 503
    (Dream.status result |> Dream.status_to_int);
  Alcotest.(check string)
    "metadata error body" {|{"error":"service_unavailable"}|}
    (Lwt_main.run (Dream.body result));
  Alcotest.(check (option string))
    "metadata error CORS" (Some "*")
    (Dream.header result "Access-Control-Allow-Origin")

let copy_file source destination =
  let input = open_in_bin source in
  Fun.protect
    ~finally:(fun () -> close_in input)
    (fun () ->
      let output = open_out_bin destination in
      Fun.protect
        ~finally:(fun () -> close_out output)
        (fun () ->
          let buffer = Bytes.create 65_536 in
          let rec copy () =
            match Stdlib.input input buffer 0 (Bytes.length buffer) with
            | 0 -> ()
            | count ->
                Stdlib.output output buffer 0 count;
                copy ()
          in
          copy ()))

let rec remove_directory path =
  if Sys.file_exists path then (
    Sys.readdir path
    |> Array.iter (fun name ->
           let child = Filename.concat path name in
           if Sys.is_directory child then remove_directory child
           else try Sys.remove child with Sys_error _ -> ());
    try Unix.rmdir path with Unix.Unix_error _ -> ())

let with_temporary_directory callback =
  let placeholder = Filename.temp_file "arkwaifu-service-cache-" ".dir" in
  Sys.remove placeholder;
  Unix.mkdir placeholder 0o750;
  Fun.protect ~finally:(fun () -> remove_directory placeholder) (fun () ->
      callback placeholder)

let cache_generations path =
  Sys.readdir path |> Array.to_list
  |> List.filter (fun name -> String.ends_with ~suffix:".sqlite3" name)

let test_live_refresh () =
  with_sqlite_fixture @@ fun source ->
  with_temporary_directory @@ fun cache_dir ->
  let responses =
    ref
      [
        `Database (Some "generation-1");
        `Not_modified;
        `Database (Some "generation-2");
        `Invalid;
      ]
  in
  let seen_etags = ref [] in
  let fetch ~etag ~destination =
    seen_etags := etag :: !seen_etags;
    match !responses with
    | [] -> Lwt.return (`Failed "unexpected fetch")
    | response :: rest -> (
        responses := rest;
        match response with
        | `Not_modified -> Lwt.return `Not_modified
        | `Database etag ->
            copy_file source destination;
            Lwt.return (`Fetched etag)
        | `Invalid ->
            copy_file source destination;
            let raw = Sqlite3.db_open destination in
            Fun.protect
              ~finally:(fun () -> ignore (Sqlite3.db_close raw))
              (fun () -> execute raw "PRAGMA user_version = 1");
            Lwt.return (`Fetched (Some "invalid")))
  in
  match
    Lwt_main.run
      (Database.For_test.live ~fetch ~cache_dir ~download_timeout_seconds:5.)
  with
  | Error error -> Alcotest.failf "cannot start live reader: %s" error
  | Ok controlled ->
      Alcotest.(check int) "one initial generation" 1
        (List.length (cache_generations cache_dir));
      Alcotest.(check bool)
        "not modified preserves generation" true
        (match Lwt_main.run (controlled.refresh_once ()) with
        | `Not_modified -> true
        | _ -> false);
      Alcotest.(check bool)
        "valid refresh replaces generation" true
        (match Lwt_main.run (controlled.refresh_once ()) with
        | `Replaced -> true
        | _ -> false);
      Alcotest.(check int) "retired generation removed" 1
        (List.length (cache_generations cache_dir));
      Alcotest.(check bool)
        "invalid schema refresh fails" true
        (match Lwt_main.run (controlled.refresh_once ()) with
        | `Failed _ -> true
        | _ -> false);
      Lwt_main.run (Database.movements controlled.database "CN")
      |> require_ok "movement after rejected refresh" |> ignore;
      Alcotest.(check (list (option string)))
        "etag changes only after replacement"
        [ None; Some "generation-1"; Some "generation-1"; Some "generation-2" ]
        (List.rev !seen_etags);
      Lwt_main.run (Database.close controlled.database);
      Alcotest.(check (list string))
        "close removes current generation" [] (cache_generations cache_dir)

let test_live_rejects_initial_schema () =
  with_sqlite_fixture @@ fun source ->
  with_temporary_directory @@ fun cache_dir ->
  let fetch ~etag:_ ~destination =
    copy_file source destination;
    let raw = Sqlite3.db_open destination in
    Fun.protect
      ~finally:(fun () -> ignore (Sqlite3.db_close raw))
      (fun () -> execute raw "PRAGMA user_version = 1");
    Lwt.return (`Fetched None)
  in
  Alcotest.(check bool)
    "unsupported schema fails startup" true
    (Result.is_error
       (Lwt_main.run
          (Database.For_test.live ~fetch ~cache_dir
             ~download_timeout_seconds:5.)))

let test_live_rejects_missing_required_schema () =
  with_sqlite_fixture @@ fun source ->
  with_temporary_directory @@ fun cache_dir ->
  let fetch ~etag:_ ~destination =
    copy_file source destination;
    let raw = Sqlite3.db_open destination in
    Fun.protect
      ~finally:(fun () -> ignore (Sqlite3.db_close raw))
      (fun () -> execute raw "DROP TABLE unit_versions");
    Lwt.return (`Fetched None)
  in
  Alcotest.(check bool)
    "missing required schema fails startup" true
    (Result.is_error
       (Lwt_main.run
          (Database.For_test.live ~fetch ~cache_dir
             ~download_timeout_seconds:5.)))

let test_refreshes_are_serialized () =
  with_sqlite_fixture @@ fun source ->
  with_temporary_directory @@ fun cache_dir ->
  let active = ref 0 in
  let maximum_active = ref 0 in
  let fetch ~etag:_ ~destination =
    incr active;
    maximum_active := max !maximum_active !active;
    copy_file source destination;
    Lwt.pause () >|= fun () ->
    decr active;
    `Fetched None
  in
  match
    Lwt_main.run
      (Database.For_test.live ~fetch ~cache_dir ~download_timeout_seconds:5.)
  with
  | Error error -> Alcotest.failf "cannot start serialized reader: %s" error
  | Ok controlled ->
      maximum_active := 0;
      let left = controlled.refresh_once ()
      and right = controlled.refresh_once () in
      Lwt_main.run (Lwt.both left right) |> ignore;
      Alcotest.(check int) "one fetch at a time" 1 !maximum_active;
      Lwt_main.run (Database.close controlled.database)

let () =
  Alcotest.run "arkwaifu-service"
    [
      ("config", [ Alcotest.test_case "HTTP URLs" `Quick test_config_urls ]);
      ("model", [ Alcotest.test_case "art JSON" `Quick test_art_json ]);
      ( "database",
        [
          Alcotest.test_case "Score and Archive contract" `Quick
            test_database_contract;
          Alcotest.test_case "live refresh" `Quick test_live_refresh;
          Alcotest.test_case "schema rejection" `Quick
            test_live_rejects_initial_schema;
          Alcotest.test_case "required schema rejection" `Quick
            test_live_rejects_missing_required_schema;
          Alcotest.test_case "serialized refresh" `Quick
            test_refreshes_are_serialized;
        ] );
      ( "http",
        [
          Alcotest.test_case "clean routes" `Quick test_http_contract;
          Alcotest.test_case "invalid composition key" `Quick
            test_http_invalid_composition_key;
        ] );
    ]
