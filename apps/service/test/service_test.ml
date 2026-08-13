open Arkwaifu_service

let image =
  Model.
    {
      object_key =
        "ART/26-08-07-10-51-39_26e0fc/composition/character/event.png";
      byte_size = 42L;
      width = 10;
      height = 20;
    }

let art =
  Model.
    {
      id = "event";
      category = "character";
      image;
      source_art_ids = [ "source" ];
    }

let source_image =
  Model.
    {
      object_key = "ART/26-08-07-10-51-39_26e0fc/source/character/source.png";
      byte_size = 43L;
      width = 11;
      height = 21;
    }

let source_art =
  Model.
    {
      id = "source";
      character_id = "character";
      role = "body";
      variant = "1";
      image = source_image;
    }

let require_ok label = function
  | Ok value -> value
  | Error `Not_found ->
      Alcotest.failf "%s unexpectedly returned not found" label
  | Error (`Unavailable error) ->
      Alcotest.failf "%s unavailable: %s" label error

let test_art_json () =
  let json =
    Model.art_json ~object_base_url:"https://objects.example/bucket/" art
  in
  let open Yojson.Safe.Util in
  Alcotest.(check string) "id" "event" (json |> member "id" |> to_string);
  Alcotest.(check string)
    "content URL"
    "https://objects.example/bucket/ART/26-08-07-10-51-39_26e0fc/composition/character/event.png"
    (json |> member "image" |> member "contentUrl" |> to_string);
  Alcotest.(check string)
    "direct thumbnail URL"
    "https://objects.example/bucket/ART/26-08-07-10-51-39_26e0fc/thumbnail/character/event.webp"
    (json |> member "thumbnailContentUrl" |> to_string);
  Alcotest.(check bool)
    "SHA-256 absent" true
    (json |> member "image" |> member "sha256" = `Null)

let test_source_art_json () =
  let json =
    Model.source_art_json ~object_base_url:"https://objects.example/bucket/"
      source_art
  in
  let open Yojson.Safe.Util in
  Alcotest.(check string)
    "content URL"
    "https://objects.example/bucket/ART/26-08-07-10-51-39_26e0fc/source/character/source.png"
    (json |> member "image" |> member "contentUrl" |> to_string)

let test_content_url_escapes_encoded_key () =
  Alcotest.(check string)
    "literal percent escape"
    "https://objects.example/bucket/art/source/id%253Avariant/hash.png"
    (Model.content_url ~object_base_url:"https://objects.example/bucket/"
       "art/source/id%3Avariant/hash.png")

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
  Unix.unsetenv "ARKWAIFU_DATABASE_URL";
  let default_config =
    match Config.load () with
    | Ok value -> value
    | Error error ->
        Alcotest.failf "default database URL was rejected: %s" error
  in
  Alcotest.(check string)
    "default database URL" "https://objects.example/bucket/arkwaifu.sqlite3"
    (Uri.to_string default_config.database_url);
  Unix.putenv "ARKWAIFU_DATABASE_URL" "";
  Alcotest.(check bool)
    "empty database URL is rejected" true
    (Result.is_error (Config.load ()));
  Unix.putenv "ARKWAIFU_DATABASE_URL" "ftp://database.example/archive.sqlite3";
  Alcotest.(check bool)
    "non-HTTP database URL is rejected" true
    (Result.is_error (Config.load ()));
  Unix.putenv "ARKWAIFU_DATABASE_URL"
    "https://database.example/arkwaifu.sqlite3";
  Unix.putenv "ARKWAIFU_OBJECT_BASE_URL" "file:///objects";
  Alcotest.(check bool)
    "non-HTTP object base URL is rejected" true
    (Result.is_error (Config.load ()));
  Unix.putenv "ARKWAIFU_OBJECT_BASE_URL" "";
  Alcotest.(check bool)
    "empty object base URL is rejected" true
    (Result.is_error (Config.load ()))

(* This is a reader fixture, not a copy of the updater-owned production schema. *)
let reader_fixture_schema =
  {|
    PRAGMA foreign_keys = ON;

    CREATE TABLE unit_versions (
      unit TEXT PRIMARY KEY,
      res_version TEXT NOT NULL
    );

    CREATE TABLE arts (
      art_id TEXT NOT NULL,
      category TEXT NOT NULL,
      object_key TEXT NOT NULL,
      byte_size INTEGER NOT NULL,
      width INTEGER NOT NULL,
      height INTEGER NOT NULL,
      PRIMARY KEY (category, art_id)
    );

    CREATE TABLE source_arts (
      source_art_id TEXT PRIMARY KEY,
      character_id TEXT NOT NULL,
      role TEXT NOT NULL,
      variant TEXT NOT NULL,
      object_key TEXT NOT NULL,
      byte_size INTEGER NOT NULL,
      width INTEGER NOT NULL,
      height INTEGER NOT NULL
    );

    CREATE TABLE art_source_refs (
      category TEXT NOT NULL,
      art_id TEXT NOT NULL,
      position INTEGER NOT NULL,
      source_art_id TEXT NOT NULL REFERENCES source_arts (source_art_id),
      PRIMARY KEY (category, art_id, position),
      FOREIGN KEY (category, art_id) REFERENCES arts (category, art_id)
    );

    CREATE TABLE story_groups (
      locale TEXT NOT NULL REFERENCES unit_versions (unit),
      group_id TEXT NOT NULL,
      name TEXT NOT NULL,
      group_type TEXT NOT NULL,
      position INTEGER NOT NULL,
      PRIMARY KEY (locale, group_id)
    );

    CREATE TABLE stories (
      locale TEXT NOT NULL,
      story_id TEXT NOT NULL,
      group_id TEXT NOT NULL,
      tag TEXT NOT NULL,
      tag_text TEXT NOT NULL,
      code TEXT NOT NULL,
      name TEXT NOT NULL,
      info TEXT NOT NULL,
      position INTEGER NOT NULL,
      PRIMARY KEY (locale, story_id),
      FOREIGN KEY (locale, group_id) REFERENCES story_groups (locale, group_id)
    );

    CREATE TABLE story_art_references (
      locale TEXT NOT NULL,
      story_id TEXT NOT NULL,
      position INTEGER NOT NULL,
      art_id TEXT NOT NULL,
      kind TEXT NOT NULL,
      category TEXT NOT NULL,
      title TEXT,
      subtitle TEXT,
      names_json TEXT NOT NULL,
      PRIMARY KEY (locale, story_id, position),
      FOREIGN KEY (locale, story_id) REFERENCES stories (locale, story_id)
    );

    CREATE TABLE galleries (
      locale TEXT NOT NULL REFERENCES unit_versions (unit),
      gallery_id TEXT NOT NULL,
      name TEXT NOT NULL,
      description TEXT NOT NULL,
      PRIMARY KEY (locale, gallery_id)
    );

    CREATE TABLE gallery_entries (
      locale TEXT NOT NULL,
      gallery_id TEXT NOT NULL,
      position INTEGER NOT NULL,
      entry_id TEXT NOT NULL,
      name TEXT NOT NULL,
      description TEXT NOT NULL,
      art_id TEXT NOT NULL,
      category TEXT NOT NULL,
      PRIMARY KEY (locale, gallery_id, entry_id),
      FOREIGN KEY (locale, gallery_id) REFERENCES galleries (locale, gallery_id)
    );

    PRAGMA user_version = 2;
  |}

let read_file path =
  let channel = open_in_bin path in
  Fun.protect
    ~finally:(fun () -> close_in channel)
    (fun () -> really_input_string channel (in_channel_length channel))

let sqlite_schema () =
  match Sys.getenv_opt "ARKWAIFU_SCHEMA_PATH" with
  | Some path -> read_file path
  | None -> reader_fixture_schema

let sqlite_rows =
  {|
    INSERT INTO unit_versions VALUES
      ('art', 'art-v1'), ('CN', 'cn-v1'), ('EN', 'en-v1');
    INSERT INTO arts
      VALUES ('event', 'character',
              'ART/art-v1/composition/character/event.png', 42, 10, 20);
    INSERT INTO arts VALUES
      ('illustration', 'image',
       'ART/art-v1/composition/image/illustration.png', 44, 1920, 1080),
      ('alternate', 'image',
       'ART/art-v1/composition/image/alternate.png', 44, 1920, 1080),
      ('third', 'image',
       'ART/art-v1/composition/image/third.png', 44, 1920, 1080),
      ('fourth', 'image',
       'ART/art-v1/composition/image/fourth.png', 44, 1920, 1080),
      ('background', 'background',
       'ART/art-v1/composition/background/background.png', 44, 1920, 1080),
      ('event#1$1', 'character',
       'ART/art-v1/composition/character/event#1$1.png', 44, 1000, 1000),
      ('event#2$2', 'character',
       'ART/art-v1/composition/character/event#2$2.png', 44, 1000, 1000),
      ('eventual#1$1', 'character',
       'ART/art-v1/composition/character/eventual#1$1.png', 44, 1000, 1000);
    INSERT INTO source_arts
      VALUES ('source', 'character', 'body', '1',
              'ART/art-v1/source/character/source.png', 43, 11, 21);
    INSERT INTO art_source_refs VALUES ('character', 'event', 0, 'source');
    INSERT INTO story_groups VALUES
      ('CN', 'group', 'Group', 'main_story', 0),
      ('CN', 'other', 'Other', 'major_event', 1),
      ('CN', 'minor-event', 'Minor event', 'minor_event', 2),
      ('CN', 'operator-record', 'Operator record', 'operator_record', 3),
      ('CN', 'integrated-strategies', 'Integrated Strategies',
       'integrated_strategies', 4),
      ('CN', 'reclamation-algorithm', 'Reclamation Algorithm',
       'reclamation_algorithm', 5),
      ('CN', 'empty', 'Empty group', 'others', 6),
      ('EN', 'encoded:组/100%', 'Encoded group', 'others', 0);
    INSERT INTO stories
      VALUES ('CN', 'story', 'group', 'before', 'Before', 'S1', 'Story', 'Info', 0);
    INSERT INTO stories
      VALUES ('CN', 'aaa-later', 'group', 'after', 'After', 'S2', 'Later story',
              'Later info', 1);
    INSERT INTO stories
      VALUES ('CN', 'background-only', 'group', 'after', 'After', 'S3',
              'Background story', 'Background info', 2);
    INSERT INTO stories
      VALUES ('CN', 'other-story', 'other', 'after', 'After', 'OS1',
              'Other story', 'Other info', 0);
    INSERT INTO story_art_references
      VALUES
        ('CN', 'story', 0, 'background', 'picture', 'background', NULL, NULL,
         '[]'),
        ('CN', 'story', 1, 'illustration', 'picture', 'image', 'Title', NULL,
         '["Alias"]'),
        ('CN', 'story', 2, 'alternate', 'picture', 'image', 'Alternate', NULL,
         '[]'),
        ('CN', 'story', 3, 'third', 'picture', 'image', 'Third', NULL, '[]'),
        ('CN', 'story', 4, 'fourth', 'picture', 'image', 'Fourth', NULL, '[]'),
        ('CN', 'story', 5, 'unavailable', 'picture', 'image', 'Unavailable', NULL,
         '[]'),
        ('CN', 'aaa-later', 0, 'illustration', 'picture', 'image', 'Title', NULL,
         '["Alias"]'),
        ('CN', 'background-only', 0, 'background', 'picture', 'background', NULL,
         NULL, '[]'),
        ('CN', 'other-story', 0, 'illustration', 'picture', 'image', 'Title',
         NULL, '[]'),
        ('CN', 'other-story', 1, 'event', 'character', 'character', NULL, NULL,
         '["安洁莉娜"]'),
        ('CN', 'other-story', 2, 'event', 'character', 'character', NULL, NULL,
         '["Angelina","安洁莉娜"]'),
        ('CN', 'other-story', 3, 'event#1$1', 'character', 'character', NULL,
         NULL, '["安洁莉娜（异格）"]');
    INSERT INTO galleries VALUES
      ('CN', 'gallery', 'Gallery', 'Description'),
      ('CN', 'background-gallery', 'Background gallery', 'Description'),
      ('EN', 'foreign-gallery', 'Foreign gallery', 'Description');
    INSERT INTO gallery_entries
      VALUES
        ('CN', 'gallery', 0, 'entry', 'Entry', 'Entry description',
         'event', 'character'),
        ('CN', 'gallery', 1, 'background', 'Background', 'Description',
         'background', 'background'),
        ('CN', 'gallery', 2, 'illustration', 'Illustration', 'Description',
         'illustration', 'image'),
        ('CN', 'gallery', 3, 'alternate', 'Alternate', 'Description',
         'alternate', 'image'),
        ('CN', 'gallery', 4, 'third', 'Third', 'Description', 'third', 'image'),
        ('CN', 'gallery', 5, 'fourth', 'Fourth', 'Description', 'fourth', 'image'),
        ('CN', 'background-gallery', 0, 'background', 'Background',
         'Description', 'background', 'background'),
        ('EN', 'foreign-gallery', 0, 'foreign', 'Foreign', 'Description',
         'event#2$2', 'character');
  |}

let create_sqlite_fixture ?(after = "") path =
  let database = Sqlite3.db_open path in
  Fun.protect
    ~finally:(fun () -> ignore (Sqlite3.db_close database))
    (fun () ->
      Sqlite3.Rc.check (Sqlite3.exec database (sqlite_schema ()));
      Sqlite3.Rc.check (Sqlite3.exec database sqlite_rows);
      if not (String.equal after "") then
        Sqlite3.Rc.check (Sqlite3.exec database after))

let with_sqlite_fixture ?after callback =
  let path = Filename.temp_file "arkwaifu-service-test-" ".sqlite3" in
  Fun.protect
    ~finally:(fun () -> try Sys.remove path with Sys_error _ -> ())
    (fun () ->
      create_sqlite_fixture ?after path;
      callback path)

let with_sqlite_database ?after callback =
  with_sqlite_fixture ?after (fun path ->
      match Database.sqlite path with
      | Ok database ->
          Fun.protect
            ~finally:(fun () -> Lwt_main.run (Database.close database))
            (fun () -> callback database)
      | Error error -> Alcotest.failf "cannot open SQLite fixture: %s" error)

let test_story_group_uses_one_pool_acquisition () =
  with_sqlite_fixture (fun path ->
      let acquisitions = ref 0 in
      match
        Database.For_test.sqlite_with_pool_observer
          ~on_acquire:(fun () -> incr acquisitions)
          path
      with
      | Error error -> Alcotest.failf "cannot open SQLite fixture: %s" error
      | Ok database ->
          Fun.protect
            ~finally:(fun () -> Lwt_main.run (Database.close database))
            (fun () ->
              Lwt_main.run (Database.story_group database "CN" "group")
              |> require_ok "story group detail"
              |> ignore;
              Alcotest.(check int)
                "one request holds one generation" 1 !acquisitions))

let test_sqlite_database () =
  with_sqlite_database (fun database ->
      Lwt_main.run (Database.health database) |> require_ok "health";
      let art =
        Lwt_main.run (Database.art database "character" "event")
        |> require_ok "art"
      in
      Alcotest.(check string) "art category" "character" art.category;
      Alcotest.(check (list string))
        "source IDs" [ "source" ] art.source_art_ids;
      Alcotest.(check int64) "art bytes" 42L art.image.byte_size;

      let source =
        Lwt_main.run (Database.source_art database "source")
        |> require_ok "source art"
      in
      Alcotest.(check string) "source character" "character" source.character_id;
      Alcotest.(check string) "source role" "body" source.role;
      Alcotest.(check int) "source width" 11 source.image.width;

      let unreferenced =
        Lwt_main.run (Database.unreferenced_arts database)
        |> require_ok "unreferenced art"
      in
      Alcotest.(check (list (pair string string)))
        "unreferenced art excludes story and gallery references in every locale"
        [ ("character", "eventual#1$1") ]
        (List.map
           (fun (art : Model.unreferenced_art) -> (art.category, art.id))
           unreferenced);

      let groups =
        Lwt_main.run (Database.story_groups database "CN")
        |> require_ok "story groups"
      in
      Alcotest.(check (list string))
        "story group IDs"
        [
          "group";
          "other";
          "minor-event";
          "operator-record";
          "integrated-strategies";
          "reclamation-algorithm";
          "empty";
        ]
        (List.map
           (fun (summary : Model.story_group_summary) -> summary.group.id)
           groups);
      Alcotest.(check (list string))
        "story group type contract"
        [
          "main_story";
          "major_event";
          "minor_event";
          "operator_record";
          "integrated_strategies";
          "reclamation_algorithm";
          "others";
        ]
        (List.map
           (fun (summary : Model.story_group_summary) ->
             summary.group.group_type)
           groups);
      Alcotest.(check bool)
        "group representative prefers image" true
        (match groups with
        | { representative_art_reference = Some reference; _ } :: _ ->
            String.equal reference.category "image"
        | _ -> false);
      Alcotest.(check (list string))
        "group previews contain three illustrations"
        [ "image"; "image"; "image" ]
        (match groups with
        | { preview_art_references; _ } :: _ ->
            List.map
              (fun (reference : Model.story_art_reference) ->
                reference.category)
              preview_art_references
        | _ -> []);
      Alcotest.(check bool)
        "group preview prioritizes illustrations unique to its group" true
        (match groups with
        | { preview_art_references; _ } :: _ ->
            not
              (List.exists
                 (fun (reference : Model.story_art_reference) ->
                   String.equal reference.art_id "illustration")
                 preview_art_references)
        | _ -> false);

      let stories =
        Lwt_main.run (Database.stories_by_group database "CN" "group")
        |> require_ok "stories by group"
      in
      Alcotest.(check (list string))
        "story summary IDs"
        [ "story"; "aaa-later"; "background-only" ]
        (List.map
           (fun (summary : Model.story_summary) -> summary.story.id)
           stories);
      Alcotest.(check bool)
        "story summaries have empty references" true
        (List.for_all
           (fun (summary : Model.story_summary) ->
             summary.story.art_references = [])
           stories);
      Alcotest.(check (list string))
        "story previews prefer illustrations and fall back to backgrounds"
        [ "image"; "image"; "background" ]
        (List.map
           (fun (summary : Model.story_summary) ->
             match summary.preview_art_references with
             | reference :: _ -> reference.category
             | [] -> "missing")
           stories);
      Alcotest.(check int)
        "story preview cap" 3
        (match stories with
        | summary :: _ -> List.length summary.preview_art_references
        | [] -> 0);
      Alcotest.(check bool)
        "story preview prioritizes illustrations unique to its story" true
        (match stories with
        | summary :: _ ->
            not
              (List.exists
                 (fun (reference : Model.story_art_reference) ->
                   String.equal reference.art_id "illustration")
                 summary.preview_art_references)
        | [] -> false);
      Alcotest.(check (list string))
        "existing empty story group" []
        (Lwt_main.run (Database.stories_by_group database "CN" "empty")
        |> require_ok "empty stories by group"
        |> List.map (fun (summary : Model.story_summary) -> summary.story.id));
      Alcotest.(check bool)
        "missing story group" true
        (match
           Lwt_main.run (Database.stories_by_group database "CN" "missing")
         with
        | Error `Not_found -> true
        | _ -> false);

      let group_detail =
        Lwt_main.run (Database.story_group database "CN" "group")
        |> require_ok "story group detail"
      in
      Alcotest.(check (list string))
        "group detail art IDs"
        [ "background"; "illustration"; "alternate"; "third"; "fourth" ]
        (List.map
           (fun (reference : Model.story_art_reference) -> reference.art_id)
           group_detail.art_references);
      Alcotest.(check (list string))
        "group detail uses the rarity-ranked index previews"
        (match groups with
        | summary :: _ ->
            List.map
              (fun (reference : Model.story_art_reference) -> reference.art_id)
              summary.preview_art_references
        | [] -> [])
        (List.map
           (fun (reference : Model.story_art_reference) -> reference.art_id)
           group_detail.preview_art_references);
      Alcotest.(check bool)
        "empty group detail" true
        (match
           Lwt_main.run (Database.story_group database "CN" "empty")
           |> require_ok "empty story group detail"
         with
        | {
         representative_art_reference = None;
         preview_art_references = [];
         art_references = [];
         _;
        } ->
            true
        | _ -> false);
      Alcotest.(check bool)
        "missing group detail" true
        (match Lwt_main.run (Database.story_group database "CN" "missing") with
        | Error `Not_found -> true
        | _ -> false);

      let story =
        Lwt_main.run (Database.story database "CN" "story")
        |> require_ok "story"
      in
      Alcotest.(check string) "story group" "group" story.group_id;
      Alcotest.(check (list string))
        "story reference names" [ "Alias" ]
        (match story.art_references with
        | _ :: reference :: _ -> reference.names
        | _ -> []);

      let galleries =
        Lwt_main.run (Database.galleries database "CN")
        |> require_ok "galleries"
      in
      Alcotest.(check (list string))
        "gallery IDs"
        [ "background-gallery"; "gallery" ]
        (List.map
           (fun (summary : Model.gallery_summary) -> summary.gallery.id)
           galleries);
      Alcotest.(check (list string))
        "SQLite gallery background fallback"
        [ "ART/art-v1/composition/background/background.png" ]
        (List.hd galleries).preview_composition_object_keys;
      Alcotest.(check int)
        "SQLite gallery illustration preview cap" 3
        (List.length (List.nth galleries 1).preview_composition_object_keys);
      Alcotest.(check bool)
        "SQLite gallery previews prefer illustrations" true
        (List.for_all
           (String.starts_with ~prefix:"ART/art-v1/composition/image/")
           (List.nth galleries 1).preview_composition_object_keys);

      let gallery =
        Lwt_main.run (Database.gallery database "CN" "gallery")
        |> require_ok "gallery"
      in
      Alcotest.(check (list string))
        "gallery entry IDs"
        [
          "entry"; "background"; "illustration"; "alternate"; "third"; "fourth";
        ]
        (List.map
           (fun (entry : Model.gallery_entry) -> entry.id)
           gallery.entries);
      Alcotest.(check (option string))
        "gallery entry joined composition"
        (Some "ART/art-v1/composition/character/event.png")
        (List.hd gallery.entries).composition_object_key;

      let context =
        Lwt_main.run (Database.art_context database "CN" "character" "event")
        |> require_ok "art context"
      in
      Alcotest.(check (list string))
        "context names are localized and deduplicated"
        [ "安洁莉娜"; "Angelina" ]
        context.names;
      Alcotest.(check (list string))
        "context siblings use exact prefix boundary"
        [ "event#1$1"; "event#2$2" ]
        (List.map
           (fun (sibling : Model.art_sibling) -> sibling.art_id)
           context.siblings);
      Alcotest.(check (list string))
        "context occurrences are distinct by story" [ "other-story" ]
        (List.map
           (fun (occurrence : Model.art_occurrence) -> occurrence.story_id)
           context.occurrences);
      let image_context =
        Lwt_main.run (Database.art_context database "CN" "image" "illustration")
        |> require_ok "image context"
      in
      Alcotest.(check bool)
        "non-character context has no siblings" true
        (image_context.siblings = []);
      Alcotest.(check bool)
        "missing context art" true
        (match
           Lwt_main.run
             (Database.art_context database "CN" "character" "missing")
         with
        | Error `Not_found -> true
        | _ -> false))

let rec remove_directory path =
  if Sys.file_exists path then (
    Sys.readdir path
    |> Array.iter (fun name ->
        let child = Filename.concat path name in
        if Sys.is_directory child then remove_directory child
        else try Sys.remove child with Sys_error _ -> ());
    try Unix.rmdir path with Unix.Unix_error _ -> ())

let with_temporary_directory callback =
  let placeholder = Filename.temp_file "arkwaifu-service-test-" ".directory" in
  Sys.remove placeholder;
  Unix.mkdir placeholder 0o750;
  Fun.protect
    ~finally:(fun () -> remove_directory placeholder)
    (fun () -> callback placeholder)

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

let cache_generations path =
  Sys.readdir path |> Array.to_list
  |> List.filter (fun name -> String.ends_with ~suffix:".sqlite3" name)

let test_story_group_during_generation_replacement () =
  with_sqlite_fixture (fun valid_database_path ->
      with_temporary_directory (fun cache_dir ->
          let fetch_count = ref 0 in
          let fetch ~etag:_ ~destination =
            incr fetch_count;
            copy_file valid_database_path destination;
            Lwt.return (`Fetched (Some (string_of_int !fetch_count)))
          in
          match
            Lwt_main.run
              (Database.For_test.live ~fetch ~cache_dir
                 ~download_timeout_seconds:5.)
          with
          | Error error -> Alcotest.failf "cannot start live fixture: %s" error
          | Ok controlled ->
              Fun.protect
                ~finally:(fun () ->
                  Lwt_main.run (Database.close controlled.database))
                (fun () ->
                  let query =
                    Database.story_group controlled.database "CN" "group"
                  and refresh = controlled.refresh_once () in
                  let detail, refresh_result =
                    Lwt_main.run (Lwt.both query refresh)
                  in
                  detail |> require_ok "story group during refresh" |> ignore;
                  Alcotest.(check bool)
                    "generation replaced" true
                    (match refresh_result with `Replaced -> true | _ -> false))))

let test_live_database_refresh () =
  with_sqlite_fixture (fun valid_database_path ->
      with_temporary_directory (fun cache_dir ->
          let responses =
            ref
              [
                `Database (valid_database_path, Some "generation-1");
                `Not_modified;
                `Database (valid_database_path, Some "generation-2");
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
                | `Invalid ->
                    let database = Sqlite3.db_open destination in
                    Fun.protect
                      ~finally:(fun () -> ignore (Sqlite3.db_close database))
                      (fun () ->
                        Sqlite3.Rc.check
                          (Sqlite3.exec database "PRAGMA user_version = 1"));
                    Lwt.return (`Fetched (Some "invalid"))
                | `Database (source, response_etag) ->
                    copy_file source destination;
                    Lwt.return (`Fetched response_etag))
          in
          let live =
            Lwt_main.run
              (Database.For_test.live ~fetch ~cache_dir
                 ~download_timeout_seconds:5.)
          in
          match live with
          | Error error -> Alcotest.failf "cannot start live fixture: %s" error
          | Ok controlled ->
              Fun.protect
                ~finally:(fun () ->
                  Lwt_main.run (Database.close controlled.database))
                (fun () ->
                  Lwt_main.run
                    (Database.art controlled.database "character" "event")
                  |> require_ok "initial generation"
                  |> ignore;
                  Alcotest.(check int)
                    "initial generation installed" 1
                    (List.length (cache_generations cache_dir));

                  Alcotest.(check bool)
                    "not-modified refresh" true
                    (match Lwt_main.run (controlled.refresh_once ()) with
                    | `Not_modified -> true
                    | _ -> false);
                  Alcotest.(check int)
                    "304 preserves generation" 1
                    (List.length (cache_generations cache_dir));

                  Alcotest.(check bool)
                    "valid refresh replaces generation" true
                    (match Lwt_main.run (controlled.refresh_once ()) with
                    | `Replaced -> true
                    | _ -> false);
                  Alcotest.(check int)
                    "replacement retires previous generation" 1
                    (List.length (cache_generations cache_dir));

                  Alcotest.(check bool)
                    "invalid refresh is rejected" true
                    (match Lwt_main.run (controlled.refresh_once ()) with
                    | `Failed _ -> true
                    | _ -> false);
                  Lwt_main.run
                    (Database.art controlled.database "character" "event")
                  |> require_ok "current generation after rejected refresh"
                  |> ignore;
                  Alcotest.(check int)
                    "invalid generation is cleaned" 1
                    (List.length (cache_generations cache_dir));
                  Alcotest.(check (list (option string)))
                    "etag advances only after replacement"
                    [
                      None;
                      Some "generation-1";
                      Some "generation-1";
                      Some "generation-2";
                    ]
                    (List.rev !seen_etags));
              Lwt_main.run (Database.close controlled.database);
              Alcotest.(check (list string))
                "close cleans current generation" []
                (cache_generations cache_dir)))

let test_live_cache_directory_error () =
  let parent_file = Filename.temp_file "arkwaifu-service-test-" ".file" in
  Fun.protect
    ~finally:(fun () -> try Sys.remove parent_file with Sys_error _ -> ())
    (fun () ->
      let fetch ~etag:_ ~destination:_ =
        Lwt.return (`Failed "unexpected fetch")
      in
      let result =
        Lwt_main.run
          (Database.For_test.live ~fetch
             ~cache_dir:(Filename.concat parent_file "database")
             ~download_timeout_seconds:5.)
      in
      Alcotest.(check bool)
        "cache-directory Unix error is returned" true (Result.is_error result))

let test_http_story_listing_and_cors () =
  with_sqlite_database @@ fun database ->
  let handler =
    Http.routes ~database ~object_base_url:"https://objects.example/bucket"
  in
  let group_index =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups" "")
  in
  Alcotest.(check int)
    "story group index status" 200
    (Dream.status group_index |> Dream.status_to_int);
  let open Yojson.Safe.Util in
  let group_index_json =
    Lwt_main.run (Dream.body group_index) |> Yojson.Safe.from_string |> to_list
  in
  Alcotest.(check string)
    "index representative category" "image"
    (group_index_json |> List.hd
    |> member "representativeArtReference"
    |> member "category" |> to_string);
  Alcotest.(check (list string))
    "index exposes three rotating illustrations"
    [ "image"; "image"; "image" ]
    (group_index_json |> List.hd
    |> member "previewArtReferences"
    |> to_list
    |> List.map (fun value -> value |> member "category" |> to_string));
  let removed_thumbnail_route =
    Dream.test handler
      (Dream.request ~method_:`GET
         ~target:"/api/arts/image/illustration/thumbnail/content" "")
  in
  Alcotest.(check int)
    "thumbnail route is absent" 404
    (Dream.status removed_thumbnail_route |> Dream.status_to_int);
  let first_preview =
    group_index_json |> List.hd
    |> member "previewArtReferences"
    |> to_list |> List.hd
  in
  let first_preview_art_id = first_preview |> member "artID" |> to_string in
  let expected_preview_url =
    Model.content_url ~object_base_url:"https://objects.example/bucket"
      ("ART/art-v1/thumbnail/image/" ^ first_preview_art_id ^ ".webp")
  in
  Alcotest.(check string)
    "preview has direct thumbnail URL" expected_preview_url
    (first_preview |> member "thumbnailContentUrl" |> to_string);

  let gallery_index =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/galleries" "")
  in
  Alcotest.(check int)
    "gallery index status" 200
    (Dream.status gallery_index |> Dream.status_to_int);
  let gallery_index_json =
    Lwt_main.run (Dream.body gallery_index)
    |> Yojson.Safe.from_string |> to_list
  in
  let gallery_summary =
    List.find
      (fun value -> value |> member "id" |> to_string = "gallery")
      gallery_index_json
  in
  Alcotest.(check int)
    "gallery exposes three preview URLs" 3
    (gallery_summary
    |> member "previewThumbnailContentUrls"
    |> to_list |> List.length);
  Alcotest.(check bool)
    "gallery preview URL is direct" true
    (gallery_summary
    |> member "previewThumbnailContentUrls"
    |> to_list |> List.hd |> to_string
    |> String.starts_with
         ~prefix:"https://objects.example/bucket/ART/art-v1/thumbnail/image/");

  let art_metadata =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/arts/character/event" "")
  in
  Alcotest.(check int)
    "art metadata status" 200
    (Dream.status art_metadata |> Dream.status_to_int);
  let art_metadata_json =
    Lwt_main.run (Dream.body art_metadata) |> Yojson.Safe.from_string
  in
  Alcotest.(check string)
    "art metadata has direct object-store URL"
    "https://objects.example/bucket/ART/art-v1/composition/character/event.png"
    (art_metadata_json |> member "image" |> member "contentUrl" |> to_string);
  Alcotest.(check string)
    "art metadata has direct thumbnail object-store URL"
    "https://objects.example/bucket/ART/art-v1/thumbnail/character/event.webp"
    (art_metadata_json |> member "thumbnailContentUrl" |> to_string);

  let art_context =
    Dream.test handler
      (Dream.request ~method_:`GET
         ~target:"/api/CN/arts/character/event/context" "")
  in
  Alcotest.(check int)
    "art context status" 200
    (Dream.status art_context |> Dream.status_to_int);
  let art_context_json =
    Lwt_main.run (Dream.body art_context) |> Yojson.Safe.from_string
  in
  Alcotest.(check (list string))
    "art context names"
    [ "安洁莉娜"; "Angelina" ]
    (art_context_json |> member "names" |> to_list |> filter_string);
  Alcotest.(check string)
    "art context sibling" "event#1$1"
    (art_context_json |> member "siblings" |> to_list |> List.hd
   |> member "artID" |> to_string);
  Alcotest.(check bool)
    "art context sibling URL is direct" true
    (art_context_json |> member "siblings" |> to_list |> List.hd
    |> member "thumbnailContentUrl"
    |> to_string
    |> String.starts_with ~prefix:"https://objects.example/bucket/ART/");
  Alcotest.(check string)
    "art occurrence group is routable" "other"
    (art_context_json |> member "occurrences" |> to_list |> List.hd
   |> member "groupID" |> to_string);

  let source_metadata =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/source-arts/source" "")
  in
  Alcotest.(check int)
    "source-art metadata status" 200
    (Dream.status source_metadata |> Dream.status_to_int);
  let source_metadata_json =
    Lwt_main.run (Dream.body source_metadata) |> Yojson.Safe.from_string
  in
  Alcotest.(check string)
    "source-art metadata has direct object-store URL"
    "https://objects.example/bucket/ART/art-v1/source/character/source.png"
    (source_metadata_json |> member "image" |> member "contentUrl" |> to_string);

  let unreferenced =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/unreferenced-arts" "")
  in
  Alcotest.(check int)
    "unreferenced art status" 200
    (Dream.status unreferenced |> Dream.status_to_int);
  let unreferenced_json =
    Lwt_main.run (Dream.body unreferenced) |> Yojson.Safe.from_string |> to_list
  in
  Alcotest.(check int) "one unreferenced art" 1 (List.length unreferenced_json);
  let unreferenced_art = List.hd unreferenced_json in
  Alcotest.(check string)
    "unreferenced ID" "eventual#1$1"
    (unreferenced_art |> member "id" |> to_string);
  Alcotest.(check string)
    "unreferenced category" "character"
    (unreferenced_art |> member "category" |> to_string);
  Alcotest.(check string)
    "unreferenced direct thumbnail URL"
    "https://objects.example/bucket/ART/art-v1/thumbnail/character/eventual%231$1.webp"
    (unreferenced_art |> member "thumbnailContentUrl" |> to_string);
  Alcotest.(check (list string))
    "unreferenced payload stays compact"
    [ "id"; "category"; "thumbnailContentUrl" ]
    (unreferenced_art |> to_assoc |> List.map fst);

  let sitemap =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/sitemap.txt" "")
  in
  Alcotest.(check int)
    "sitemap status" 200 (Dream.status sitemap |> Dream.status_to_int);
  Alcotest.(check (option string))
    "sitemap content type" (Some "text/plain; charset=utf-8")
    (Dream.header sitemap "Content-Type");
  Alcotest.(check (option string))
    "sitemap CORS" (Some "*")
    (Dream.header sitemap "Access-Control-Allow-Origin");
  let sitemap_urls =
    Lwt_main.run (Dream.body sitemap) |> String.split_on_char '\n'
    |> List.filter (fun value -> not (String.equal value ""))
  in
  Alcotest.(check int) "sitemap URL count" 58 (List.length sitemap_urls);
  Alcotest.(check int)
    "sitemap URLs are unique" 58
    (sitemap_urls |> List.sort_uniq String.compare |> List.length);
  List.iter
    (fun url ->
      Alcotest.(check bool)
        ("sitemap contains " ^ url) true
        (List.mem url sitemap_urls))
    [
      "https://arkwaifu.cc/CN";
      "https://arkwaifu.cc/CN/stories/main/group";
      "https://arkwaifu.cc/CN/stories/integrated-strategies/integrated-strategies";
      "https://arkwaifu.cc/CN/stories/reclamation-algorithm/reclamation-algorithm";
      "https://arkwaifu.cc/CN/stories/others/empty";
      "https://arkwaifu.cc/EN/stories/others/encoded%3A%E7%BB%84%2F100%25";
      "https://arkwaifu.cc/EN/galleries/foreign-gallery";
      "https://arkwaifu.cc/TW/galleries";
      "https://arkwaifu.cc/CN/about";
      "https://arkwaifu.cc/CN/unreferenced";
    ];
  List.iter
    (fun (label, target) ->
      let removed_route =
        Dream.test handler (Dream.request ~method_:`GET ~target "")
      in
      Alcotest.(check int)
        label 404
        (Dream.status removed_route |> Dream.status_to_int))
    [
      ("art content route is absent", "/api/arts/character/event/content");
      ("source-art content route is absent", "/api/source-arts/source/content");
    ];
  let response =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups/group/stories"
         "")
  in
  Alcotest.(check int)
    "story listing status" 200
    (Dream.status response |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS origin" (Some "*")
    (Dream.header response "Access-Control-Allow-Origin");
  let json = Lwt_main.run (Dream.body response) |> Yojson.Safe.from_string in
  let stories = json |> to_list in
  Alcotest.(check (list string))
    "story listing IDs"
    [ "story"; "aaa-later"; "background-only" ]
    (List.map (fun value -> value |> member "id" |> to_string) stories);
  Alcotest.(check bool)
    "HTTP summaries have empty detail references" true
    (List.for_all
       (fun value -> value |> member "artReferences" = `List [])
       stories);
  Alcotest.(check (list string))
    "HTTP story previews prefer images then fall back"
    [ "image"; "image"; "background" ]
    (List.map
       (fun value ->
         value
         |> member "previewArtReferences"
         |> to_list |> List.hd |> member "category" |> to_string)
       stories);
  Alcotest.(check bool)
    "legacy representative remains first preview" true
    (List.for_all
       (fun value ->
         let representative = value |> member "representativeArtReference" in
         let preview =
           value |> member "previewArtReferences" |> to_list |> List.hd
         in
         representative = preview)
       stories);

  let story_detail =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/stories/story" "")
  in
  let story_detail_json =
    Lwt_main.run (Dream.body story_detail) |> Yojson.Safe.from_string
  in
  let detail_references =
    story_detail_json |> member "artReferences" |> to_list
  in
  Alcotest.(check string)
    "story reference has direct thumbnail URL"
    "https://objects.example/bucket/ART/art-v1/thumbnail/background/background.webp"
    (detail_references |> List.hd |> member "thumbnailContentUrl" |> to_string);
  Alcotest.(check bool)
    "unresolved story reference has null thumbnail URL" true
    (detail_references |> List.rev |> List.hd
    |> member "thumbnailContentUrl"
    = `Null);

  let group =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups/group" "")
  in
  Alcotest.(check int)
    "story group detail status" 200
    (Dream.status group |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS on group detail" (Some "*")
    (Dream.header group "Access-Control-Allow-Origin");
  let group_json = Lwt_main.run (Dream.body group) |> Yojson.Safe.from_string in
  Alcotest.(check string)
    "group representative category" "image"
    (group_json
    |> member "representativeArtReference"
    |> member "category" |> to_string);
  Alcotest.(check int)
    "group detail preview cap" 3
    (group_json |> member "previewArtReferences" |> to_list |> List.length);
  Alcotest.(check (list string))
    "HTTP group art IDs"
    [ "background"; "illustration"; "alternate"; "third"; "fourth" ]
    (group_json |> member "artReferences" |> to_list
    |> List.map (fun value -> value |> member "artID" |> to_string));

  let empty =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups/empty/stories"
         "")
  in
  Alcotest.(check int)
    "empty story group status" 200
    (Dream.status empty |> Dream.status_to_int);
  Alcotest.(check bool)
    "empty story group body" true
    (Lwt_main.run (Dream.body empty) |> Yojson.Safe.from_string = `List []);

  let empty_group =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups/empty" "")
  in
  Alcotest.(check int)
    "empty group detail status" 200
    (Dream.status empty_group |> Dream.status_to_int);
  let empty_group_json =
    Lwt_main.run (Dream.body empty_group) |> Yojson.Safe.from_string
  in
  Alcotest.(check string)
    "empty group exposes the others category" "others"
    (empty_group_json |> member "type" |> to_string);
  Alcotest.(check bool)
    "empty group has no representative" true
    (empty_group_json |> member "representativeArtReference" = `Null);
  Alcotest.(check bool)
    "empty group has no art" true
    (empty_group_json |> member "artReferences" = `List []);
  Alcotest.(check bool)
    "empty group has no previews" true
    (empty_group_json |> member "previewArtReferences" = `List []);

  let missing_group =
    Dream.test handler
      (Dream.request ~method_:`GET
         ~target:"/api/CN/story-groups/missing/stories" "")
  in
  Alcotest.(check int)
    "missing story group status" 404
    (Dream.status missing_group |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS on missing story group" (Some "*")
    (Dream.header missing_group "Access-Control-Allow-Origin");

  let missing_group_detail =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups/missing" "")
  in
  Alcotest.(check int)
    "missing group detail status" 404
    (Dream.status missing_group_detail |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS on missing group detail" (Some "*")
    (Dream.header missing_group_detail "Access-Control-Allow-Origin");

  let missing =
    Dream.test handler (Dream.request ~method_:`GET ~target:"/missing" "")
  in
  Alcotest.(check int)
    "missing route status" 404
    (Dream.status missing |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS on errors" (Some "*")
    (Dream.header missing "Access-Control-Allow-Origin");

  let preflight =
    Dream.test handler
      (Dream.request ~method_:`OPTIONS
         ~target:"/api/CN/story-groups/group/stories" "")
  in
  Alcotest.(check int)
    "preflight status" 204
    (Dream.status preflight |> Dream.status_to_int);
  Alcotest.(check (option string))
    "preflight origin" (Some "*")
    (Dream.header preflight "Access-Control-Allow-Origin");
  Alcotest.(check (option string))
    "preflight methods" (Some "GET, OPTIONS")
    (Dream.header preflight "Access-Control-Allow-Methods")

let test_http_invalid_composition_key () =
  with_sqlite_database
    ~after:
      "UPDATE arts SET object_key = 'malformed.png' WHERE category = \
       'character' AND art_id = 'event'"
  @@ fun database ->
  let handler =
    Http.routes ~database ~object_base_url:"https://objects.example/bucket"
  in
  let response =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/arts/character/event" "")
  in
  Alcotest.(check int)
    "invalid composition key status" 503
    (Dream.status response |> Dream.status_to_int);
  Alcotest.(check string)
    "invalid composition key body" {|{"error":"service_unavailable"}|}
    (Lwt_main.run (Dream.body response));
  Alcotest.(check (option string))
    "invalid composition key CORS" (Some "*")
    (Dream.header response "Access-Control-Allow-Origin")

let () =
  Alcotest.run "arkwaifu-service"
    [
      ("config", [ Alcotest.test_case "HTTP URLs" `Quick test_config_urls ]);
      ( "model",
        [
          Alcotest.test_case "art JSON" `Quick test_art_json;
          Alcotest.test_case "source-art JSON" `Quick test_source_art_json;
          Alcotest.test_case "object-key escaping" `Quick
            test_content_url_escapes_encoded_key;
        ] );
      ( "database",
        [
          Alcotest.test_case "SQLite queries" `Quick test_sqlite_database;
          Alcotest.test_case "story group uses one pool acquisition" `Quick
            test_story_group_uses_one_pool_acquisition;
          Alcotest.test_case "story group during generation replacement" `Quick
            test_story_group_during_generation_replacement;
          Alcotest.test_case "live refresh lifecycle" `Quick
            test_live_database_refresh;
          Alcotest.test_case "cache directory error" `Quick
            test_live_cache_directory_error;
        ] );
      ( "http",
        [
          Alcotest.test_case "story listing and CORS" `Quick
            test_http_story_listing_and_cors;
          Alcotest.test_case "invalid composition key" `Quick
            test_http_invalid_composition_key;
        ] );
    ]
