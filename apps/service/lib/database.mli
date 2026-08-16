(** Read-only access to one current Arkwaifu SQLite generation. *)

type error = [ `Not_found | `Unavailable of string ]
type t

type sitemap_data = {
  movements : (string * string) list;
      (** [(locale, movement_id)] rows. *)
  movement_sections : (string * string * string) list;
      (** [(locale, movement_id, section_id)] canonical Score placements. *)
  archive_groups : (string * string * string) list;
      (** [(locale, archive_kind, group_id)] rows using database kind names. *)
  galleries : (string * string) list;  (** [(locale, gallery_id)] rows. *)
}

val sqlite : string -> (t, string) result

val live :
  url:Uri.t ->
  cache_dir:string ->
  poll_seconds:float ->
  download_timeout_seconds:float ->
  (t, string) result Lwt.t

module For_test : sig
  type fetch_result =
    [ `Not_modified | `Fetched of string option | `Failed of string ]

  type refresh_result = [ `Not_modified | `Replaced | `Failed of string ]

  type controlled_live = {
    database : t;
    refresh_once : unit -> refresh_result Lwt.t;
  }

  val live :
    fetch:(etag:string option -> destination:string -> fetch_result Lwt.t) ->
    cache_dir:string ->
    download_timeout_seconds:float ->
    (controlled_live, string) result Lwt.t

  val sqlite_with_pool_observer :
    on_acquire:(unit -> unit) -> string -> (t, string) result
end

val close : t -> unit Lwt.t
val health : t -> (unit, error) result Lwt.t
val sitemap_data : t -> (sitemap_data, error) result Lwt.t

val art : t -> string -> string -> (Model.art, error) result Lwt.t

val source_art :
  t -> string -> string -> (Model.source_art, error) result Lwt.t

val unreferenced_arts : t -> (Model.unreferenced_art list, error) result Lwt.t

val art_context :
  t -> string -> string -> string -> (Model.art_context, error) result Lwt.t

val movements : t -> string -> (Model.movement list, error) result Lwt.t

val movement :
  t -> string -> string -> (Model.movement_detail, error) result Lwt.t

val movement_section :
  t ->
  string ->
  string ->
  string ->
  (Model.movement_section_detail, error) result Lwt.t

val score_story :
  t ->
  string ->
  string ->
  string ->
  string ->
  (Model.story_detail, error) result Lwt.t

val archive_index :
  t -> string -> (Model.archive_index_entry list, error) result Lwt.t

val archive_groups :
  t ->
  string ->
  string ->
  (Model.archive_group_summary list, error) result Lwt.t

val archive_group :
  t ->
  string ->
  string ->
  string ->
  (Model.archive_group_detail, error) result Lwt.t

val archive_story :
  t ->
  string ->
  string ->
  string ->
  string ->
  (Model.story_detail, error) result Lwt.t

val galleries : t -> string -> (Model.gallery_summary list, error) result Lwt.t
val gallery : t -> string -> string -> (Model.gallery, error) result Lwt.t
val search : t -> string -> string -> (Model.search_result list, error) result Lwt.t
