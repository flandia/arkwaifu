(** Validated runtime configuration for the HTTP service and database refresh
    loop. *)

type t = {
  database_url : Uri.t;
      (** Absolute HTTP or HTTPS URL of the current [arkwaifu.sqlite3] object.
      *)
  database_cache_dir : string;
      (** Process-private directory for downloaded SQLite generations. *)
  database_poll_seconds : float;
      (** Positive delay between refresh attempts, in seconds. *)
  database_download_timeout_seconds : float;
      (** Positive timeout for one complete database download, in seconds. *)
  object_base_url : string;
      (** Absolute HTTP or HTTPS public bucket or content delivery network base
          URL. *)
  interface : string;  (** Network interface passed to [Dream.run]. *)
  port : int;  (** TCP port in the inclusive range 1 through 65,535. *)
}
(** Runtime configuration loaded by {!load}.

    String values retain their configured form except for defaults derived by
    {!load}. Durations use seconds. *)

val load : unit -> (t, string) result
(** [load ()] reads and validates the [ARKWAIFU_*] environment variables.

    It returns [Error message] when a required value is missing, either URL is
    not absolute HTTP or HTTPS, [port] is outside 1 through 65,535, or either
    duration is not positive. *)
