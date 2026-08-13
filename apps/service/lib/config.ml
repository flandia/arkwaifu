(** Environment-backed configuration for the HTTP reader. *)

type t = {
  database_url : Uri.t;
  database_cache_dir : string;
  database_poll_seconds : float;
  database_download_timeout_seconds : float;
  object_base_url : string;
  china_object_base_url : string option;
  interface : string;
  port : int;
}

let required name =
  match Sys.getenv_opt name with
  | Some value when not (String.equal value "") -> Ok value
  | _ ->
      Error (Printf.sprintf "required environment variable is not set: %s" name)

let trim_trailing_slash value =
  if String.length value > 0 && value.[String.length value - 1] = '/' then
    String.sub value 0 (String.length value - 1)
  else value

let http_uri name value =
  let invalid () =
    Error (Printf.sprintf "%s must be an absolute HTTP or HTTPS URL" name)
  in
  try
    let uri = Uri.of_string value in
    match (Uri.scheme uri, Uri.host uri) with
    | Some scheme, Some host
      when (not (String.equal host ""))
           && List.mem (String.lowercase_ascii scheme) [ "http"; "https" ] ->
        Ok uri
    | _ -> invalid ()
  with Invalid_argument _ -> invalid ()

let optional_http_url name =
  match Sys.getenv_opt name with
  | None | Some "" -> Ok None
  | Some value -> Result.map (fun _ -> Some value) (http_uri name value)

let load () =
  match required "ARKWAIFU_OBJECT_BASE_URL" with
  | Error error -> Error error
  | Ok object_base_url -> (
      match http_uri "ARKWAIFU_OBJECT_BASE_URL" object_base_url with
      | Error error -> Error error
      | Ok _ -> (
          match optional_http_url "ARKWAIFU_CN_OBJECT_BASE_URL" with
          | Error error -> Error error
          | Ok china_object_base_url ->
          let interface =
            Option.value ~default:"0.0.0.0"
              (Sys.getenv_opt "ARKWAIFU_INTERFACE")
          in
          let raw_port =
            Option.value ~default:"8080" (Sys.getenv_opt "ARKWAIFU_PORT")
          in
          let raw_poll =
            Option.value ~default:"30"
              (Sys.getenv_opt "ARKWAIFU_DATABASE_POLL_SECONDS")
          in
          let raw_download_timeout =
            Option.value ~default:"600"
              (Sys.getenv_opt "ARKWAIFU_DATABASE_DOWNLOAD_TIMEOUT_SECONDS")
          in
          match
            ( int_of_string_opt raw_port,
              float_of_string_opt raw_poll,
              float_of_string_opt raw_download_timeout )
          with
          | ( Some port,
              Some database_poll_seconds,
              Some database_download_timeout_seconds )
            when port > 0 && port <= 65535 && database_poll_seconds > 0.
                 && database_download_timeout_seconds > 0. -> (
              let database_url =
                Option.value
                  ~default:
                    (trim_trailing_slash object_base_url ^ "/arkwaifu.sqlite3")
                  (Sys.getenv_opt "ARKWAIFU_DATABASE_URL")
              in
              let database_cache_dir =
                Option.value ~default:"/var/lib/arkwaifu/database"
                  (Sys.getenv_opt "ARKWAIFU_DATABASE_CACHE_DIR")
              in
              match http_uri "ARKWAIFU_DATABASE_URL" database_url with
              | Error error -> Error error
              | Ok database_url ->
                  Ok
                    {
                      database_url;
                      database_cache_dir;
                      database_poll_seconds;
                      database_download_timeout_seconds;
                      object_base_url;
                      china_object_base_url;
                      interface;
                      port;
                    })
          | _ ->
              Error
                (Printf.sprintf
                   "ARKWAIFU_PORT must be an integer from 1 through 65535, and \
                    ARKWAIFU_DATABASE_POLL_SECONDS and \
                    ARKWAIFU_DATABASE_DOWNLOAD_TIMEOUT_SECONDS must be \
                    positive numbers; got %S, %S, and %S"
                   raw_port raw_poll raw_download_timeout)))
