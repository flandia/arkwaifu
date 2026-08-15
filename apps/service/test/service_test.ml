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
      position INTEGER NOT NULL, PRIMARY KEY(locale, story_id));
    CREATE TABLE story_art_references (locale TEXT NOT NULL, story_id TEXT NOT NULL,
      position INTEGER NOT NULL, art_id TEXT NOT NULL, kind TEXT NOT NULL,
      category TEXT NOT NULL, title TEXT, subtitle TEXT, names_json TEXT NOT NULL,
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
      panel_art_id TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
      PRIMARY KEY(locale, gallery_id, display_id, artwork_position, position));
    PRAGMA user_version = 2;
    COMMIT;
  |}

let fixture_rows =
  {|
    BEGIN;
    INSERT INTO unit_versions VALUES ('art', 'art-v1'), ('CN', 'cn-v1');
    INSERT INTO arts VALUES
      ('display-first', 'image', 'ART/art-v1/composition/image/display-first.png', 101, 100, 60),
      ('display-second', 'image', 'ART/art-v1/composition/image/display-second.png', 102, 100, 60),
      ('cg/part', 'image', 'ART/art-v1/composition/image/cg%2Fpart.png', 103, 70, 120),
      ('amiya', 'character', 'ART/art-v1/composition/character/amiya.png', 104, 80, 160),
      ('amiya#1', 'character', 'ART/art-v1/composition/character/amiya%231.png', 104, 80, 160),
      ('amiyaa#1', 'character', 'ART/art-v1/composition/character/amiyaa%231.png', 104, 80, 160),
      ('panel/source', 'image', 'ART/art-v1/composition/image/panel%2Fsource.png', 51, 70, 60),
      ('unused', 'image', 'ART/art-v1/composition/image/unused.png', 105, 80, 80);
    INSERT INTO source_arts VALUES
      ('character', 'amiya-body', 'character', 'amiya', 'body', 'default',
       'ART/art-v1/source/character/amiya-body.png', 50, 80, 160),
      ('image', 'panel/source', 'composite_panel', NULL, NULL, NULL,
       'ART/art-v1/source/image/panel%2Fsource.png', 51, 70, 60);
    INSERT INTO art_source_refs VALUES
      ('character', 'amiya', 0, 'character', 'amiya-body'),
      ('image', 'cg/part', 0, 'image', 'panel/source');
    INSERT INTO score_assets VALUES
      ('icon', 'icon-main', 'SCORE/icon/icon-main.png', 10, 64, 64),
      ('background', 'background-main', 'SCORE/background/background-main.png', 20, 1920, 1080),
      ('key_visual', 'kv-section', 'SCORE/key_visual/kv-section.png', 30, 800, 600),
      ('split', 'split-one', 'SCORE/split/split-one.png', 11, 64, 64);
    INSERT INTO score_videos VALUES
      ('video-one', 'SCORE/video/video-one.webm', 1000, 1920, 1080, 30000, 1001, 90);
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
       '0-1', '序幕', 'Score story', 0),
      ('CN', 'archive-story', 'archive_group:event-a', 'after', '行动后',
       'CW-ST-1', '归航', 'Archive story', 0);
    INSERT INTO story_art_references VALUES
      ('CN', 'score-story', 0, 'display-first', 'picture', 'image',
       'First', NULL, '["阿米娅"]'),
      ('CN', 'score-story', 1, 'amiya', 'character', 'character',
       NULL, NULL, '["阿米娅"]'),
      ('CN', 'score-story', 2, 'amiya#1', 'character', 'character',
       NULL, NULL, '["阿米娅"]'),
      ('CN', 'score-story', 3, 'amiyaa#1', 'character', 'character',
       NULL, NULL, '["错误前缀"]'),
      ('CN', 'archive-story', 0, 'missing-background', 'picture', 'background',
       NULL, NULL, '[]');
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
    INSERT INTO gallery_display_artwork_panels VALUES
      ('CN', 'score-gallery', 'display-two', 0, 0, 'panel/source', 70, 60);
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
        source_arts = [ { id = "panel/source"; category = "image" } ];
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
  Alcotest.(check bool)
    "section embeds gallery hierarchy" true
    (match section.gallery with
    | Some { displays = [ first; second ]; _ } ->
        List.length first.artworks = 2
        && List.length second.artworks = 1
        && (List.hd second.artworks).art_id = "cg/part"
    | _ -> false);
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
  let source =
    Lwt_main.run (Database.source_art database "image" "panel/source")
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
  Alcotest.(check bool)
    "route ownership is enforced" true
    (match
       Lwt_main.run
         (Database.archive_story database "CN" "events" "event-a"
            "score-story")
     with
    | Error `Not_found -> true
    | _ -> false)

let response handler target =
  Dream.test handler (Dream.request ~method_:`GET ~target "")

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
  Alcotest.(check int)
    "embedded sibling displays" 2
    (section |> member "gallery" |> member "displays" |> to_list |> List.length);
  let archive =
    response handler "/api/CN/archives/events/event-a" |> response_json
  in
  Alcotest.(check string) "archive route kind" "events"
    (archive |> member "kind" |> to_string);
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
  let source = response handler "/api/source-arts/image/panel%2Fsource" in
  Alcotest.(check int) "category-qualified source art" 200
    (Dream.status source |> Dream.status_to_int);
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
