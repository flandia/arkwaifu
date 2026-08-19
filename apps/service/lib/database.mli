(** Read-only access to one current Arkwaifu SQLite generation. *)

type error = [ `Not_found | `Unavailable of string ]
type t

type sitemap_data = {
  movements : (string * string) list;
      (** [(locale, movement_id)] rows. *)
  sections : (string * string * string) list;
      (** [(locale, movement_id, section_id)] canonical Score placements. *)
  archive_groups : (string * string * string) list;
      (** [(locale, archive_category, group_id)] rows using database kind names. *)
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

val narrative_image_asset : t -> string -> string -> (Model.narrative_image_asset, error) result Lwt.t

val material_asset :
  t -> string -> string -> (Model.material_asset, error) result Lwt.t

val narrative_media_asset :
  t -> string -> string -> (Model.narrative_media_asset, error) result Lwt.t

val orphan_narrative_image_assets :
  t -> string -> (Model.orphan_narrative_image_asset list, error) result Lwt.t
val orphan_narrative_media_assets :
  t -> string -> (Model.orphan_narrative_media_asset list, error) result Lwt.t

val narrative_image_asset_reverse_references :
  t -> string -> string -> string -> (Model.narrative_image_asset_reverse_references, error) result Lwt.t

val narrative_media_asset_reverse_references :
  t -> string -> string -> string -> (Model.narrative_media_asset_reverse_references, error) result Lwt.t

val movements : t -> string -> (Model.movement list, error) result Lwt.t

val movement :
  t -> string -> string -> (Model.movement_detail, error) result Lwt.t

val section :
  t ->
  string ->
  string ->
  string ->
  (Model.section_detail, error) result Lwt.t

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
val presentation_assets :
  t -> string -> (Model.presentation_asset list, error) result Lwt.t
val presentation_asset :
  t ->
  string ->
  string ->
  string ->
  (Model.presentation_asset_detail, error) result Lwt.t
val search : t -> string -> string -> (Model.search_result list, error) result Lwt.t
