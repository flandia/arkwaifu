(** JSON-facing records served by the Arkwaifu HTTP module. *)

(** Metadata of one PNG object stored outside the SQLite database. *)
type object_metadata = {
  object_key : string;
  byte_size : int64;
  width : int;
  height : int;
}

(** One final art and its composition object. *)
type art = {
  id : string;
  category : string;
  image : object_metadata;
  source_art_ids : string list;
}

(** One retained character layer and its source object. *)
type source_art = {
  id : string;
  character_id : string;
  role : string;
  variant : string;
  image : object_metadata;
}

(** One picture or character referenced by a story. The composition key is
    present only when the logical reference resolves against [arts]. *)
type art_reference = {
  art_id : string;
  kind : string;
  category : string;
  title : string option;
  subtitle : string option;
  names : string list;
  composition_object_key : string option;
}

(** One localized story and its ordered art references. *)
type story = {
  id : string;
  group_id : string;
  tag : string;
  tag_text : string;
  code : string;
  name : string;
  info : string;
  art_references : art_reference list;
}

(** A summary of one ordered story group. *)
type story_group = {
  id : string;
  name : string;
  group_type : string;
}

(** A story list row with up to three stable, usable card backgrounds. The
    representative is the first preview for backward compatibility. *)
type story_summary = {
  story : story;
  representative_art_reference : art_reference option;
  preview_art_references : art_reference list;
}

(** A story-group list row with up to three stable, usable card backgrounds. The
    representative is the first preview for backward compatibility. *)
type story_group_summary = {
  group : story_group;
  representative_art_reference : art_reference option;
  preview_art_references : art_reference list;
}

(** One group, its previews, and every available art reference in it. *)
type story_group_detail = {
  group : story_group;
  representative_art_reference : art_reference option;
  preview_art_references : art_reference list;
  art_references : art_reference list;
}

(** One ordered category-qualified art entry in a gallery. The composition key
    is absent when the logical reference does not resolve against [arts]. *)
type gallery_entry = {
  id : string;
  position : int;
  name : string;
  description : string;
  art_id : string;
  category : string;
  composition_object_key : string option;
}

(** One localized gallery. Summaries contain an empty [entries] list. *)
type gallery = {
  id : string;
  name : string;
  description : string;
  entries : gallery_entry list;
}

(** Build the public URL of an object key, escaping every path segment. *)
val content_url : object_base_url:string -> string -> string

(** Encode one final art record. *)
val art_json : object_base_url:string -> art -> Yojson.Safe.t

(** Encode one original source art record. *)
val source_art_json : object_base_url:string -> source_art -> Yojson.Safe.t

(** Encode one story with all art references. *)
val story_json : object_base_url:string -> story -> Yojson.Safe.t

(** Encode one story list row. [artReferences] remains empty for compatibility. *)
val story_summary_json :
  object_base_url:string -> story_summary -> Yojson.Safe.t

(** Encode one story-group list row. *)
val story_group_summary_json :
  object_base_url:string -> story_group_summary -> Yojson.Safe.t

(** Encode one story group with all available, deduplicated art references. *)
val story_group_detail_json :
  object_base_url:string -> story_group_detail -> Yojson.Safe.t

(** Encode one gallery with its entries. *)
val gallery_json : object_base_url:string -> gallery -> Yojson.Safe.t

(** Encode one gallery without entries. *)
val gallery_summary_json : gallery -> Yojson.Safe.t
