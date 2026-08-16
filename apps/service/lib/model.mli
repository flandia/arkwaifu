(** Domain records and JSON encoders for the public read interface. *)

type image_metadata = {
  object_key : string;
  byte_size : int64;
  width : int;
  height : int;
}

type video_metadata = {
  object_key : string;
  byte_size : int64;
  width : int;
  height : int;
  frame_rate : float;
  frame_count : int;
}

type art_source_reference = { id : string; category : string }

type art = {
  id : string;
  category : string;
  image : image_metadata;
  source_arts : art_source_reference list;
}

type source_art = {
  id : string;
  category : string;
  kind : string;
  character_id : string option;
  role : string option;
  variant : string option;
  image : image_metadata;
}

type unreferenced_art = {
  id : string;
  category : string;
  composition_object_key : string;
}

type story_art_reference = {
  art_id : string;
  kind : string;
  category : string;
  title : string option;
  subtitle : string option;
  names : string list;
  composition_object_key : string option;
}

type collection_parent =
  | Score_parent of {
      movement_id : string;
      movement_name : string;
      section_id : string;
      section_name : string;
    }
  | Archive_parent of {
      archive_kind : string;
      group_id : string;
      group_name : string;
    }

type story = {
  id : string;
  tag : string;
  tag_text : string;
  code : string;
  name : string;
  info : string;
  art_references : story_art_reference list;
}

type story_summary = {
  story : story;
  representative_art_reference : story_art_reference option;
  preview_art_references : story_art_reference list;
}

type story_detail = { story : story; parent : collection_parent }

type score_image_reference = {
  id : string;
  image : image_metadata option;
}

type score_video_reference = {
  id : string;
  video : video_metadata option;
}

type gallery_artwork = {
  position : int;
  cg_id : string;
  art_id : string;
  category : string;
  composition_object_key : string option;
}

type gallery_display = {
  id : string;
  position : int;
  name : string;
  description : string;
  related_story_id : string option;
  related_stage_id : string option;
  artworks : gallery_artwork list;
}

type gallery = {
  id : string;
  name : string;
  description : string;
  parent : collection_parent;
  displays : gallery_display list;
}

type gallery_summary = {
  gallery : gallery;
  preview_composition_object_keys : string list;
}

type movement = {
  id : string;
  name : string;
  movement_type : string;
  position : int;
  section_count : int;
  start_time : int64;
  icon : score_image_reference option;
  logo : score_image_reference option;
  background : score_image_reference option;
  background_video : score_video_reference option;
}

type movement_section = {
  id : string;
  name : string;
  description : string;
  section_type : string;
  position : int;
  sort_by_year : int;
  sort_within_year : int;
  key_visual : score_image_reference option;
  title_image : score_image_reference option;
  background : score_image_reference option;
  decoration : score_image_reference option;
  retro_background : score_image_reference option;
  story_count : int;
}

type movement_split = {
  id : string;
  position : int;
  sub_name : string;
  icon : score_image_reference option;
  video : score_video_reference option;
}

type movement_item =
  | Movement_split of movement_split
  | Movement_section of { position : int; section : movement_section }

type movement_detail = { movement : movement; items : movement_item list }

type movement_section_detail = {
  section : movement_section;
  active_background_video : score_video_reference option;
  stories : story_summary list;
  art_references : story_art_reference list;
  gallery : gallery option;
}

type archive_index_entry = { kind : string; group_count : int }

type archive_group = {
  id : string;
  name : string;
  kind : string;
  group_type : string;
}

type archive_group_summary = {
  group : archive_group;
  representative_art_reference : story_art_reference option;
  preview_art_references : story_art_reference list;
}

type archive_group_detail = {
  group : archive_group;
  stories : story_summary list;
  representative_art_reference : story_art_reference option;
  preview_art_references : story_art_reference list;
  art_references : story_art_reference list;
  gallery : gallery option;
}

type art_sibling = {
  art_id : string;
  names : string list;
  composition_object_key : string;
}

type art_occurrence = {
  parent : collection_parent;
  story_id : string;
  story_name : string;
  story_code : string;
  story_tag_text : string;
}

type art_context = {
  names : string list;
  siblings : art_sibling list;
  occurrences : art_occurrence list;
}

type search_result = {
  kind : string;
  id : string;
  category : string option;
  title : string;
  subtitle : string option;
  thumbnail_object_key : string option;
  parent : collection_parent option;
}

val content_url : object_base_url:string -> string -> string
val art_json : object_base_url:string -> art -> Yojson.Safe.t
val source_art_json : object_base_url:string -> source_art -> Yojson.Safe.t
val unreferenced_art_json :
  object_base_url:string -> unreferenced_art -> Yojson.Safe.t
val story_summary_json :
  object_base_url:string -> story_summary -> Yojson.Safe.t
val story_detail_json : object_base_url:string -> story_detail -> Yojson.Safe.t
val movement_json : object_base_url:string -> movement -> Yojson.Safe.t
val movement_detail_json :
  object_base_url:string -> movement_detail -> Yojson.Safe.t
val movement_section_detail_json :
  object_base_url:string -> movement_section_detail -> Yojson.Safe.t
val archive_index_entry_json : archive_index_entry -> Yojson.Safe.t
val archive_group_summary_json :
  object_base_url:string -> archive_group_summary -> Yojson.Safe.t
val archive_group_detail_json :
  object_base_url:string -> archive_group_detail -> Yojson.Safe.t
val gallery_summary_json :
  object_base_url:string -> gallery_summary -> Yojson.Safe.t
val gallery_json : object_base_url:string -> gallery -> Yojson.Safe.t
val art_context_json : object_base_url:string -> art_context -> Yojson.Safe.t
val search_result_json : object_base_url:string -> search_result -> Yojson.Safe.t
