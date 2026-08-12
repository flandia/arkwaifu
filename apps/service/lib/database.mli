(** Read the current Arkwaifu database through one stable query interface. *)

(** Lookup errors distinguish absent records from an unavailable database. *)
type error =
  [ `Not_found
  | `Unavailable of string
  ]

type t

(** Open one SQLite file read-only. The caller owns the file until [close]. The
    [live] reader checks schema compatibility before exposing this reader. *)
val sqlite : string -> (t, string) result

(** Download and serve a changing remote SQLite database.

    The initial download must succeed. Later refresh failures keep the last
    compatible local generation. Every downloaded generation is admitted by
    schema version before it can serve queries. *)
val live :
  url:Uri.t ->
  cache_dir:string ->
  poll_seconds:float ->
  download_timeout_seconds:float ->
  (t, string) result Lwt.t

(** Narrow test access to the production refresh state machine. The callback
    writes a fetched database to [destination]; no test-only query model is
    involved. *)
module For_test : sig
  type fetch_result =
    [ `Not_modified
    | `Fetched of string option
    | `Failed of string
    ]

  type refresh_result =
    [ `Not_modified
    | `Replaced
    | `Failed of string
    ]

  type controlled_live = {
    database : t;
    refresh_once : unit -> refresh_result Lwt.t;
  }

  val live :
    fetch:(etag:string option -> destination:string -> fetch_result Lwt.t) ->
    cache_dir:string ->
    download_timeout_seconds:float ->
    (controlled_live, string) result Lwt.t

  (** Open SQLite with an observer called for every pool acquisition. *)
  val sqlite_with_pool_observer :
    on_acquire:(unit -> unit) -> string -> (t, string) result
end

(** Release the reader. A live reader also stops polling and removes its managed
    file. *)
val close : t -> unit Lwt.t

(** Check whether the current reader is available. *)
val health : t -> (unit, error) result Lwt.t

(** Get one final art record by category and logical identifier. *)
val art : t -> string -> string -> (Model.art, error) result Lwt.t

(** Get one original source art record by its logical identifier. *)
val source_art : t -> string -> (Model.source_art, error) result Lwt.t

(** List every indexed art absent from every locale's stories and galleries.
    Results are ordered by image, background, item, character, then art ID. *)
val unclassified_arts : t -> (Model.unclassified_art list, error) result Lwt.t

(** Get localized names, character siblings, and story occurrences for one
    available art. *)
val art_context :
  t -> string -> string -> string -> (Model.art_context, error) result Lwt.t

(** List ordered story groups for a locale such as ["CN"] or ["EN"]. Each
    summary includes up to three available previews, prioritizing references
    used by fewer distinct groups and using a stable shuffle for ties. If any
    illustration is available, previews contain illustrations only; otherwise
    they contain backgrounds. The representative is the first preview. *)
val story_groups :
  t -> string -> (Model.story_group_summary list, error) result Lwt.t

(** List ordered story summaries in one localized group. [art_references]
    remains empty. Each summary includes up to three previews, prioritizing
    references used by fewer distinct stories and otherwise using the same
    preference as [story_groups]. Its representative is the first preview. A
    missing group returns [`Not_found]. *)
val stories_by_group :
  t -> string -> string -> (Model.story_summary list, error) result Lwt.t

(** Get one group, its preview references, and every available art reference
    across its stories, deduplicated by category and art ID. *)
val story_group :
  t -> string -> string -> (Model.story_group_detail, error) result Lwt.t

(** Get one story from the selected locale. *)
val story : t -> string -> string -> (Model.story, error) result Lwt.t

(** List gallery summaries for the selected locale. Each summary includes up to
    three stable preview thumbnails. Available illustrations are preferred;
    backgrounds are used only when no illustration is available. *)
val galleries : t -> string -> (Model.gallery_summary list, error) result Lwt.t

(** Get one gallery and its ordered entries from the selected locale. *)
val gallery : t -> string -> string -> (Model.gallery, error) result Lwt.t
