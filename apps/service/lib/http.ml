(** Dream routes for narrative_image_asset, Scores, Archives, galleries, and health. *)

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

let archive_categories =
  [
    "events";
    "operator-record";
    "integrated-strategies";
    "reclamation-algorithm";
    "others";
  ]

let archive_route_of_database_category = function
  | "events" -> "events"
  | "operator_record" -> "operator-record"
  | "integrated_strategies" -> "integrated-strategies"
  | "reclamation_algorithm" -> "reclamation-algorithm"
  | "others" -> "others"
  | value -> invalid_arg ("unknown Archive Category: " ^ value)

let sitemap_text (data : Database.sitemap_data) =
  let origin = "https://arkwaifu.cc" in
  let encode =
    Uri.pct_encode ~component:(`Custom (`Path, "", "$&+,;=:@"))
  in
  let locale_paths =
    locales
    |> List.concat_map (fun locale ->
           [
             Printf.sprintf "%s/%s" origin locale;
             Printf.sprintf "%s/%s/scores" origin locale;
             Printf.sprintf "%s/%s/archives" origin locale;
             Printf.sprintf "%s/%s/galleries" origin locale;
             Printf.sprintf "%s/%s/about" origin locale;
             Printf.sprintf "%s/%s/orphans" origin locale;
             Printf.sprintf "%s/%s/assets/presentation" origin locale;
           ]
           @ List.map
               (fun category ->
                 Printf.sprintf "%s/%s/archives/%s" origin locale category)
               archive_categories)
  in
  let movement_paths =
    data.movements
    |> List.map (fun (locale, movement_id) ->
           Printf.sprintf "%s/%s/scores/%s" origin locale (encode movement_id))
  in
  let section_paths =
    data.sections
    |> List.map (fun (locale, movement_id, section_id) ->
           Printf.sprintf "%s/%s/scores/%s/%s" origin locale
             (encode movement_id) (encode section_id))
  in
  let archive_paths =
    data.archive_groups
    |> List.map (fun (locale, category, id) ->
           Printf.sprintf "%s/%s/archives/%s/%s" origin locale
             (archive_route_of_database_category category)
             (encode id))
  in
  let gallery_paths =
    data.galleries
    |> List.map (fun (locale, id) ->
           Printf.sprintf "%s/%s/galleries/%s" origin locale (encode id))
  in
  let paths =
    List.sort_uniq String.compare
      (locale_paths @ movement_paths @ section_paths @ archive_paths
     @ gallery_paths)
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

let archive_category request =
  let value = Dream.param request "archive-category" in
  if List.mem value archive_categories then Ok value else Error `Not_found

let with_archive_category request callback =
  match archive_category request with
  | Ok value -> callback value
  | Error `Not_found -> error_json `Not_Found "not_found"

let add_public_read_headers response =
  Dream.set_header response "Access-Control-Allow-Origin" "*";
  Dream.set_header response "Access-Control-Allow-Methods" "GET, OPTIONS";
  Dream.set_header response "Access-Control-Allow-Headers"
    "Accept, Content-Type";
  Dream.set_header response "Access-Control-Max-Age" "86400";
  Dream.set_header response "Vary" "X-Forwarded-Host";
  response

let public_read_cors inner_handler request =
  (if Dream.methods_equal (Dream.method_ request) `OPTIONS then
     Dream.empty `No_Content
   else inner_handler request)
  >|= add_public_read_headers

let routes ?china_object_base_url ~database ~object_base_url =
  let request_object_base_url request =
    match (china_object_base_url, Dream.header request "X-Forwarded-Host") with
    | Some mirror_url, Some forwarded_host
      when String.equal
             (String.lowercase_ascii (String.trim forwarded_host))
             "api.cn.arkwaifu.cc" ->
        mirror_url
    | _ -> object_base_url
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
  let object_url request = request_object_base_url request in
  public_read_cors
  @@ Dream.router
       [
         Dream.get "/health" (fun _ ->
             Database.health database
             >>= respond (fun () -> `Assoc [ ("status", `String "ok") ]));
         Dream.get "/sitemap.txt" sitemap;
         Dream.head "/sitemap.txt" sitemap;
         Dream.get "/api/assets/narrative/:asset-category/:asset-id" (fun request ->
             let object_base_url = object_url request in
             let category = Dream.param request "asset-category" in
             let id = Dream.param request "asset-id" in
             if List.mem category [ "audio"; "video" ] then
               Database.narrative_media_asset database category id
               >>= respond (Model.narrative_media_asset_json ~object_base_url)
             else
               Database.narrative_image_asset database category id
               >>= respond (Model.narrative_image_asset_json ~object_base_url));
         Dream.get "/api/assets/material/:asset-category/:asset-id" (fun request ->
             let object_base_url = object_url request in
             Database.material_asset database
               (Dream.param request "asset-category")
               (Dream.param request "asset-id")
             >>= respond (Model.material_asset_json ~object_base_url));
         Dream.get "/api/:locale/orphans" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 Database.orphan_narrative_image_assets database locale
                 >>= function
                 | Error error -> database_error error
                 | Ok images ->
                     Database.orphan_narrative_media_assets database locale
                     >>= respond (fun media ->
                             `List
                               (List.map
                                  (Model.orphan_narrative_image_asset_json
                                     ~object_base_url)
                                  images
                               @ List.map
                                   (Model.orphan_narrative_media_asset_json
                                      ~object_base_url)
                                   media))));
         Dream.get "/api/:locale/assets/presentation" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 Database.presentation_assets database locale
                 >>= respond (fun assets ->
                         let category = Dream.query request "category" in
                         let format = Dream.query request "format" in
                         let orphaned =
                           Dream.query request "orphaned"
                           |> Option.map (String.equal "true")
                         in
                         assets
                         |> List.filter (fun (asset : Model.presentation_asset) ->
                                Option.fold ~none:true
                                  ~some:(String.equal asset.category)
                                  category
                                && Option.fold ~none:true
                                     ~some:(String.equal asset.format)
                                     format
                                && Option.fold ~none:true
                                     ~some:(fun value ->
                                       Bool.equal value
                                         (asset.reference_count = 0))
                                     orphaned)
                         |> List.map
                              (Model.presentation_asset_summary_json
                                 ~object_base_url)
                         |> fun values -> `List values)));
         Dream.get
           "/api/:locale/assets/presentation/:asset-category/:asset-id"
           (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 Database.presentation_asset database locale
                   (Dream.param request "asset-category")
                   (Dream.param request "asset-id")
                 >>= respond
                       (Model.presentation_asset_detail_json
                          ~object_base_url)));
         Dream.get "/api/:locale/search" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 let query = Dream.query request "q" |> Option.value ~default:"" in
                 Database.search database locale query
                 >>= respond (fun results ->
                         `List
                           (List.map
                              (Model.search_result_json ~object_base_url)
                              results))));
         Dream.get
           "/api/:locale/assets/narrative/:asset-category/:asset-id/reverse-references"
           (fun request ->
             let category = Dream.param request "asset-category" in
             let id = Dream.param request "asset-id" in
             with_locale request (fun locale ->
                 if List.mem category [ "audio"; "video" ] then
                   Database.narrative_media_asset_reverse_references database locale category id
                   >>= respond Model.narrative_media_asset_reverse_references_json
                 else
                   let object_base_url = object_url request in
                   Database.narrative_image_asset_reverse_references database locale category id
                   >>= respond
                         (Model.narrative_image_asset_reverse_references_json
                            ~object_base_url)));
         Dream.get "/api/:locale/scores" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 Database.movements database locale
                 >>= respond (fun movements ->
                         `List
                           (List.map
                              (Model.movement_json ~object_base_url)
                              movements))));
         Dream.get "/api/:locale/scores/:movement-id" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 Database.movement database locale
                   (Dream.param request "movement-id")
                 >>= respond (Model.movement_detail_json ~object_base_url)));
         Dream.get "/api/:locale/scores/:movement-id/:section-id" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 Database.section database locale
                   (Dream.param request "movement-id")
                   (Dream.param request "section-id")
                 >>= respond
                       (Model.section_detail_json ~object_base_url)));
         Dream.get
           "/api/:locale/scores/:movement-id/:section-id/:story-id"
           (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 Database.score_story database locale
                   (Dream.param request "movement-id")
                   (Dream.param request "section-id")
                   (Dream.param request "story-id")
                 >>= respond (Model.story_detail_json ~object_base_url)));
         Dream.get "/api/:locale/archives" (fun request ->
             with_locale request (fun locale ->
                 Database.archive_index database locale
                 >>= respond (fun entries ->
                         `List (List.map Model.archive_index_entry_json entries))));
         Dream.get "/api/:locale/archives/:archive-category" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 with_archive_category request (fun category ->
                     Database.archive_groups database locale category
                     >>= respond (fun groups ->
                             `List
                               (List.map
                                  (Model.archive_group_summary_json
                                     ~object_base_url)
                                  groups)))));
         Dream.get "/api/:locale/archives/:archive-category/:group-id" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 with_archive_category request (fun category ->
                     Database.archive_group database locale category
                       (Dream.param request "group-id")
                     >>= respond
                           (Model.archive_group_detail_json ~object_base_url))));
         Dream.get
           "/api/:locale/archives/:archive-category/:group-id/:story-id"
           (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 with_archive_category request (fun category ->
                     Database.archive_story database locale category
                       (Dream.param request "group-id")
                       (Dream.param request "story-id")
                     >>= respond (Model.story_detail_json ~object_base_url))));
         Dream.get "/api/:locale/galleries" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 Database.galleries database locale
                 >>= respond (fun galleries ->
                         `List
                           (List.map
                              (Model.gallery_summary_json ~object_base_url)
                              galleries))));
         Dream.get "/api/:locale/galleries/:gallery-id" (fun request ->
             let object_base_url = object_url request in
             with_locale request (fun locale ->
                 Database.gallery database locale (Dream.param request "gallery-id")
                 >>= respond (Model.gallery_json ~object_base_url)));
       ]
