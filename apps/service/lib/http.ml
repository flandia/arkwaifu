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

let redirect_to_content ~object_base_url request get_image = function
  | Ok value ->
      let image : Model.object_metadata = get_image value in
      Dream.redirect request
        (Model.content_url ~object_base_url image.object_key)
  | Error error -> database_error error

let locales = [ "CN"; "EN"; "JP"; "KR"; "TW" ]

let locale request =
  let value = String.uppercase_ascii (Dream.param request "locale") in
  if List.mem value locales then Ok value else Error `Not_found

let with_locale request callback =
  match locale request with
  | Ok value -> callback value
  | Error `Not_found -> error_json `Not_Found "not_found"

let routes ~database ~object_base_url =
  let art request =
    Database.art database (Dream.param request "category") (Dream.param request "id")
    >>= respond (Model.art_json ~object_base_url)
  in
  let art_content request =
    Database.art database (Dream.param request "category") (Dream.param request "id")
    >>= redirect_to_content ~object_base_url request (fun (art : Model.art) ->
            art.image)
  in
  let source_art request =
    Database.source_art database (Dream.param request "id")
    >>= respond (Model.source_art_json ~object_base_url)
  in
  let source_art_content request =
    Database.source_art database (Dream.param request "id")
    >>= redirect_to_content ~object_base_url request
          (fun (source : Model.source_art) -> source.image)
  in
  Dream.router
    [
      Dream.get "/health" (fun _ ->
          Database.health database
          >>= respond (fun () -> `Assoc [ ("status", `String "ok") ]));
      Dream.get "/api/arts/:category/:id" art;
      Dream.get "/api/arts/:category/:id/content" art_content;
      Dream.get "/api/source-arts/:id" source_art;
      Dream.get "/api/source-arts/:id/content" source_art_content;
      Dream.get "/api/:locale/story-groups" (fun request ->
          with_locale request (fun locale ->
              Database.story_groups database locale
              >>= respond (fun groups ->
                      `List (List.map Model.story_group_json groups))));
      Dream.get "/api/:locale/stories/:id" (fun request ->
          with_locale request (fun locale ->
              Database.story database locale (Dream.param request "id")
              >>= respond Model.story_json));
      Dream.get "/api/:locale/galleries" (fun request ->
          with_locale request (fun locale ->
              Database.galleries database locale
              >>= respond (fun galleries ->
                      `List (List.map Model.gallery_summary_json galleries))));
      Dream.get "/api/:locale/galleries/:id" (fun request ->
          with_locale request (fun locale ->
              Database.gallery database locale (Dream.param request "id")
              >>= respond Model.gallery_json));
    ]
