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

let picture_art id category =
  Model.
    {
      id;
      category;
      image =
        {
          object_key = "ART/art-v1/composition/" ^ category ^ "/" ^ id ^ ".png";
          byte_size = 44L;
          width = 1920;
          height = 1080;
        };
      source_art_ids = [];
    }

let illustration_art = picture_art "illustration" "image"
let alternate_illustration_art = picture_art "alternate" "image"
let third_illustration_art = picture_art "third" "image"
let fourth_illustration_art = picture_art "fourth" "image"
let background_art = picture_art "background" "background"

let source_image =
  Model.
    {
      object_key =
        "ART/26-08-07-10-51-39_26e0fc/source/character/source.png";
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

let story_reference =
  Model.
    {
      art_id = "illustration";
      kind = "picture";
      category = "image";
      title = Some "Title";
      subtitle = None;
      names = [ "Alias" ];
      composition_object_key = None;
    }

let alternate_story_reference =
  Model.
    {
      art_id = "alternate";
      kind = "picture";
      category = "image";
      title = Some "Alternate";
      subtitle = None;
      names = [];
      composition_object_key = None;
    }

let picture_reference art_id title =
  Model.
    {
      art_id;
      kind = "picture";
      category = "image";
      title = Some title;
      subtitle = None;
      names = [];
      composition_object_key = None;
    }

let third_story_reference = picture_reference "third" "Third"
let fourth_story_reference = picture_reference "fourth" "Fourth"
let unavailable_story_reference = picture_reference "unavailable" "Unavailable"

let background_reference =
  Model.
    {
      art_id = "background";
      kind = "picture";
      category = "background";
      title = None;
      subtitle = None;
      names = [];
      composition_object_key = None;
    }

let story =
  Model.
    {
      id = "story";
      group_id = "group";
      tag = "before";
      tag_text = "Before";
      code = "S1";
      name = "Story";
      info = "Info";
      art_references =
        [
          background_reference;
          story_reference;
          alternate_story_reference;
          third_story_reference;
          fourth_story_reference;
          unavailable_story_reference;
        ];
    }

let later_story =
  Model.
    {
      id = "aaa-later";
      group_id = "group";
      tag = "after";
      tag_text = "After";
      code = "S2";
      name = "Later story";
      info = "Later info";
      art_references = [ story_reference ];
    }

let background_only_story =
  Model.
    {
      id = "background-only";
      group_id = "group";
      tag = "after";
      tag_text = "After";
      code = "S3";
      name = "Background story";
      info = "Background info";
      art_references = [ background_reference ];
    }

let story_group =
  Model.{ id = "group"; name = "Group"; group_type = "main_story" }

let empty_story_group =
  Model.{ id = "empty"; name = "Empty group"; group_type = "other" }

let test_art_json () =
  let json = Model.art_json ~object_base_url:"https://objects.example/bucket/" art in
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
    "SHA-256 absent"
    true
    (json |> member "image" |> member "sha256" = `Null)

let test_source_art_json () =
  let json =
    Model.source_art_json ~object_base_url:"https://objects.example/bucket/" source_art
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

let test_memory_database () =
  let gallery_entry =
    Model.
      {
        id = "entry";
        position = 0;
        name = "Entry";
        description = "Description";
        art_id = "event";
        category = "image";
        composition_object_key = None;
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
    { Database.arts =
        [
          art;
          illustration_art;
          alternate_illustration_art;
          third_illustration_art;
          fourth_illustration_art;
          background_art;
        ];
      source_arts = [ source_art ];
      story_groups = [ ("CN", [ story_group; empty_story_group ]) ];
      stories = [ ("CN", [ story; later_story; background_only_story ]) ];
      galleries = [ ("CN", [ gallery ]) ];
    }
  in
  let database = Database.memory snapshot in
  let found = Lwt_main.run (Database.art database "character" "event") in
  let wrong_category = Lwt_main.run (Database.art database "image" "event") in
  let stories =
    Lwt_main.run (Database.stories_by_group database "CN" "group")
  in
  let groups = Lwt_main.run (Database.story_groups database "CN") in
  let groups_again = Lwt_main.run (Database.story_groups database "CN") in
  let group_detail =
    Lwt_main.run (Database.story_group database "CN" "group")
  in
  let empty_group_detail =
    Lwt_main.run (Database.story_group database "CN" "empty")
  in
  let missing_group_detail =
    Lwt_main.run (Database.story_group database "CN" "missing")
  in
  let empty_stories =
    Lwt_main.run (Database.stories_by_group database "CN" "empty")
  in
  let missing_stories =
    Lwt_main.run (Database.stories_by_group database "CN" "missing")
  in
  let summaries = Lwt_main.run (Database.galleries database "CN") in
  let detailed = Lwt_main.run (Database.gallery database "CN" "gallery") in
  Alcotest.(check bool) "found" true (Result.is_ok found);
  Alcotest.(check bool)
    "missing"
    true
    (match wrong_category with Error `Not_found -> true | _ -> false);
  Alcotest.(check (list string))
    "story summary order"
    [ "story"; "aaa-later"; "background-only" ]
    (match stories with
    | Ok values ->
        List.map (fun (value : Model.story_summary) -> value.story.id) values
    | Error _ -> []);
  Alcotest.(check bool)
    "story summaries have empty references"
    true
    (match stories with
    | Ok values ->
        List.for_all
          (fun (value : Model.story_summary) -> value.story.art_references = [])
          values
    | Error _ -> false);
  Alcotest.(check bool)
    "story representative prefers image"
    true
    (match stories with
    | Ok ({ representative_art_reference = Some reference; _ } :: _) ->
        String.equal reference.category "image"
    | _ -> false);
  Alcotest.(check (list string))
    "story previews contain three available illustrations"
    [ "image"; "image"; "image" ]
    (match stories with
    | Ok ({ preview_art_references; _ } :: _) ->
        List.map
          (fun (reference : Model.art_reference) -> reference.category)
          preview_art_references
    | _ -> []);
  Alcotest.(check (list string))
    "background-only story falls back to its background"
    [ "background" ]
    (match stories with
    | Ok values ->
        values |> List.rev |> List.hd |> fun (summary : Model.story_summary) ->
        List.map
          (fun (reference : Model.art_reference) -> reference.category)
          summary.preview_art_references
    | Error _ -> []);
  Alcotest.(check bool)
    "group representative prefers image"
    true
    (match groups with
    | Ok [ { representative_art_reference = Some reference; _ }; _ ] ->
        String.equal reference.category "image"
    | _ -> false);
  let representative_id
      (result : (Model.story_group_summary list, Database.error) result) =
    match result with
    | Ok ({ representative_art_reference = Some reference; _ } :: _) ->
        Some reference.art_id
    | _ -> None
  in
  Alcotest.(check (option string))
    "representative selection is stable"
    (representative_id groups)
    (representative_id groups_again);
  let preview_ids
      (result : (Model.story_group_summary list, Database.error) result) =
    match result with
    | Ok ({ preview_art_references; _ } :: _) ->
        List.map
          (fun (reference : Model.art_reference) -> reference.art_id)
          preview_art_references
    | _ -> []
  in
  Alcotest.(check int) "group preview cap" 3 (List.length (preview_ids groups));
  Alcotest.(check (list string))
    "group preview order is stable"
    (preview_ids groups)
    (preview_ids groups_again);
  Alcotest.(check (list string))
    "group detail deduplicates available art"
    [ "background"; "illustration"; "alternate"; "third"; "fourth" ]
    (match group_detail with
    | Ok value ->
        List.map (fun (reference : Model.art_reference) -> reference.art_id)
          value.art_references
    | Error _ -> []);
  Alcotest.(check bool)
    "empty group detail"
    true
    (match empty_group_detail with
    | Ok
        {
          representative_art_reference = None;
          preview_art_references = [];
          art_references = [];
          _;
        } ->
        true
    | _ -> false);
  Alcotest.(check bool)
    "missing group detail"
    true
    (match missing_group_detail with Error `Not_found -> true | _ -> false);
  Alcotest.(check bool)
    "existing empty story group"
    true
    (match empty_stories with Ok [] -> true | _ -> false);
  Alcotest.(check bool)
    "missing story group"
    true
    (match missing_stories with Error `Not_found -> true | _ -> false);
  Alcotest.(check bool)
    "summary entries are empty"
    true
    (match summaries with Ok [ value ] -> value.entries = [] | _ -> false);
  Alcotest.(check bool)
    "detail retains unresolved entries"
    true
    (match detailed with
    | Ok value ->
        value.entries = [ gallery_entry ]
        && (List.hd value.entries).composition_object_key = None
    | _ -> false)

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
    INSERT INTO unit_versions VALUES ('art', 'art-v1'), ('CN', 'cn-v1');
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
       'ART/art-v1/composition/background/background.png', 44, 1920, 1080);
    INSERT INTO source_arts
      VALUES ('source', 'character', 'body', '1',
              'ART/art-v1/source/character/source.png', 43, 11, 21);
    INSERT INTO art_source_refs VALUES ('character', 'event', 0, 'source');
    INSERT INTO story_groups VALUES
      ('CN', 'group', 'Group', 'main_story', 0),
      ('CN', 'empty', 'Empty group', 'other', 1);
    INSERT INTO stories
      VALUES ('CN', 'story', 'group', 'before', 'Before', 'S1', 'Story', 'Info', 0);
    INSERT INTO stories
      VALUES ('CN', 'aaa-later', 'group', 'after', 'After', 'S2', 'Later story',
              'Later info', 1);
    INSERT INTO stories
      VALUES ('CN', 'background-only', 'group', 'after', 'After', 'S3',
              'Background story', 'Background info', 2);
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
         NULL, '[]');
    INSERT INTO galleries VALUES ('CN', 'gallery', 'Gallery', 'Description');
    INSERT INTO gallery_entries
      VALUES ('CN', 'gallery', 0, 'entry', 'Entry', 'Entry description',
              'event', 'character');
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
      let art =
        Lwt_main.run (Database.art database "character" "event") |> require_ok "art"
      in
      Alcotest.(check string) "art category" "character" art.category;
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
        "story group IDs" [ "group"; "empty" ]
        (List.map
           (fun (summary : Model.story_group_summary) -> summary.group.id)
           groups);
      Alcotest.(check bool)
        "group representative prefers image"
        true
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
              (fun (reference : Model.art_reference) -> reference.category)
              preview_art_references
        | _ -> []);

      let stories =
        Lwt_main.run (Database.stories_by_group database "CN" "group")
        |> require_ok "stories by group"
      in
      Alcotest.(check (list string))
        "story summary IDs" [ "story"; "aaa-later"; "background-only" ]
        (List.map (fun (summary : Model.story_summary) -> summary.story.id) stories);
      Alcotest.(check bool)
        "story summaries have empty references"
        true
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
      Alcotest.(check (list string))
        "existing empty story group" []
        (Lwt_main.run (Database.stories_by_group database "CN" "empty")
        |> require_ok "empty stories by group"
        |> List.map (fun (summary : Model.story_summary) -> summary.story.id));
      Alcotest.(check bool)
        "missing story group"
        true
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
        (List.map (fun (reference : Model.art_reference) -> reference.art_id)
           group_detail.art_references);
      Alcotest.(check bool)
        "empty group detail"
        true
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
        "missing group detail"
        true
        (match Lwt_main.run (Database.story_group database "CN" "missing") with
        | Error `Not_found -> true
        | _ -> false);

      let story =
        Lwt_main.run (Database.story database "CN" "story") |> require_ok "story"
      in
      Alcotest.(check string) "story group" "group" story.group_id;
      Alcotest.(check (list string))
        "story reference names" [ "Alias" ]
        (match story.art_references with
        | _ :: reference :: _ -> reference.names
        | _ -> []);

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
        (List.map (fun (entry : Model.gallery_entry) -> entry.id) gallery.entries);
      Alcotest.(check (option string))
        "gallery entry joined composition"
        (Some "ART/art-v1/composition/character/event.png")
        (List.hd gallery.entries).composition_object_key)

let test_http_story_listing_and_cors () =
  let snapshot : Database.snapshot =
    { Database.empty_snapshot with
      arts =
        [
          art;
          illustration_art;
          alternate_illustration_art;
          third_illustration_art;
          fourth_illustration_art;
          background_art;
        ];
      source_arts = [ source_art ];
      story_groups = [ ("CN", [ story_group; empty_story_group ]) ];
      stories = [ ("CN", [ story; later_story; background_only_story ]) ];
    }
  in
  let handler =
    Http.routes ~database:(Database.memory snapshot)
      ~object_base_url:"https://objects.example/bucket"
  in
  let group_index =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups" "")
  in
  Alcotest.(check int) "story group index status" 200
    (Dream.status group_index |> Dream.status_to_int);
  let open Yojson.Safe.Util in
  let group_index_json =
    Lwt_main.run (Dream.body group_index) |> Yojson.Safe.from_string |> to_list
  in
  Alcotest.(check string)
    "index representative category" "image"
    (group_index_json |> List.hd |> member "representativeArtReference"
    |> member "category" |> to_string);
  Alcotest.(check (list string))
    "index exposes three rotating illustrations"
    [ "image"; "image"; "image" ]
    (group_index_json |> List.hd |> member "previewArtReferences" |> to_list
    |> List.map (fun value -> value |> member "category" |> to_string));
  let removed_thumbnail_route =
    Dream.test handler
      (Dream.request ~method_:`GET
         ~target:"/api/arts/image/illustration/thumbnail/content" "")
  in
  Alcotest.(check int) "thumbnail route is absent" 404
    (Dream.status removed_thumbnail_route |> Dream.status_to_int);
  Alcotest.(check string)
    "preview has direct thumbnail URL"
    "https://objects.example/bucket/ART/art-v1/thumbnail/image/illustration.webp"
    (group_index_json |> List.hd |> member "previewArtReferences" |> to_list
    |> List.hd |> member "thumbnailContentUrl" |> to_string);

  let art_metadata =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/arts/character/event" "")
  in
  Alcotest.(check int) "art metadata status" 200
    (Dream.status art_metadata |> Dream.status_to_int);
  let art_metadata_json =
    Lwt_main.run (Dream.body art_metadata) |> Yojson.Safe.from_string
  in
  Alcotest.(check string)
    "art metadata has direct object-store URL"
    "https://objects.example/bucket/ART/26-08-07-10-51-39_26e0fc/composition/character/event.png"
    (art_metadata_json |> member "image" |> member "contentUrl" |> to_string);
  Alcotest.(check string)
    "art metadata has direct thumbnail object-store URL"
    "https://objects.example/bucket/ART/26-08-07-10-51-39_26e0fc/thumbnail/character/event.webp"
    (art_metadata_json |> member "thumbnailContentUrl" |> to_string);

  let source_metadata =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/source-arts/source" "")
  in
  Alcotest.(check int) "source-art metadata status" 200
    (Dream.status source_metadata |> Dream.status_to_int);
  let source_metadata_json =
    Lwt_main.run (Dream.body source_metadata) |> Yojson.Safe.from_string
  in
  Alcotest.(check string)
    "source-art metadata has direct object-store URL"
    "https://objects.example/bucket/ART/26-08-07-10-51-39_26e0fc/source/character/source.png"
    (source_metadata_json |> member "image" |> member "contentUrl" |> to_string);

  List.iter
    (fun (label, target) ->
      let removed_route =
        Dream.test handler (Dream.request ~method_:`GET ~target "")
      in
      Alcotest.(check int) label 404
        (Dream.status removed_route |> Dream.status_to_int))
    [
      ("art content route is absent", "/api/arts/character/event/content");
      ("source-art content route is absent", "/api/source-arts/source/content");
    ];
  let response =
    Dream.test handler
      (Dream.request ~method_:`GET
         ~target:"/api/CN/story-groups/group/stories" "")
  in
  Alcotest.(check int) "story listing status" 200
    (Dream.status response |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS origin" (Some "*")
    (Dream.header response "Access-Control-Allow-Origin");
  let json = Lwt_main.run (Dream.body response) |> Yojson.Safe.from_string in
  let stories = json |> to_list in
  Alcotest.(check (list string))
    "story listing IDs" [ "story"; "aaa-later"; "background-only" ]
    (List.map (fun value -> value |> member "id" |> to_string) stories);
  Alcotest.(check bool)
    "HTTP summaries have empty references"
    true
    (List.for_all
       (fun value -> value |> member "artReferences" |> to_list = [])
       stories);
  Alcotest.(check (list string))
    "HTTP story previews prefer images then fall back"
    [ "image"; "image"; "background" ]
    (List.map
       (fun value ->
         value |> member "previewArtReferences" |> to_list |> List.hd
         |> member "category" |> to_string)
       stories);
  Alcotest.(check bool)
    "legacy representative remains first preview"
    true
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
  let detail_references = story_detail_json |> member "artReferences" |> to_list in
  Alcotest.(check string)
    "story reference has direct thumbnail URL"
    "https://objects.example/bucket/ART/art-v1/thumbnail/background/background.webp"
    (detail_references |> List.hd |> member "thumbnailContentUrl" |> to_string);
  Alcotest.(check bool)
    "unresolved story reference has null thumbnail URL"
    true
    (detail_references |> List.rev |> List.hd |> member "thumbnailContentUrl"
    = `Null);

  let group =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups/group" "")
  in
  Alcotest.(check int) "story group detail status" 200
    (Dream.status group |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS on group detail" (Some "*")
    (Dream.header group "Access-Control-Allow-Origin");
  let group_json = Lwt_main.run (Dream.body group) |> Yojson.Safe.from_string in
  Alcotest.(check string)
    "group representative category" "image"
    (group_json |> member "representativeArtReference" |> member "category"
    |> to_string);
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
      (Dream.request ~method_:`GET
         ~target:"/api/CN/story-groups/empty/stories" "")
  in
  Alcotest.(check int) "empty story group status" 200
    (Dream.status empty |> Dream.status_to_int);
  Alcotest.(check bool)
    "empty story group body"
    true
    (Lwt_main.run (Dream.body empty) |> Yojson.Safe.from_string = `List []);

  let empty_group =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups/empty" "")
  in
  Alcotest.(check int) "empty group detail status" 200
    (Dream.status empty_group |> Dream.status_to_int);
  let empty_group_json =
    Lwt_main.run (Dream.body empty_group) |> Yojson.Safe.from_string
  in
  Alcotest.(check bool)
    "empty group has no representative"
    true
    (empty_group_json |> member "representativeArtReference" = `Null);
  Alcotest.(check bool)
    "empty group has no art"
    true
    (empty_group_json |> member "artReferences" = `List []);
  Alcotest.(check bool)
    "empty group has no previews"
    true
    (empty_group_json |> member "previewArtReferences" = `List []);

  let missing_group =
    Dream.test handler
      (Dream.request ~method_:`GET
         ~target:"/api/CN/story-groups/missing/stories" "")
  in
  Alcotest.(check int) "missing story group status" 404
    (Dream.status missing_group |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS on missing story group" (Some "*")
    (Dream.header missing_group "Access-Control-Allow-Origin");

  let missing_group_detail =
    Dream.test handler
      (Dream.request ~method_:`GET ~target:"/api/CN/story-groups/missing" "")
  in
  Alcotest.(check int) "missing group detail status" 404
    (Dream.status missing_group_detail |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS on missing group detail" (Some "*")
    (Dream.header missing_group_detail "Access-Control-Allow-Origin");

  let missing =
    Dream.test handler (Dream.request ~method_:`GET ~target:"/missing" "")
  in
  Alcotest.(check int) "missing route status" 404
    (Dream.status missing |> Dream.status_to_int);
  Alcotest.(check (option string))
    "CORS on errors" (Some "*")
    (Dream.header missing "Access-Control-Allow-Origin");

  let preflight =
    Dream.test handler
      (Dream.request ~method_:`OPTIONS
         ~target:"/api/CN/story-groups/group/stories" "")
  in
  Alcotest.(check int) "preflight status" 204
    (Dream.status preflight |> Dream.status_to_int);
  Alcotest.(check (option string))
    "preflight origin" (Some "*")
    (Dream.header preflight "Access-Control-Allow-Origin");
  Alcotest.(check (option string))
    "preflight methods" (Some "GET, OPTIONS")
    (Dream.header preflight "Access-Control-Allow-Methods")

let () =
  Alcotest.run "arkwaifu-service"
    [
      ( "model",
        [
          Alcotest.test_case "art JSON" `Quick test_art_json;
          Alcotest.test_case "source-art JSON" `Quick test_source_art_json;
          Alcotest.test_case "object-key escaping" `Quick
            test_content_url_escapes_encoded_key;
        ] );
      ( "database",
        [
          Alcotest.test_case "memory lookup" `Quick test_memory_database;
          Alcotest.test_case "SQLite queries" `Quick test_sqlite_database;
        ] );
      ( "http",
        [
          Alcotest.test_case "story listing and CORS" `Quick
            test_http_story_listing_and_cors;
        ] );
    ]
