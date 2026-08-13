(** Read-only access to one current Arkwaifu SQLite generation. *)

type error = [ `Not_found | `Unavailable of string ]
(** A query fails when the requested record is absent or the current SQLite
    reader cannot complete the query. [`Unavailable message] contains an
    internal diagnostic and must not be returned directly to web clients. *)

type t
(** A read-only database reader. Call {!close} when you no longer need it.

    Localized queries require the exact uppercase locale [CN], [EN], [JP], [KR],
    or [TW]. This module does not normalize locale values. *)

type sitemap_data = {
  story_groups : (string * string * string) list;
      (** [(locale, group_id, group_type)] rows. *)
  galleries : (string * string) list;  (** [(locale, gallery_id)] rows. *)
}
(** The minimal archive index needed to render the public sitemap. *)

val sqlite : string -> (t, string) result
(** [sqlite path] opens [path] through a read-only Caqti pool.

    The caller owns [path] and must keep it available until {!close} finishes.
    The function reports pool creation errors as [Error message]. Use {!health}
    or an application query to detect later connection failures. *)

val live :
  url:Uri.t ->
  cache_dir:string ->
  poll_seconds:float ->
  download_timeout_seconds:float ->
  (t, string) result Lwt.t
(** [live ~url ~cache_dir ~poll_seconds ~download_timeout_seconds] downloads and
    serves a changing remote SQLite database.

    The implementation uses a pool of at most 10 SQLite connections. Both
    durations use seconds and must be positive. The initial download and
    schema-version check must succeed before this function returns [Ok reader].
    Later failures preserve the last valid generation. A successful refresh
    drains the previous pool before removing its file.

    [cache_dir] belongs to this reader and must not be shared with another
    process. {!close} stops polling, drains the current pool, and removes the
    managed generation. Startup and filesystem failures return [Error message].
*)

(** Test access to the production refresh state machine. Application code should
    use {!live}. *)
module For_test : sig
  type fetch_result =
    [ `Not_modified | `Fetched of string option | `Failed of string ]
  (** A fetch either reuses the current generation, writes a new generation, or
      fails. [`Fetched etag] carries the response entity tag when available. *)

  type refresh_result = [ `Not_modified | `Replaced | `Failed of string ]
  (** The result of one controlled refresh attempt. *)

  type controlled_live = {
    database : t;
    refresh_once : unit -> refresh_result Lwt.t;
  }
  (** A live reader without a polling task. [refresh_once ()] runs one
      serialized refresh through the same replacement logic as {!Database.live}.
  *)

  val live :
    fetch:(etag:string option -> destination:string -> fetch_result Lwt.t) ->
    cache_dir:string ->
    download_timeout_seconds:float ->
    (controlled_live, string) result Lwt.t
  (** [live ~fetch ~cache_dir ~download_timeout_seconds] starts a controlled
      reader. [fetch] must write a complete SQLite file to [destination] before
      returning [`Fetched _]. The timeout uses seconds. *)

  val sqlite_with_pool_observer :
    on_acquire:(unit -> unit) -> string -> (t, string) result
  (** [sqlite_with_pool_observer ~on_acquire path] opens [path] like {!sqlite}
      and invokes [on_acquire ()] once for each pool acquisition. *)
end

val close : t -> unit Lwt.t
(** [close database] releases [database]. Calling it more than once returns the
    same close promise. A live reader also stops its polling task and removes
    its managed SQLite file after any active refresh finishes. *)

val health : t -> (unit, error) result Lwt.t
(** [health database] checks that the current SQLite generation can execute a
    query. It returns [`Unavailable _] when the check fails. *)

val sitemap_data : t -> (sitemap_data, error) result Lwt.t
(** [sitemap_data database] reads every story-group and gallery identity from
    one current database generation. *)

val art : t -> string -> string -> (Model.art, error) result Lwt.t
(** [art database category id] returns one composed artwork identified by the
    pair [(category, id)]. It returns [`Not_found] when no exact pair exists. *)

val source_art : t -> string -> (Model.source_art, error) result Lwt.t
(** [source_art database id] returns one retained source layer. It returns
    [`Not_found] when [id] does not exist. *)

val unreferenced_arts : t -> (Model.unreferenced_art list, error) result Lwt.t
(** [unreferenced_arts database] lists artwork referenced by neither a story nor
    a gallery in any locale. Results preserve the defined category and ID
    ordering. *)

val art_context :
  t -> string -> string -> string -> (Model.art_context, error) result Lwt.t
(** [art_context database locale category id] returns localized names, character
    siblings, and story occurrences for one available artwork. It returns
    [`Not_found] when no exact [(category, id)] artwork exists. *)

val story_groups :
  t -> string -> (Model.story_group_summary list, error) result Lwt.t
(** [story_groups database locale] lists story groups in stored position order.
    Each summary contains up to three available previews and uses its first
    preview as the representative. *)

val stories_by_group :
  t -> string -> string -> (Model.story_summary list, error) result Lwt.t
(** [stories_by_group database locale group_id] lists summaries in stored story
    order. Each summary has an empty internal [art_references] list, up to three
    available previews, and its first preview as the representative.

    An existing group without stories returns [Ok []]. A missing group returns
    [`Not_found]. *)

val story_group :
  t -> string -> string -> (Model.story_group_detail, error) result Lwt.t
(** [story_group database locale id] returns one group with its previews and all
    available art references in stored story and reference order. It
    deduplicates references by category and artwork ID. A missing group returns
    [`Not_found]. *)

val story : t -> string -> string -> (Model.story, error) result Lwt.t
(** [story database locale id] returns one story with ordered art references.
    Unresolved references remain present without composition object keys. A
    missing story returns [`Not_found]. *)

val galleries : t -> string -> (Model.gallery_summary list, error) result Lwt.t
(** [galleries database locale] lists gallery summaries by gallery ID. Each
    summary contains up to three stable preview composition keys. *)

val gallery : t -> string -> string -> (Model.gallery, error) result Lwt.t
(** [gallery database locale id] returns one gallery with entries in stored
    position order. Unresolved entries remain present without composition object
    keys. A missing gallery returns [`Not_found]. *)
