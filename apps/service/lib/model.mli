(** Domain records and JSON encoders for the public read interface. *)

type image_metadata = {
  object_key : string;
  size : int64;
  width : int;
  height : int;
}

type video_metadata = {
  object_key : string;
  size : int64;
  width : int;
  height : int;
  frame_rate : float;
  frame_count : int;
}

type asset_reference = {
  namespace : string;
  id : string;
  category : string;
}

type narrative_image_asset = {
  id : string;
  category : string;
  image : image_metadata;
  material_assets : asset_reference list;
}

type material_asset = {
  id : string;
  category : string;
  kind : string;
  character_id : string option;
  role : string option;
  variant : string option;
  image : image_metadata;
  narrative_image_asset_references : asset_reference list;
}

type orphan_narrative_image_asset = {
  id : string;
  category : string;
  asset_object_key : string;
  size : int64;
  width : int;
  height : int;
}

type orphan_narrative_media_asset = {
  id : string;
  kind : string;
  object_key : string;
  mime : string;
  size : int64;
}

type story_narrative_image_reference = {
  asset_id : string;
  kind : string;
  category : string;
  is_anime_kv : bool;
  title : string option;
  subtitle : string option;
  names : string list;
  asset_object_key : string option;
}

type story_narrative_media_reference = {
  asset_id : string;
  kind : string;
  mime : string option;
  size : int64 option;
  object_key : string option;
}

type narrative_media_asset = {
  id : string;
  kind : string;
  object_key : string;
  mime : string;
  size : int64;
  duration : float option;
  sample_rate : int option;
  width : int option;
  height : int option;
  frame_rate : float option;
  frame_count : int option;
}

type collection_parent =
  | Score_parent of {
      movement_id : string;
      movement_name : string;
      section_id : string;
      section_name : string;
    }
  | Archive_parent of {
      archive_category : string;
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
  text : string;
  media_references : story_narrative_media_reference list;
  narrative_image_asset_references : story_narrative_image_reference list;
}

type story_summary = {
  story : story;
  representative_narrative_image_asset_reference : story_narrative_image_reference option;
  preview_narrative_image_asset_references : story_narrative_image_reference list;
}

type story_detail = { story : story; parent : collection_parent }

type score_image_reference = {
  id : string;
  category : string;
  image : image_metadata option;
}

type score_video_reference = {
  id : string;
  category : string;
  video : video_metadata option;
}

type gallery_reference = {
  position : int;
  cg_id : string;
  asset_id : string;
  category : string;
  asset_object_key : string option;
}

type gallery_group = {
  id : string;
  position : int;
  name : string;
  description : string;
  related_story_id : string option;
  related_stage_id : string option;
  references : gallery_reference list;
}

type gallery = {
  id : string;
  name : string;
  description : string;
  parent : collection_parent;
  groups : gallery_group list;
}

type gallery_summary = {
  gallery : gallery;
  preview_asset_object_keys : string list;
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

type section = {
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
  opening_media_references : story_narrative_media_reference list;
}

type movement_divider = {
  id : string;
  position : int;
  sub_name : string;
  icon : score_image_reference option;
  video : score_video_reference option;
}

type movement_item =
  | Divider of movement_divider
  | Section of { position : int; section : section }

type movement_detail = { movement : movement; items : movement_item list }

type section_detail = {
  section : section;
  active_background_video : score_video_reference option;
  stories : story_summary list;
  media_references : story_narrative_media_reference list;
  narrative_image_asset_references : story_narrative_image_reference list;
  gallery : gallery option;
}

type archive_index_entry = { category : string; group_count : int }

type archive_group = {
  id : string;
  name : string;
  category : string;
  group_type : string;
}

type archive_group_summary = {
  group : archive_group;
  representative_narrative_image_asset_reference : story_narrative_image_reference option;
  preview_narrative_image_asset_references : story_narrative_image_reference list;
}

type archive_group_detail = {
  group : archive_group;
  stories : story_summary list;
  representative_narrative_image_asset_reference : story_narrative_image_reference option;
  preview_narrative_image_asset_references : story_narrative_image_reference list;
  media_references : story_narrative_media_reference list;
  narrative_image_asset_references : story_narrative_image_reference list;
  opening_media_references : story_narrative_media_reference list;
  gallery : gallery option;
}

type related_narrative_image_asset = {
  asset_id : string;
  names : string list;
  asset_object_key : string;
}

type narrative_image_occurrence = {
  parent : collection_parent;
  story_id : string;
  story_name : string;
  story_code : string;
  story_tag_text : string;
}

type narrative_asset_gallery_reference = {
  gallery_id : string;
  gallery_name : string;
  gallery_description : string;
  group_id : string;
  group_name : string;
  group_description : string;
  cg_id : string;
}

type narrative_media_asset_reverse_references = {
  occurrences : narrative_image_occurrence list;
  collections : collection_parent list;
}

type narrative_image_asset_reverse_references = {
  names : string list;
  character_variants : related_narrative_image_asset list;
  textures : related_narrative_image_asset list;
  occurrences : narrative_image_occurrence list;
  galleries : narrative_asset_gallery_reference list;
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

type presentation_asset = {
  id : string;
  category : string;
  format : string;
  mime : string;
  size : int64;
  object_key : string;
  width : int option;
  height : int option;
  duration : float option;
  frame_rate : float option;
  frame_count : int option;
  reference_count : int;
}

type presentation_reverse_reference = {
  owner_type : string;
  owner_id : string;
  movement_id : string;
  role : string;
  name : string;
}

type presentation_asset_detail = {
  asset : presentation_asset;
  reverse_references : presentation_reverse_reference list;
}

val content_url : object_base_url:string -> string -> string
val narrative_image_asset_json : object_base_url:string -> narrative_image_asset -> Yojson.Safe.t
val material_asset_json : object_base_url:string -> material_asset -> Yojson.Safe.t
val orphan_narrative_image_asset_json :
  object_base_url:string -> orphan_narrative_image_asset -> Yojson.Safe.t
val orphan_narrative_media_asset_json :
  object_base_url:string -> orphan_narrative_media_asset -> Yojson.Safe.t
val story_summary_json :
  object_base_url:string -> story_summary -> Yojson.Safe.t
val story_detail_json : object_base_url:string -> story_detail -> Yojson.Safe.t
val narrative_media_asset_json : object_base_url:string -> narrative_media_asset -> Yojson.Safe.t
val narrative_media_asset_reverse_references_json : narrative_media_asset_reverse_references -> Yojson.Safe.t
val movement_json : object_base_url:string -> movement -> Yojson.Safe.t
val movement_detail_json :
  object_base_url:string -> movement_detail -> Yojson.Safe.t
val section_detail_json :
  object_base_url:string -> section_detail -> Yojson.Safe.t
val archive_index_entry_json : archive_index_entry -> Yojson.Safe.t
val archive_group_summary_json :
  object_base_url:string -> archive_group_summary -> Yojson.Safe.t
val archive_group_detail_json :
  object_base_url:string -> archive_group_detail -> Yojson.Safe.t
val gallery_summary_json :
  object_base_url:string -> gallery_summary -> Yojson.Safe.t
val gallery_json : object_base_url:string -> gallery -> Yojson.Safe.t
val narrative_image_asset_reverse_references_json : object_base_url:string -> narrative_image_asset_reverse_references -> Yojson.Safe.t
val search_result_json : object_base_url:string -> search_result -> Yojson.Safe.t
val presentation_asset_summary_json :
  object_base_url:string -> presentation_asset -> Yojson.Safe.t
val presentation_asset_detail_json :
  object_base_url:string -> presentation_asset_detail -> Yojson.Safe.t
