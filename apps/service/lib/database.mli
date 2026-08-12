(** Read the current Arkwaifu database through one stable query interface. *)

(** Lookup errors distinguish absent records from an unavailable database. *)
type error = [ `Not_found | `Unavailable of string ]
type t

(** In-memory records used by deterministic reader tests. *)
type snapshot = {
  arts : Model.art list;
  source_arts : Model.source_art list;
  story_groups : (string * Model.story_group list) list;
  stories : (string * Model.story list) list;
  galleries : (string * Model.gallery list) list;
}

(** The empty in-memory database used as a base by small reader tests. *)
val empty_snapshot : snapshot

(** Build a reader over an in-memory snapshot. *)
val memory : snapshot -> t

(** Open one SQLite file read-only. The caller owns the file until [close].
    The [live] reader checks schema compatibility before exposing this reader. *)
val sqlite : string -> (t, string) result

(** Download and serve a changing remote SQLite database.

    The initial download must succeed. Later refresh failures keep the last
    compatible local generation. Every downloaded generation is admitted by schema
    version before it can serve queries. *)
val live :
  url:Uri.t ->
  cache_dir:string ->
  poll_seconds:float ->
  download_timeout_seconds:float ->
  (t, string) result Lwt.t

(** Release the reader. A live reader also stops polling and removes its managed file. *)
val close : t -> unit Lwt.t

(** Check whether the current reader is available. *)
val health : t -> (unit, error) result Lwt.t

(** Get one final art record by category and logical identifier. *)
val art : t -> string -> string -> (Model.art, error) result Lwt.t

(** Get one original source art record by its logical identifier. *)
val source_art : t -> string -> (Model.source_art, error) result Lwt.t

(** List ordered story groups for a locale such as ["CN"] or ["EN"]. *)
val story_groups : t -> string -> (Model.story_group list, error) result Lwt.t

(** List ordered story summaries in one localized group. Summary art-reference
    lists are empty. A missing group returns [`Not_found]. *)
val stories_by_group :
  t -> string -> string -> (Model.story list, error) result Lwt.t

(** Get one story from the selected locale. *)
val story : t -> string -> string -> (Model.story, error) result Lwt.t

(** List gallery summaries for the selected locale. *)
val galleries : t -> string -> (Model.gallery list, error) result Lwt.t

(** Get one gallery and its ordered entries from the selected locale. *)
val gallery : t -> string -> string -> (Model.gallery, error) result Lwt.t
