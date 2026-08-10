open Arkwaifu_service

let image =
  Model.
    {
      object_key = "ART/version/composition/image/event.png";
      byte_size = 42L;
      width = 10;
      height = 20;
    }

let art =
  Model.{ id = "event"; category = "image"; image; source_art_ids = [ "source" ] }

let source_art =
  Model.
    {
      id = "source";
      character_id = "character";
      role = "body";
      variant = "1";
      image;
    }

let test_art_json () =
  let json = Model.art_json ~object_base_url:"https://objects.example/bucket/" art in
  let open Yojson.Safe.Util in
  Alcotest.(check string) "id" "event" (json |> member "id" |> to_string);
  Alcotest.(check string)
    "content URL"
    "https://objects.example/bucket/ART/version/composition/image/event.png"
    (json |> member "image" |> member "contentUrl" |> to_string);
  Alcotest.(check bool)
    "SHA-256 absent"
    true
    (json |> member "image" |> member "sha256" = `Null)

let test_content_url_escapes_encoded_key () =
  Alcotest.(check string)
    "literal percent escape"
    "https://objects.example/bucket/art/source/id%253Avariant/hash.png"
    (Model.content_url ~object_base_url:"https://objects.example/bucket/"
       "art/source/id%3Avariant/hash.png")

let test_memory_database () =
  let gallery_entry =
    Model.
      {
        id = "entry";
        position = 0;
        name = "Entry";
        description = "Description";
        art_id = "event";
      }
  in
  let gallery =
    Model.
      {
        id = "gallery";
        name = "Gallery";
        description = "Description";
        entries = [ gallery_entry ];
      }
  in
  let snapshot : Database.snapshot =
    { Database.empty_snapshot with
      arts = [ art ];
      source_arts = [ source_art ];
      galleries = [ ("CN", [ gallery ]) ];
    }
  in
  let database = Database.memory snapshot in
  let found = Lwt_main.run (Database.art database "event") in
  let missing = Lwt_main.run (Database.art database "missing") in
  let summaries = Lwt_main.run (Database.galleries database "CN") in
  let detailed = Lwt_main.run (Database.gallery database "CN" "gallery") in
  Alcotest.(check bool) "found" true (Result.is_ok found);
  Alcotest.(check bool)
    "missing"
    true
    (match missing with Error `Not_found -> true | _ -> false);
  Alcotest.(check bool)
    "summary entries are empty"
    true
    (match summaries with Ok [ value ] -> value.entries = [] | _ -> false);
  Alcotest.(check bool)
    "detail retains entries"
    true
    (match detailed with Ok value -> value.entries = [ gallery_entry ] | _ -> false)

(* This is a reader fixture, not a copy of the updater-owned production schema. *)
let reader_fixture_schema =
  {|
    PRAGMA foreign_keys = ON;

    CREATE TABLE unit_versions (
      unit TEXT PRIMARY KEY,
      res_version TEXT NOT NULL
    );

    CREATE TABLE arts (
      art_id TEXT PRIMARY KEY,
      category TEXT NOT NULL,
      object_key TEXT NOT NULL,
      byte_size INTEGER NOT NULL,
      width INTEGER NOT NULL,
      height INTEGER NOT NULL
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
      art_id TEXT NOT NULL REFERENCES arts (art_id),
      position INTEGER NOT NULL,
      source_art_id TEXT NOT NULL REFERENCES source_arts (source_art_id),
      PRIMARY KEY (art_id, position)
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
      PRIMARY KEY (locale, gallery_id, entry_id),
      FOREIGN KEY (locale, gallery_id) REFERENCES galleries (locale, gallery_id)
    );

    PRAGMA user_version = 1;
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
    INSERT INTO unit_versions VALUES ('art', 'art-v1'), ('CN', 'cn-v1');
    INSERT INTO arts VALUES ('event', 'image', 'art/event.png', 42, 10, 20);
    INSERT INTO source_arts
      VALUES ('source', 'character', 'body', '1', 'art/source.png', 43, 11, 21);
    INSERT INTO art_source_refs VALUES ('event', 0, 'source');
    INSERT INTO story_groups VALUES ('CN', 'group', 'Group', 'main_story', 0);
    INSERT INTO stories
      VALUES ('CN', 'story', 'group', 'before', 'Before', 'S1', 'Story', 'Info', 0);
    INSERT INTO story_art_references
      VALUES ('CN', 'story', 0, 'event', 'picture', 'image', 'Title', NULL,
              '["Alias"]');
    INSERT INTO galleries VALUES ('CN', 'gallery', 'Gallery', 'Description');
    INSERT INTO gallery_entries
      VALUES ('CN', 'gallery', 0, 'entry', 'Entry', 'Entry description', 'event');
  |}

let with_sqlite_database callback =
  let path = Filename.temp_file "arkwaifu-service-test-" ".sqlite3" in
  Fun.protect
    ~finally:(fun () -> try Sys.remove path with Sys_error _ -> ())
    (fun () ->
      let database = Sqlite3.db_open path in
      Fun.protect
        ~finally:(fun () -> ignore (Sqlite3.db_close database))
        (fun () ->
          Sqlite3.Rc.check (Sqlite3.exec database (sqlite_schema ()));
          Sqlite3.Rc.check (Sqlite3.exec database sqlite_rows));
      match Database.sqlite path with
      | Ok database ->
          Fun.protect
            ~finally:(fun () -> Lwt_main.run (Database.close database))
            (fun () -> callback database)
      | Error error -> Alcotest.failf "cannot open SQLite fixture: %s" error)

let require_ok label = function
  | Ok value -> value
  | Error `Not_found -> Alcotest.failf "%s unexpectedly returned not found" label
  | Error (`Unavailable error) -> Alcotest.failf "%s unavailable: %s" label error

let test_sqlite_database () =
  with_sqlite_database (fun database ->
      Lwt_main.run (Database.health database) |> require_ok "health";
      let art = Lwt_main.run (Database.art database "event") |> require_ok "art" in
      Alcotest.(check string) "art category" "image" art.category;
      Alcotest.(check (list string)) "source IDs" [ "source" ] art.source_art_ids;
      Alcotest.(check int64) "art bytes" 42L art.image.byte_size;

      let source =
        Lwt_main.run (Database.source_art database "source") |> require_ok "source art"
      in
      Alcotest.(check string) "source character" "character" source.character_id;
      Alcotest.(check string) "source role" "body" source.role;
      Alcotest.(check int) "source width" 11 source.image.width;

      let groups =
        Lwt_main.run (Database.story_groups database "CN") |> require_ok "story groups"
      in
      Alcotest.(check (list string))
        "story group IDs" [ "group" ]
        (List.map (fun (group : Model.story_group) -> group.id) groups);

      let story =
        Lwt_main.run (Database.story database "CN" "story") |> require_ok "story"
      in
      Alcotest.(check string) "story group" "group" story.group_id;
      Alcotest.(check (list string))
        "story reference names" [ "Alias" ]
        (match story.art_references with [ reference ] -> reference.names | _ -> []);

      let galleries =
        Lwt_main.run (Database.galleries database "CN") |> require_ok "galleries"
      in
      Alcotest.(check (list string))
        "gallery IDs" [ "gallery" ]
        (List.map (fun (gallery : Model.gallery) -> gallery.id) galleries);

      let gallery =
        Lwt_main.run (Database.gallery database "CN" "gallery") |> require_ok "gallery"
      in
      Alcotest.(check (list string))
        "gallery entry IDs" [ "entry" ]
        (List.map (fun (entry : Model.gallery_entry) -> entry.id) gallery.entries))

let () =
  Alcotest.run "arkwaifu-service"
    [
      ( "model",
        [
          Alcotest.test_case "art JSON" `Quick test_art_json;
          Alcotest.test_case "object-key escaping" `Quick
            test_content_url_escapes_encoded_key;
        ] );
      ( "database",
        [
          Alcotest.test_case "memory lookup" `Quick test_memory_database;
          Alcotest.test_case "SQLite queries" `Quick test_sqlite_database;
        ] );
    ]
