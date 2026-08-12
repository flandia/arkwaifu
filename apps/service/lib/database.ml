(** SQLite readers and the remote-generation replacement implementation. *)

open Lwt.Infix

type error = [ `Not_found | `Unavailable of string ]

type t = {
  close : unit -> unit Lwt.t;
  check : unit -> (unit, error) result Lwt.t;
  health : unit -> (unit, error) result Lwt.t;
  art : string -> string -> (Model.art, error) result Lwt.t;
  source_art : string -> (Model.source_art, error) result Lwt.t;
  story_groups : string -> (Model.story_group_summary list, error) result Lwt.t;
  stories_by_group : string -> string -> (Model.story_summary list, error) result Lwt.t;
  story_group : string -> string -> (Model.story_group_detail, error) result Lwt.t;
  story : string -> string -> (Model.story, error) result Lwt.t;
  galleries : string -> (Model.gallery list, error) result Lwt.t;
  gallery : string -> string -> (Model.gallery, error) result Lwt.t;
}

type snapshot = {
  arts : Model.art list;
  source_arts : Model.source_art list;
  story_groups : (string * Model.story_group list) list;
  stories : (string * Model.story list) list;
  galleries : (string * Model.gallery list) list;
}

let empty_snapshot =
  { arts = []; source_arts = []; story_groups = []; stories = []; galleries = [] }

let find_by_id id get_id values =
  match List.find_opt (fun value -> String.equal id (get_id value)) values with
  | Some value -> Ok value
  | None -> Error `Not_found

let locale_values locale values =
  Option.value ~default:[] (List.assoc_opt locale values)

let resolve_reference arts (reference : Model.art_reference) =
  let composition_object_key =
    arts
    |> List.find_opt (fun (art : Model.art) ->
           String.equal art.category reference.category
           && String.equal art.id reference.art_id)
    |> Option.map (fun (art : Model.art) -> art.image.object_key)
  in
  { reference with composition_object_key }

let available_references arts references =
  references
  |> List.map (resolve_reference arts)
  |> List.filter (fun (reference : Model.art_reference) ->
         Option.is_some reference.composition_object_key)

let unique_references references =
  let seen = Hashtbl.create (List.length references) in
  List.filter
    (fun (reference : Model.art_reference) ->
      let key = (reference.category, reference.art_id) in
      if Hashtbl.mem seen key then false
      else (
        Hashtbl.add seen key ();
        true))
    references

let character_code value position =
  if String.length value = 0 then 0L
  else Int64.of_int (Char.code value.[position mod String.length value])

let representative_score seed (reference : Model.art_reference) =
  let weighted factor value = Int64.mul factor value in
  let middle value = String.length value / 2 in
  let score =
    Int64.add
      (weighted 1_103_515_245L (Int64.of_int (String.length reference.art_id)))
      (Int64.add
         (weighted 12_345L (character_code reference.art_id 0))
         (Int64.add
            (weighted 2_654_435_761L
               (character_code reference.art_id (middle reference.art_id)))
            (Int64.add
               (weighted 97L
                  (character_code reference.art_id
                     (String.length reference.art_id - 1)))
               (Int64.add
                  (weighted 193L (Int64.of_int (String.length seed)))
                  (Int64.add
                     (weighted 389L (character_code seed 0))
                     (Int64.add
                        (weighted 769L (character_code seed (middle seed)))
                        (weighted 1_543L
                           (character_code seed (String.length seed - 1)))))))))
  in
  Int64.rem score 2_147_483_647L

let rec take count values =
  if count <= 0 then []
  else
    match values with
    | [] -> []
    | value :: rest -> value :: take (count - 1) rest

let preview_references ~seed references =
  let choose category =
    references
    |> unique_references
    |> List.filter (fun (reference : Model.art_reference) ->
           String.equal reference.category category)
    |> List.sort (fun left right ->
           match
             Int64.compare
               (representative_score seed left)
               (representative_score seed right)
           with
           | 0 -> String.compare left.art_id right.art_id
           | order -> order)
    |> take 3
  in
  match choose "image" with
  | _ :: _ as references -> references
  | [] -> choose "background"

let representative_reference = function
  | reference :: _ -> Some reference
  | [] -> None

let stories_in_group snapshot locale group_id =
  locale_values locale snapshot.stories
  |> List.filter (fun (story : Model.story) -> String.equal story.group_id group_id)

let group_references snapshot locale group_id =
  stories_in_group snapshot locale group_id
  |> List.concat_map (fun (story : Model.story) -> story.art_references)
  |> available_references snapshot.arts |> unique_references

let memory snapshot =
  {
    close = (fun () -> Lwt.return_unit);
    check = (fun () -> Lwt.return (Ok ()));
    health = (fun () -> Lwt.return (Ok ()));
    art =
      (fun category id ->
        snapshot.arts
        |> List.find_opt (fun (value : Model.art) ->
               String.equal category value.category && String.equal id value.id)
        |> (function Some value -> Ok value | None -> Error `Not_found)
        |> Lwt.return);
    source_art =
      (fun id ->
        Lwt.return
          (find_by_id id
             (fun (value : Model.source_art) -> value.id)
             snapshot.source_arts));
    story_groups =
      (fun locale ->
        locale_values locale snapshot.story_groups
        |> List.map (fun (group : Model.story_group) ->
               let references =
                 group_references snapshot locale group.id
                 |> List.filter (fun (reference : Model.art_reference) ->
                        Option.is_some reference.composition_object_key)
               in
               let preview_art_references =
                 preview_references ~seed:group.id references
               in
               Model.
                 {
                   group;
                   representative_art_reference =
                     representative_reference preview_art_references;
                   preview_art_references;
                 })
        |> Result.ok |> Lwt.return);
    stories_by_group =
      (fun locale group_id ->
        if
          locale_values locale snapshot.story_groups
          |> List.exists (fun (group : Model.story_group) ->
                 String.equal group_id group.id)
        then
          stories_in_group snapshot locale group_id
          |> List.map (fun (story : Model.story) ->
                 let references =
                   available_references snapshot.arts story.art_references
                 in
                 let preview_art_references =
                   preview_references ~seed:story.id references
                 in
                 Model.
                   {
                     story = { story with art_references = [] };
                     representative_art_reference =
                       representative_reference preview_art_references;
                     preview_art_references;
                   })
          |> Result.ok |> Lwt.return
        else Lwt.return (Error `Not_found));
    story_group =
      (fun locale id ->
        match
          find_by_id id
            (fun (value : Model.story_group) -> value.id)
            (locale_values locale snapshot.story_groups)
        with
        | Error error -> Lwt.return (Error error)
        | Ok group ->
            let art_references = group_references snapshot locale id in
            let preview_art_references =
              art_references
              |> List.filter (fun (reference : Model.art_reference) ->
                     Option.is_some reference.composition_object_key)
              |> preview_references ~seed:group.id
            in
            Lwt.return
              (Ok
                 Model.
                   {
                     group;
                     representative_art_reference =
                       representative_reference preview_art_references;
                     preview_art_references;
                     art_references;
                   }));
    story =
      (fun locale id ->
        find_by_id id
          (fun (value : Model.story) -> value.id)
          (locale_values locale snapshot.stories)
        |> Result.map (fun (story : Model.story) ->
               {
                 story with
                 art_references =
                   List.map (resolve_reference snapshot.arts) story.art_references;
               })
        |> Lwt.return);
    galleries =
      (fun locale ->
        locale_values locale snapshot.galleries
        |> List.map (fun (gallery : Model.gallery) -> { gallery with entries = [] })
        |> Result.ok |> Lwt.return);
    gallery =
      (fun locale id ->
        find_by_id id
          (fun (value : Model.gallery) -> value.id)
          (locale_values locale snapshot.galleries)
        |> Result.map (fun (gallery : Model.gallery) ->
               {
                 gallery with
                 entries =
                   List.map
                     (fun (entry : Model.gallery_entry) ->
                       let composition_object_key =
                         snapshot.arts
                         |> List.find_opt (fun (art : Model.art) ->
                                String.equal art.category entry.category
                                && String.equal art.id entry.art_id)
                         |> Option.map (fun (art : Model.art) ->
                                art.image.object_key)
                       in
                       { entry with composition_object_key })
                     gallery.entries;
               })
        |> Lwt.return);
  }

module Query = struct
  (* Parent rows are repeated by the ordered child joins below. The decoders
     rebuild one domain record while preserving source, reference, and entry
     order from SQLite. *)
  open Caqti_type.Std
  open Caqti_request.Infix

  let schema_version = (unit ->! int) "PRAGMA user_version"
  let ping = (unit ->! int) "SELECT 1"

  let art =
    let row =
      t2 string
        (t2 string (t2 int64 (t2 int (t2 int (option string)))))
    in
    (t2 string string ->* row)
      {|
        SELECT art.category, art.object_key, art.byte_size, art.width,
               art.height, reference.source_art_id
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
           (t2 string (t2 string (t2 int64 (t2 int int)))))
    in
    (string ->? row)
      {|
        SELECT character_id, role, variant, object_key, byte_size, width, height
        FROM source_arts
        WHERE source_art_id = ?
      |}

  let optional_reference =
    t2 (option string)
      (t2 (option string)
         (t2 (option string)
            (t2 (option string)
               (t2 (option string)
                  (t2 (option string) (option string))))))

  let story_groups =
    let row = t2 string (t2 string (t2 string optional_reference)) in
    (t2 string string ->* row)
      {|
        WITH candidate_references AS (
          SELECT story.group_id, story.position AS story_position,
                 reference.position AS reference_position, reference.art_id,
                 reference.kind, reference.category, reference.title,
                 reference.subtitle, reference.names_json, art.object_key,
                 ROW_NUMBER() OVER (
                   PARTITION BY story.group_id, reference.category,
                                reference.art_id
                   ORDER BY story.position, reference.position
                 ) AS duplicate_rank
          FROM stories AS story
          JOIN story_art_references AS reference
            ON reference.locale = story.locale
           AND reference.story_id = story.story_id
          JOIN arts AS art
            ON art.category = reference.category
           AND art.art_id = reference.art_id
          WHERE story.locale = ?
            AND reference.category IN ('image', 'background')
        ), unique_references AS (
          SELECT *,
                 MAX(CASE reference.category WHEN 'image' THEN 1 ELSE 0 END)
                   OVER (PARTITION BY group_id) AS has_image,
                 (
                   length(art_id) * 1103515245
                   + unicode(substr(art_id, 1, 1)) * 12345
                   + unicode(substr(
                       art_id,
                       (length(art_id) / 2) + 1,
                       1
                     )) * 2654435761
                   + unicode(substr(art_id, -1, 1)) * 97
                   + length(group_id) * 193
                   + unicode(substr(group_id, 1, 1)) * 389
                   + unicode(substr(
                       group_id,
                       (length(group_id) / 2) + 1,
                       1
                     )) * 769
                   + unicode(substr(group_id, -1, 1)) * 1543
                 ) % 2147483647 AS shuffle_score
          FROM candidate_references AS reference
          WHERE duplicate_rank = 1
        ), ranked_references AS (
          SELECT *,
                 ROW_NUMBER() OVER (
                   PARTITION BY group_id
                   ORDER BY shuffle_score, art_id, story_position,
                            reference_position
                 ) AS rank
          FROM unique_references
          WHERE (has_image = 1 AND category = 'image')
             OR (has_image = 0 AND category = 'background')
        )
        SELECT story_group.group_id, story_group.name, story_group.group_type,
               reference.art_id, reference.kind, reference.category,
               reference.title, reference.subtitle, reference.names_json,
               reference.object_key
        FROM story_groups AS story_group
        LEFT JOIN ranked_references AS reference
          ON reference.group_id = story_group.group_id AND reference.rank <= 3
        WHERE story_group.locale = ?
        ORDER BY story_group.position, reference.rank
      |}

  let stories_by_group =
    let row =
      t2 string
        (t2 string
           (t2 string
              (t2 string
                 (t2 string (t2 string (t2 string optional_reference))))))
    in
    (t2 (t2 string string) (t2 string string) ->* row)
      {|
        WITH candidate_references AS (
          SELECT reference.story_id, reference.position, reference.art_id,
                 reference.kind, reference.category, reference.title,
                 reference.subtitle, reference.names_json, art.object_key,
                 ROW_NUMBER() OVER (
                   PARTITION BY reference.story_id, reference.category,
                                reference.art_id
                   ORDER BY reference.position
                 ) AS duplicate_rank
          FROM stories AS candidate_story
          JOIN story_art_references AS reference
            ON reference.locale = candidate_story.locale
           AND reference.story_id = candidate_story.story_id
          JOIN arts AS art
            ON art.category = reference.category
           AND art.art_id = reference.art_id
          WHERE candidate_story.locale = ? AND candidate_story.group_id = ?
            AND reference.category IN ('image', 'background')
        ), unique_references AS (
          SELECT *,
                 MAX(CASE reference.category WHEN 'image' THEN 1 ELSE 0 END)
                   OVER (PARTITION BY story_id) AS has_image,
                 (
                   length(art_id) * 1103515245
                   + unicode(substr(art_id, 1, 1)) * 12345
                   + unicode(substr(
                       art_id,
                       (length(art_id) / 2) + 1,
                       1
                     )) * 2654435761
                   + unicode(substr(art_id, -1, 1)) * 97
                   + length(story_id) * 193
                   + unicode(substr(story_id, 1, 1)) * 389
                   + unicode(substr(
                       story_id,
                       (length(story_id) / 2) + 1,
                       1
                     )) * 769
                   + unicode(substr(story_id, -1, 1)) * 1543
                 ) % 2147483647 AS shuffle_score
          FROM candidate_references AS reference
          WHERE duplicate_rank = 1
        ), ranked_references AS (
          SELECT *,
                 ROW_NUMBER() OVER (
                   PARTITION BY story_id
                   ORDER BY shuffle_score, art_id, position
                 ) AS rank
          FROM unique_references
          WHERE (has_image = 1 AND category = 'image')
             OR (has_image = 0 AND category = 'background')
        )
        SELECT story.story_id, story.group_id, story.tag, story.tag_text,
               story.code, story.name, story.info, reference.art_id,
               reference.kind, reference.category, reference.title,
               reference.subtitle, reference.names_json, reference.object_key
        FROM stories AS story
        LEFT JOIN ranked_references AS reference
          ON reference.story_id = story.story_id AND reference.rank <= 3
        WHERE story.locale = ? AND story.group_id = ?
        ORDER BY story.position, reference.rank
      |}

  let story_group_exists =
    (t2 string string ->? int)
      {|
        SELECT 1
        FROM story_groups
        WHERE locale = ? AND group_id = ?
      |}

  let story_group =
    let row = t2 string (t2 string (t2 string optional_reference)) in
    (t2 (t2 string string) (t2 string string) ->* row)
      {|
        WITH group_references AS (
          SELECT story.group_id, story.position AS story_position,
                 reference.position AS reference_position, reference.art_id,
                 reference.kind, reference.category, reference.title,
                 reference.subtitle, reference.names_json, art.object_key
          FROM stories AS story
          JOIN story_art_references AS reference
            ON reference.locale = story.locale
           AND reference.story_id = story.story_id
          JOIN arts AS art
            ON art.category = reference.category
           AND art.art_id = reference.art_id
          WHERE story.locale = ? AND story.group_id = ?
        )
        SELECT story_group.group_id, story_group.name, story_group.group_type,
               reference.art_id, reference.kind, reference.category,
               reference.title, reference.subtitle, reference.names_json,
               reference.object_key
        FROM story_groups AS story_group
        LEFT JOIN group_references AS reference
          ON reference.group_id = story_group.group_id
        WHERE story_group.locale = ? AND story_group.group_id = ?
        ORDER BY reference.story_position, reference.reference_position
      |}

  let story =
    let row =
      t2 string
        (t2 string
           (t2 string
              (t2 string
                 (t2 string
                    (t2 string
                       (t2 (option string)
                          (t2 (option string)
                             (t2 (option string)
                                (t2 (option string)
                                   (t2 (option string)
                                      (t2 (option string)
                                         (option string))))))))))))
    in
    (t2 string string ->* row)
      {|
        SELECT story.group_id, story.tag, story.tag_text, story.code,
               story.name, story.info, reference.art_id, reference.kind,
               reference.category, reference.title, reference.subtitle,
               reference.names_json, art.object_key
        FROM stories AS story
        LEFT JOIN story_art_references AS reference
          ON reference.locale = story.locale
         AND reference.story_id = story.story_id
        LEFT JOIN arts AS art
          ON art.category = reference.category
         AND art.art_id = reference.art_id
        WHERE story.locale = ? AND story.story_id = ?
        ORDER BY reference.position
      |}

  let galleries =
    let row = t2 string (t2 string string) in
    (string ->* row)
      {|
        SELECT gallery_id, name, description
        FROM galleries
        WHERE locale = ?
        ORDER BY gallery_id
      |}

  let gallery =
    let row =
      t2 string
        (t2 string
           (t2 string
              (t2 (option string)
                 (t2 (option int)
                       (t2 (option string)
                          (t2 (option string)
                             (t2 (option string)
                                (t2 (option string) (option string)))))))))
    in
    (t2 string string ->* row)
      {|
        SELECT gallery.gallery_id, gallery.name, gallery.description,
               entry.entry_id, entry.position, entry.name,
               entry.description, entry.art_id, entry.category, art.object_key
        FROM galleries AS gallery
        LEFT JOIN gallery_entries AS entry
          ON entry.locale = gallery.locale
         AND entry.gallery_id = gallery.gallery_id
        LEFT JOIN arts AS art
          ON art.category = entry.category
         AND art.art_id = entry.art_id
        WHERE gallery.locale = ? AND gallery.gallery_id = ?
        ORDER BY entry.position
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
    ~query:[ ("write", [ "false" ]); ("create", [ "false" ]) ] ()

let sqlite path =
  let pool_config = Caqti_pool_config.create ~max_size:10 () in
  match Caqti_lwt_unix.connect_pool ~pool_config (sqlite_uri path) with
  | Error error -> Error (Caqti_error.show error)
  | Ok pool ->
      let use callback =
        Caqti_lwt_unix.Pool.use callback pool >|= function
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
      let art category id =
        use (fun (module Db) -> Db.collect_list Query.art (category, id)) >|= function
        | Error error -> Error error
        | Ok [] -> Error `Not_found
        | Ok
            ((category, (object_key, (byte_size, (width, (height, _))))) :: _ as rows)
          ->
            let source_art_ids =
              List.filter_map
                (fun (_, (_, (_, (_, (_, source_id))))) -> source_id)
                rows
            in
            Ok
              Model.
                {
                  id;
                  category;
                  image = { object_key; byte_size; width; height };
                  source_art_ids;
                }
      in
      let source_art id =
        use (fun (module Db) -> Db.find_opt Query.source_art id) >|= function
        | Error error -> Error error
        | Ok None -> Error `Not_found
        | Ok
            (Some
              ( character_id,
                (role, (variant, (object_key, (byte_size, (width, height))))) )) ->
            Ok
              Model.
                {
                  id;
                  character_id;
                  role;
                  variant;
                  image = { object_key; byte_size; width; height };
                }
      in
      let names_from_json = function
        | None -> []
        | Some raw ->
            Yojson.Safe.from_string raw |> Yojson.Safe.Util.to_list
            |> List.filter_map (function `String value -> Some value | _ -> None)
      in
      let reference_from_columns
          (art_id, (kind, (category, (title, (subtitle, (names, object_key)))))) =
        match (art_id, kind, category) with
        | Some art_id, Some kind, Some category ->
            Some
              Model.
                {
                  art_id;
                  kind;
                  category;
                  title;
                  subtitle;
                  names = names_from_json names;
                  composition_object_key = object_key;
                }
        | _ -> None
      in
      let story_groups locale =
        use (fun (module Db) ->
            Db.collect_list Query.story_groups (locale, locale))
        >|= Result.map (fun rows ->
                let rec gather id references = function
                  | (next_id, (_, (_, reference))) :: rest
                    when String.equal id next_id ->
                      let references =
                        match reference_from_columns reference with
                        | Some reference -> reference :: references
                        | None -> references
                      in
                      gather id references rest
                  | remaining -> (List.rev references, remaining)
                in
                let rec decode summaries = function
                  | [] -> List.rev summaries
                  | (id, (name, (group_type, reference))) :: rest ->
                      let initial =
                        match reference_from_columns reference with
                        | Some reference -> [ reference ]
                        | None -> []
                      in
                      let references, remaining = gather id initial rest in
                      let preview_art_references =
                        preview_references ~seed:id references
                      in
                      let summary =
                        Model.
                          {
                            group = { id; name; group_type };
                            representative_art_reference =
                              representative_reference preview_art_references;
                            preview_art_references;
                          }
                      in
                      decode (summary :: summaries) remaining
                in
                decode [] rows)
      in
      let stories_by_group locale group_id =
        use (fun (module Db) ->
            Db.collect_list Query.stories_by_group
              ((locale, group_id), (locale, group_id))
            >>= fun rows ->
            match rows with
            | Error error -> Lwt.return (Error error)
            | Ok (_ :: _ as values) -> Lwt.return (Ok (`Stories values))
            | Ok [] ->
                Db.find_opt Query.story_group_exists (locale, group_id)
                >|= Result.map (fun parent -> `Empty parent))
        >|= function
        | Error error -> Error error
        | Ok (`Empty None) -> Error `Not_found
        | Ok (`Empty (Some _)) -> Ok []
        | Ok (`Stories rows) ->
            let rec gather id references = function
              | ( next_id,
                  (_, (_, (_, (_, (_, (_, reference)))))) )
                :: rest
                when String.equal id next_id ->
                  let references =
                    match reference_from_columns reference with
                    | Some reference -> reference :: references
                    | None -> references
                  in
                  gather id references rest
              | remaining -> (List.rev references, remaining)
            in
            let rec decode summaries = function
              | [] -> List.rev summaries
              | ( id,
                  ( group_id,
                    (tag, (tag_text, (code, (name, (info, reference))))) ) )
                :: rest ->
                  let initial =
                    match reference_from_columns reference with
                    | Some reference -> [ reference ]
                    | None -> []
                  in
                  let references, remaining = gather id initial rest in
                  let preview_art_references =
                    preview_references ~seed:id references
                  in
                  let summary =
                    Model.
                      {
                        story =
                          {
                            id;
                            group_id;
                            tag;
                            tag_text;
                            code;
                            name;
                            info;
                            art_references = [];
                          };
                        representative_art_reference =
                          representative_reference preview_art_references;
                        preview_art_references;
                      }
                  in
                  decode (summary :: summaries) remaining
            in
            Ok (decode [] rows)
      in
      let story_group locale id =
        use (fun (module Db) ->
            Db.collect_list Query.story_group ((locale, id), (locale, id)))
        >|= function
        | Error error -> Error error
        | Ok [] -> Error `Not_found
        | Ok ((id, (name, (group_type, _))) :: _ as rows) ->
            let art_references =
              rows
              |> List.filter_map (fun (_, (_, (_, reference))) ->
                     reference_from_columns reference)
              |> unique_references
            in
            let preview_art_references =
              art_references
              |> List.filter (fun (reference : Model.art_reference) ->
                     Option.is_some reference.composition_object_key)
              |> preview_references ~seed:id
            in
            Ok
              Model.
                {
                  group = { id; name; group_type };
                  representative_art_reference =
                    representative_reference preview_art_references;
                  preview_art_references;
                  art_references;
                }
      in
      let story locale id =
        use (fun (module Db) -> Db.collect_list Query.story (locale, id))
        >|= function
        | Error error -> Error error
        | Ok [] -> Error `Not_found
        | Ok
            ((group_id, (tag, (tag_text, (code, (name, (info, _)))))) :: _ as rows)
          ->
            let art_references =
              List.filter_map
                (fun (_, (_, (_, (_, (_, (_, reference)))))) ->
                  reference_from_columns reference)
                rows
            in
            Ok Model.{ id; group_id; tag; tag_text; code; name; info; art_references }
      in
      let galleries locale =
        use (fun (module Db) -> Db.collect_list Query.galleries locale)
        >|= Result.map (fun rows ->
                List.map
                  (fun (id, (name, description)) ->
                    Model.{ id; name; description; entries = [] })
                  rows)
      in
      let gallery locale id =
        use (fun (module Db) -> Db.collect_list Query.gallery (locale, id))
        >|= function
        | Error error -> Error error
        | Ok [] -> Error `Not_found
        | Ok ((id, (name, (description, _))) :: _ as rows) ->
            let entries =
              List.filter_map
                (fun
                  ( _,
                    ( _,
                      ( _,
                        ( entry_id,
                          ( position,
                            ( name,
                              ( description,
                                (art_id, (category, object_key)) ) ) ) ) ) ) ) ->
                  match (entry_id, position, name, description, art_id, category) with
                  | ( Some id,
                      Some position,
                      Some name,
                      Some description,
                      Some art_id,
                      Some category ) ->
                      Some
                        Model.
                          {
                            id;
                            position;
                            name;
                            description;
                            art_id;
                            category;
                            composition_object_key = object_key;
                          }
                  | _ -> None)
                rows
            in
            Ok Model.{ id; name; description; entries }
      in
      Ok
        {
          close = idempotent_close (fun () -> Caqti_lwt_unix.Pool.drain pool);
          check;
          health;
          art;
          source_art;
          story_groups;
          stories_by_group;
          story_group;
          story;
          galleries;
          gallery;
        }

let remove_if_exists path =
  try Sys.remove path with Sys_error _ -> ()

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
  (* A cache directory belongs to one service process. Files matching this
     managed prefix are incomplete or retired generations from an earlier
     process and are safe to remove before the initial download. *)
  Sys.readdir path
  |> Array.iter (fun name ->
         if
           String.starts_with ~prefix:"arkwaifu-" name
           &&
           (String.ends_with ~suffix:".sqlite3" name
           || String.ends_with ~suffix:".sqlite3.part" name)
         then remove_if_exists (Filename.concat path name))

type generation = { database : t; path : string }

let download_generation ~url ~cache_dir ~counter ~etag ~timeout_seconds =
  (* Download to a .part file and rename it before opening SQLite. A candidate
     is returned only after its schema version has been admitted; every failure
     closes the candidate and removes both paths. *)
  let name = Printf.sprintf "arkwaifu-%d-%d.sqlite3" (Unix.getpid ()) counter in
  let path = Filename.concat cache_dir name in
  let part = path ^ ".part" in
  let headers =
    match etag with
    | None -> Cohttp.Header.init ()
    | Some value -> Cohttp.Header.init_with "if-none-match" value
  in
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
    Cohttp_lwt_unix.Client.get ~headers url >>= fun (response, body) ->
    match Cohttp.Response.status response with
    | `Not_modified ->
        Cohttp_lwt.Body.drain_body body >|= fun () -> `Not_modified
    | `OK ->
        Lwt_io.with_file ~mode:Lwt_io.Output part (fun channel ->
            Cohttp_lwt.Body.to_stream body
            |> Lwt_stream.iter_s (Lwt_io.write channel))
        >>= fun () ->
        Sys.rename part path;
        let response_etag =
          Cohttp.Header.get (Cohttp.Response.headers response) "etag"
        in
        (match sqlite path with
        | Error error -> cleanup ("cannot open downloaded database: " ^ error)
        | Ok database ->
            candidate := Some database;
            database.check () >>= function
            | Error (`Unavailable error) -> cleanup error
            | Error `Not_found -> cleanup "database health check failed"
            | Ok () ->
                candidate := None;
                Lwt.return (`Fetched ({ database; path }, response_etag)))
    | status ->
        Cohttp_lwt.Body.drain_body body >>= fun () ->
        cleanup
          (Printf.sprintf "database download returned HTTP %s"
             (Cohttp.Code.string_of_status status))
  in
  Lwt.catch
    (fun () -> Lwt_unix.with_timeout timeout_seconds download)
    (function
      | Lwt_unix.Timeout ->
          cleanup
            (Printf.sprintf "database download timed out after %.0f seconds"
               timeout_seconds)
      | exception_ -> cleanup (Printexc.to_string exception_))

let live ~url ~cache_dir ~poll_seconds ~download_timeout_seconds =
  (* Keep one readable local generation current. Pool draining lets queries
     already using the previous generation finish before its file is removed. *)
  try
    make_directory cache_dir;
    clean_database_cache cache_dir;
    download_generation ~url ~cache_dir ~counter:0 ~etag:None
      ~timeout_seconds:download_timeout_seconds
    >>= function
    | `Not_modified -> Lwt.return (Error "database was not downloaded at startup")
    | `Failed error -> Lwt.return (Error error)
    | `Fetched (first, first_etag) ->
        let current = ref first in
        let etag = ref first_etag in
        let closed = ref false in
        let counter = ref 1 in
        let retire generation =
          generation.database.close () >|= fun () -> remove_if_exists generation.path
        in
        let rec poll () =
          if !closed then Lwt.return_unit
          else
            Lwt_unix.sleep poll_seconds >>= fun () ->
            let next = !counter in
            incr counter;
            download_generation ~url ~cache_dir ~counter:next ~etag:!etag
              ~timeout_seconds:download_timeout_seconds
            >>= fun result ->
            (match result with
            | `Not_modified -> Lwt.return_unit
            | `Failed error ->
                if not !closed then
                  Printf.eprintf "database refresh failed: %s\n%!" error;
                Lwt.return_unit
            | `Fetched (fresh, fresh_etag) ->
                if !closed then retire fresh
                else
                  let previous = !current in
                  current := fresh;
                  etag := fresh_etag;
                  Lwt.async (fun () -> retire previous);
                  Lwt.return_unit)
            >>= poll
        in
        let poll_task = poll () in
        Lwt.async (fun () -> poll_task);
        let with_current callback = callback (!current).database in
        let close_task = ref None in
        let close () =
          match !close_task with
          | Some task -> task
          | None ->
              closed := true;
              Lwt.cancel poll_task;
              let task =
                Lwt.catch
                  (fun () -> poll_task)
                  (function Lwt.Canceled -> Lwt.return_unit | error -> Lwt.fail error)
                >>= fun () -> retire !current
              in
              close_task := Some task;
              task
        in
        let database =
          {
            close;
            check = (fun () -> with_current (fun value -> value.check ()));
            health = (fun () -> with_current (fun value -> value.health ()));
            art = (fun category id -> with_current (fun value -> value.art category id));
            source_art =
              (fun id -> with_current (fun value -> value.source_art id));
            story_groups =
              (fun locale -> with_current (fun value -> value.story_groups locale));
            stories_by_group =
              (fun locale group_id ->
                with_current (fun value -> value.stories_by_group locale group_id));
            story_group =
              (fun locale id ->
                with_current (fun value -> value.story_group locale id));
            story =
              (fun locale id -> with_current (fun value -> value.story locale id));
            galleries =
              (fun locale -> with_current (fun value -> value.galleries locale));
            gallery =
              (fun locale id -> with_current (fun value -> value.gallery locale id));
          }
        in
        Lwt.return (Ok database)
  with Sys_error error -> Lwt.return (Error error)

let close (database : t) = database.close ()
let health (database : t) = database.health ()
let art (database : t) category id = database.art category id
let source_art (database : t) id = database.source_art id
let story_groups (database : t) locale = database.story_groups locale
let stories_by_group (database : t) locale group_id =
  database.stories_by_group locale group_id

let story_group (database : t) locale id = database.story_group locale id
let story (database : t) locale id = database.story locale id
let galleries (database : t) locale = database.galleries locale
let gallery (database : t) locale id = database.gallery locale id
