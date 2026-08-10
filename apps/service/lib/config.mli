(** Runtime settings loaded from the process environment. *)
type t = {
  database_url : Uri.t;
  database_cache_dir : string;
  database_poll_seconds : float;
  database_download_timeout_seconds : float;
  object_base_url : string;
  interface : string;
  port : int;
}

(** Load and validate the HTTP and database-refresh settings. *)
val load : unit -> (t, string) result
