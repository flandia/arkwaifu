(** Dream routes for art collections, localized stories, galleries, and health.
*)

open Lwt.Infix

let json ?(status = `OK) value =
  Dream.json ~status (Yojson.Safe.to_string value)

let error_json status code = json ~status (`Assoc [ ("error", `String code) ])

let database_error = function
  | `Not_found -> error_json `Not_Found "not_found"
  | `Unavailable message ->
      Dream.log "database unavailable: %s" message;
      error_json `Service_Unavailable "service_unavailable"

let encode_response encode value =
  try Ok (encode value) with Invalid_argument message -> Error message

let respond encode = function
  | Ok value -> (
      match encode_response encode value with
      | Ok encoded -> json encoded
      | Error message -> database_error (`Unavailable message))
  | Error error -> database_error error

let locales = [ "CN"; "EN"; "JP"; "KR"; "TW" ]

let story_sections =
  [
    ("main_story", "main");
    ("major_event", "events");
    ("minor_event", "vignettes");
    ("operator_record", "records");
    ("integrated_strategies", "integrated-strategies");
    ("reclamation_algorithm", "reclamation-algorithm");
    ("others", "others");
  ]

let story_section group_type =
  match List.assoc_opt group_type story_sections with
  | Some value -> value
  | None -> invalid_arg ("unknown story group type: " ^ group_type)

let sitemap_text (data : Database.sitemap_data) =
  let origin = "https://arkwaifu.cc" in
  (* Match encodeURIComponent, which the web client uses for one route segment. *)
  let encode =
    Uri.pct_encode ~component:(`Custom (`Path, "", "$&+,;=:@"))
  in
  let locale_paths =
    locales
    |> List.concat_map (fun locale ->
        (origin ^ "/" ^ locale)
        :: (List.map
              (fun (_, section) ->
                Printf.sprintf "%s/%s/stories/%s" origin locale section)
              story_sections
           @ [ Printf.sprintf "%s/%s/galleries" origin locale ]))
  in
  let story_paths =
    List.map
      (fun (locale, id, group_type) ->
        Printf.sprintf "%s/%s/stories/%s/%s" origin locale
          (story_section group_type) (encode id))
      data.story_groups
  in
  let gallery_paths =
    List.map
      (fun (locale, id) ->
        Printf.sprintf "%s/%s/galleries/%s" origin locale (encode id))
      data.galleries
  in
  let paths =
    List.sort_uniq String.compare
      ([ origin ^ "/CN/about"; origin ^ "/CN/unreferenced" ]
      @ locale_paths @ story_paths @ gallery_paths)
  in
  if List.length paths > 50_000 then invalid_arg "sitemap exceeds 50,000 URLs";
  let body = String.concat "\n" paths ^ "\n" in
  if String.length body > 52_428_800 then
    invalid_arg "sitemap exceeds 50 MiB";
  body

let locale request =
  let value = String.uppercase_ascii (Dream.param request "locale") in
  if List.mem value locales then Ok value else Error `Not_found

let with_locale request callback =
  match locale request with
  | Ok value -> callback value
  | Error `Not_found -> error_json `Not_Found "not_found"

let add_public_read_headers response =
  Dream.set_header response "Access-Control-Allow-Origin" "*";
  Dream.set_header response "Access-Control-Allow-Methods" "GET, OPTIONS";
  Dream.set_header response "Access-Control-Allow-Headers"
    "Accept, Content-Type";
  Dream.set_header response "Access-Control-Max-Age" "86400";
  response

let public_read_cors inner_handler request =
  (if Dream.methods_equal (Dream.method_ request) `OPTIONS then
     Dream.empty `No_Content
   else inner_handler request)
  >|= add_public_read_headers

let routes ~database ~object_base_url =
  let art request =
    Database.art database
      (Dream.param request "category")
      (Dream.param request "id")
    >>= respond (Model.art_json ~object_base_url)
  in
  let source_art request =
    Database.source_art database (Dream.param request "id")
    >>= respond (Model.source_art_json ~object_base_url)
  in
  let unreferenced_arts _ =
    Database.unreferenced_arts database
    >>= respond (fun arts ->
        `List (List.map (Model.unreferenced_art_json ~object_base_url) arts))
  in
  let sitemap _ =
    Database.sitemap_data database >>= function
    | Error error -> database_error error
    | Ok data -> (
        match encode_response sitemap_text data with
        | Error message -> database_error (`Unavailable message)
        | Ok body ->
            Dream.respond
              ~headers:[ ("Content-Type", "text/plain; charset=utf-8") ]
              body)
  in
  public_read_cors
  @@ Dream.router
       [
         Dream.get "/health" (fun _ ->
             Database.health database
             >>= respond (fun () -> `Assoc [ ("status", `String "ok") ]));
         Dream.get "/sitemap.txt" sitemap;
         Dream.get "/api/arts/:category/:id" art;
         Dream.get "/api/source-arts/:id" source_art;
         Dream.get "/api/unreferenced-arts" unreferenced_arts;
         Dream.get "/api/:locale/arts/:category/:id/context" (fun request ->
             with_locale request (fun locale ->
                 Database.art_context database locale
                   (Dream.param request "category")
                   (Dream.param request "id")
                 >>= respond (Model.art_context_json ~object_base_url)));
         Dream.get "/api/:locale/story-groups" (fun request ->
             with_locale request (fun locale ->
                 Database.story_groups database locale
                 >>= respond (fun groups ->
                     `List
                       (List.map
                          (Model.story_group_summary_json ~object_base_url)
                          groups))));
         Dream.get "/api/:locale/story-groups/:id" (fun request ->
             with_locale request (fun locale ->
                 Database.story_group database locale (Dream.param request "id")
                 >>= respond (Model.story_group_detail_json ~object_base_url)));
         Dream.get "/api/:locale/story-groups/:id/stories" (fun request ->
             with_locale request (fun locale ->
                 Database.stories_by_group database locale
                   (Dream.param request "id")
                 >>= respond (fun stories ->
                     `List
                       (List.map
                          (Model.story_summary_json ~object_base_url)
                          stories))));
         Dream.get "/api/:locale/stories/:id" (fun request ->
             with_locale request (fun locale ->
                 Database.story database locale (Dream.param request "id")
                 >>= respond (Model.story_json ~object_base_url)));
         Dream.get "/api/:locale/galleries" (fun request ->
             with_locale request (fun locale ->
                 Database.galleries database locale
                 >>= respond (fun galleries ->
                     `List
                       (List.map
                          (Model.gallery_summary_json ~object_base_url)
                          galleries))));
         Dream.get "/api/:locale/galleries/:id" (fun request ->
             with_locale request (fun locale ->
                 Database.gallery database locale (Dream.param request "id")
                 >>= respond (Model.gallery_json ~object_base_url)));
       ]
