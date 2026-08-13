(** Domain records and encoders for public web responses. *)

type image_metadata = {
  object_key : string;  (** Bucket-relative object key. *)
  byte_size : int64;  (** Object size in bytes. *)
  width : int;  (** Image width in pixels. *)
  height : int;  (** Image height in pixels. *)
}
(** Metadata for one Portable Network Graphics (PNG) object in object storage.
*)

type art = {
  id : string;  (** Logical artwork identifier within [category]. *)
  category : string;  (** Storage and routing category. *)
  image : image_metadata;  (** Composed PNG object. *)
  source_art_ids : string list;  (** Source layers in composition order. *)
}
(** One composed artwork and its source-layer identifiers. *)

type source_art = {
  id : string;  (** Logical source-layer identifier. *)
  character_id : string;  (** Upstream character identifier. *)
  role : string;  (** Layer role such as [body], [face], or [whole_body]. *)
  variant : string;  (** Upstream layer variant. *)
  image : image_metadata;  (** Source PNG object. *)
}
(** One retained source layer used to compose character artwork. *)

type unreferenced_art = {
  id : string;  (** Logical artwork identifier within [category]. *)
  category : string;  (** Storage and routing category. *)
  composition_object_key : string;  (** Composed PNG object key. *)
}
(** One composed artwork referenced by neither a story nor a gallery. *)

type story_art_reference = {
  art_id : string;  (** Logical artwork identifier within [category]. *)
  kind : string;  (** Upstream reference kind, [picture] or [character]. *)
  category : string;  (** Storage and routing category. *)
  title : string option;  (** Optional localized title. *)
  subtitle : string option;  (** Optional localized subtitle. *)
  names : string list;  (** Localized character names in source order. *)
  composition_object_key : string option;
      (** Composed PNG key, or [None] when the artwork is unavailable. *)
}
(** One story artwork reference. *)

type story = {
  id : string;  (** Logical story identifier within [group_id]. *)
  group_id : string;  (** Parent story-group identifier. *)
  tag : string;  (** Position tag: [before], [after], or [interlude]. *)
  tag_text : string;  (** Localized position label. *)
  code : string;  (** Localized display code. *)
  name : string;  (** Localized story name. *)
  info : string;  (** Localized story description. *)
  art_references : story_art_reference list;  (** References in source order. *)
}
(** One localized story with ordered artwork references. *)

type story_group = {
  id : string;  (** Logical group identifier. *)
  name : string;  (** Localized group name. *)
  group_type : string;
      (** One of [main_story], [major_event], [minor_event], [operator_record],
          [integrated_strategies], [reclamation_algorithm], or [others]. *)
}
(** One ordered story group. *)

type story_summary = {
  story : story;
      (** Story metadata with an empty internal [art_references] list. *)
  representative_art_reference : story_art_reference option;
      (** First preview, or [None] when no preview is available. *)
  preview_art_references : story_art_reference list;
      (** Up to three available card backgrounds in stable ranked order. *)
}
(** One story prepared for a group listing. *)

type story_group_summary = {
  group : story_group;  (** Group metadata. *)
  representative_art_reference : story_art_reference option;
      (** First preview, or [None] when no preview is available. *)
  preview_art_references : story_art_reference list;
      (** Up to three available card backgrounds in stable ranked order. *)
}
(** One story group prepared for an index listing. *)

type story_group_detail = {
  group : story_group;  (** Group metadata. *)
  representative_art_reference : story_art_reference option;
      (** First preview, or [None] when no preview is available. *)
  preview_art_references : story_art_reference list;
      (** Up to three available card backgrounds in stable ranked order. *)
  art_references : story_art_reference list;
      (** Available references in stored order, deduplicated by category and ID.
      *)
}
(** One story group with artwork referenced by its stories. *)

type gallery_entry = {
  id : string;  (** Logical entry identifier within its gallery. *)
  position : int;  (** Nonnegative stored position. *)
  name : string;  (** Localized entry name. *)
  description : string;  (** Localized entry description. *)
  art_id : string;  (** Referenced artwork identifier within [category]. *)
  category : string;  (** Referenced artwork category. *)
  composition_object_key : string option;
      (** Composed PNG key, or [None] when the artwork is unavailable. *)
}
(** One ordered gallery entry. *)

type gallery = {
  id : string;  (** Logical gallery identifier. *)
  name : string;  (** Localized gallery name. *)
  description : string;  (** Localized gallery description. *)
  entries : gallery_entry list;  (** Entries in stored position order. *)
}
(** One localized gallery. *)

type gallery_summary = {
  gallery : gallery;  (** Gallery metadata with an empty [entries] list. *)
  preview_composition_object_keys : string list;
      (** Up to three available composition keys in stable ranked order. *)
}
(** One gallery prepared for an index listing. *)

type art_sibling = {
  art_id : string;  (** Related artwork identifier. *)
  names : string list;  (** Deduplicated localized names in source order. *)
  composition_object_key : string;  (** Composed PNG object key. *)
}
(** One available character variant related to selected artwork. *)

type art_occurrence = {
  group_id : string;  (** Parent group identifier. *)
  group_name : string;  (** Localized parent group name. *)
  group_type : string;  (** Parent group navigation category. *)
  story_id : string;  (** Story identifier. *)
  story_name : string;  (** Localized story name. *)
  story_code : string;  (** Localized story code. *)
  story_tag_text : string;  (** Localized story-position label. *)
}
(** One localized story occurrence of selected artwork. *)

type art_context = {
  names : string list;  (** Deduplicated names in first-occurrence order. *)
  siblings : art_sibling list;  (** Related character variants by artwork ID. *)
  occurrences : art_occurrence list;  (** Distinct stories in stored order. *)
}
(** Localized context for one available artwork. *)

val content_url : object_base_url:string -> string -> string
(** [content_url ~object_base_url object_key] builds a public object URL. It
    removes one trailing slash from the base and percent-encodes each key path
    segment. *)

val art_json : object_base_url:string -> art -> Yojson.Safe.t
(** [art_json ~object_base_url art] encodes composed-art metadata, its direct
    PNG URL, its direct thumbnail URL, and source-layer IDs.

    @raise Invalid_argument
      if the composition object key cannot identify its thumbnail. *)

val source_art_json : object_base_url:string -> source_art -> Yojson.Safe.t
(** [source_art_json ~object_base_url art] encodes source-layer metadata and its
    direct PNG URL. *)

val unreferenced_art_json :
  object_base_url:string -> unreferenced_art -> Yojson.Safe.t
(** [unreferenced_art_json ~object_base_url art] encodes a compact artwork card
    with a direct thumbnail URL.

    @raise Invalid_argument
      if the composition object key cannot identify its thumbnail. *)

val story_json : object_base_url:string -> story -> Yojson.Safe.t
(** [story_json ~object_base_url story] encodes story metadata and every ordered
    artwork reference. Unavailable references have a null thumbnail URL.

    @raise Invalid_argument
      if an available composition object key cannot identify its thumbnail. *)

val story_summary_json :
  object_base_url:string -> story_summary -> Yojson.Safe.t
(** [story_summary_json ~object_base_url summary] encodes story metadata and
    previews. It includes an empty [artReferences] list for compatibility.

    @raise Invalid_argument
      if an available composition object key cannot identify its thumbnail. *)

val story_group_summary_json :
  object_base_url:string -> story_group_summary -> Yojson.Safe.t
(** [story_group_summary_json ~object_base_url summary] encodes group metadata
    and previews.

    @raise Invalid_argument
      if an available composition object key cannot identify its thumbnail. *)

val story_group_detail_json :
  object_base_url:string -> story_group_detail -> Yojson.Safe.t
(** [story_group_detail_json ~object_base_url detail] encodes group metadata,
    previews, and all available deduplicated artwork references.

    @raise Invalid_argument
      if an available composition object key cannot identify its thumbnail. *)

val gallery_json : object_base_url:string -> gallery -> Yojson.Safe.t
(** [gallery_json ~object_base_url gallery] encodes gallery metadata and every
    ordered entry. Unavailable entries have a null thumbnail URL.

    @raise Invalid_argument
      if an available composition object key cannot identify its thumbnail. *)

val gallery_summary_json :
  object_base_url:string -> gallery_summary -> Yojson.Safe.t
(** [gallery_summary_json ~object_base_url summary] encodes gallery metadata and
    direct preview thumbnail URLs.

    @raise Invalid_argument
      if a composition object key cannot identify its thumbnail. *)

val art_context_json : object_base_url:string -> art_context -> Yojson.Safe.t
(** [art_context_json ~object_base_url context] encodes localized names,
    character siblings, and story occurrences with direct sibling thumbnails.

    @raise Invalid_argument
      if a sibling composition object key cannot identify its thumbnail. *)
