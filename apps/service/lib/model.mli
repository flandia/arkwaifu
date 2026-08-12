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

(** One picture or character referenced by a story. *)
type art_reference = {
  art_id : string;
  kind : string;
  category : string;
  title : string option;
  subtitle : string option;
  names : string list;
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

(** One ordered category-qualified art entry in a gallery. *)
type gallery_entry = {
  id : string;
  position : int;
  name : string;
  description : string;
  art_id : string;
  category : string;
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
val story_json : story -> Yojson.Safe.t

(** Encode one story group summary. *)
val story_group_json : story_group -> Yojson.Safe.t

(** Encode one gallery with its entries. *)
val gallery_json : gallery -> Yojson.Safe.t

(** Encode one gallery without entries. *)
val gallery_summary_json : gallery -> Yojson.Safe.t
