(** Dream routes for art, localized stories, galleries, and health. *)

open Lwt.Infix

let json ?(status = `OK) value =
  Dream.json ~status (Yojson.Safe.to_string value)

let error_json status code = json ~status (`Assoc [ ("error", `String code) ])

let database_error = function
  | `Not_found -> error_json `Not_Found "not_found"
  | `Unavailable message ->
      Dream.log "database unavailable: %s" message;
      error_json `Service_Unavailable "service_unavailable"

let respond encode = function
  | Ok value -> json (encode value)
  | Error error -> database_error error

let locales = [ "CN"; "EN"; "JP"; "KR"; "TW" ]

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
  Dream.set_header response "Access-Control-Allow-Headers" "Accept, Content-Type";
  Dream.set_header response "Access-Control-Max-Age" "86400";
  response

let public_read_cors inner_handler request =
  (if Dream.methods_equal (Dream.method_ request) `OPTIONS then
     Dream.empty `No_Content
   else inner_handler request)
  >|= add_public_read_headers

let routes ~database ~object_base_url =
  let art request =
    Database.art database (Dream.param request "category") (Dream.param request "id")
    >>= respond (Model.art_json ~object_base_url)
  in
  let source_art request =
    Database.source_art database (Dream.param request "id")
    >>= respond (Model.source_art_json ~object_base_url)
  in
  public_read_cors
  @@ Dream.router
       [
      Dream.get "/health" (fun _ ->
          Database.health database
          >>= respond (fun () -> `Assoc [ ("status", `String "ok") ]));
      Dream.get "/api/arts/:category/:id" art;
      Dream.get "/api/source-arts/:id" source_art;
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
              Database.stories_by_group database locale (Dream.param request "id")
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
                      `List (List.map Model.gallery_summary_json galleries))));
      Dream.get "/api/:locale/galleries/:id" (fun request ->
          with_locale request (fun locale ->
              Database.gallery database locale (Dream.param request "id")
              >>= respond (Model.gallery_json ~object_base_url)));
       ]
