(** Start the live SQLite reader before accepting HTTP requests. *)

let fail message =
  prerr_endline message;
  exit 1

let () =
  let config =
    match Arkwaifu_service.Config.load () with Ok value -> value | Error error -> fail error
  in
  let database =
    match
      Lwt_main.run
        (Arkwaifu_service.Database.live ~url:config.database_url
           ~cache_dir:config.database_cache_dir
           ~poll_seconds:config.database_poll_seconds
           ~download_timeout_seconds:config.database_download_timeout_seconds)
    with
    | Ok value -> value
    | Error error -> fail ("cannot load SQLite database: " ^ error)
  in
  Dream.run ~interface:config.interface ~port:config.port
  @@ Dream.logger
  @@ Arkwaifu_service.Http.routes ~database ~object_base_url:config.object_base_url
