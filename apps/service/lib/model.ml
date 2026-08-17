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
  is_anime_kv : bool;
  title : string option;
  subtitle : string option;
  names : string list;
  composition_object_key : string option;
}

type story_media_reference = {
  media_id : string;
  kind : string;
  content_type : string option;
  byte_size : int64 option;
  object_key : string option;
}

type media_asset = {
  id : string;
  kind : string;
  object_key : string;
  content_type : string;
  byte_size : int64;
  duration : float option;
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
  text : string;
  media_references : story_media_reference list;
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
  opening_media_references : story_media_reference list;
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
  opening_media_references : story_media_reference list;
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
  textures : art_sibling list;
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

let trim_trailing_slash value =
  if String.length value > 0 && value.[String.length value - 1] = '/' then
    String.sub value 0 (String.length value - 1)
  else value

let content_url ~object_base_url object_key =
  let encoded_key =
    object_key |> String.split_on_char '/'
    |> List.map (Uri.pct_encode ~component:`Path)
    |> String.concat "/"
  in
  trim_trailing_slash object_base_url ^ "/" ^ encoded_key

let thumbnail_object_key object_key =
  match String.split_on_char '/' object_key with
  | [ "ART"; version; "composition"; category; filename ]
    when String.ends_with ~suffix:".png" filename ->
      let name = String.sub filename 0 (String.length filename - 4) in
      String.concat "/"
        [ "ART"; version; "thumbnail"; category; name ^ ".webp" ]
  | _ -> invalid_arg ("not an art composition object key: " ^ object_key)

let thumbnail_content_url ~object_base_url object_key =
  content_url ~object_base_url (thumbnail_object_key object_key)

let option_string = function None -> `Null | Some value -> `String value
let string_list values = `List (List.map (fun value -> `String value) values)

let image_metadata_json ~object_base_url (image : image_metadata) =
  `Assoc
    [
      ("byteSize", `Intlit (Int64.to_string image.byte_size));
      ("width", `Int image.width);
      ("height", `Int image.height);
      ("contentUrl", `String (content_url ~object_base_url image.object_key));
    ]

let video_metadata_json ~object_base_url (video : video_metadata) =
  `Assoc
    [
      ("byteSize", `Intlit (Int64.to_string video.byte_size));
      ("width", `Int video.width);
      ("height", `Int video.height);
      ("frameRate", `Float video.frame_rate);
      ("frameCount", `Int video.frame_count);
      ("contentUrl", `String (content_url ~object_base_url video.object_key));
    ]

let art_source_reference_json (source : art_source_reference) =
  `Assoc [ ("id", `String source.id); ("category", `String source.category) ]

let art_json ~object_base_url (art : art) =
  `Assoc
    [
      ("id", `String art.id);
      ("category", `String art.category);
      ( "thumbnailContentUrl",
        `String (thumbnail_content_url ~object_base_url art.image.object_key) );
      ("image", image_metadata_json ~object_base_url art.image);
      ("sourceArts", `List (List.map art_source_reference_json art.source_arts));
    ]

let source_art_json ~object_base_url (source : source_art) =
  `Assoc
    [
      ("id", `String source.id);
      ("category", `String source.category);
      ("kind", `String source.kind);
      ("characterID", option_string source.character_id);
      ("role", option_string source.role);
      ("variant", option_string source.variant);
      ("image", image_metadata_json ~object_base_url source.image);
    ]

let unreferenced_art_json ~object_base_url (art : unreferenced_art) =
  `Assoc
    [
      ("id", `String art.id);
      ("category", `String art.category);
      ( "thumbnailContentUrl",
        `String
          (thumbnail_content_url ~object_base_url art.composition_object_key) );
    ]

let option_thumbnail_content_url ~object_base_url = function
  | None -> `Null
  | Some object_key ->
      `String (thumbnail_content_url ~object_base_url object_key)

let story_art_reference_json ~object_base_url (reference : story_art_reference)
    =
  `Assoc
    [
      ("artID", `String reference.art_id);
      ("kind", `String reference.kind);
      ("category", `String reference.category);
      ("isAnimeKV", `Bool reference.is_anime_kv);
      ("title", option_string reference.title);
      ("subtitle", option_string reference.subtitle);
      ("names", string_list reference.names);
      ( "thumbnailContentUrl",
        option_thumbnail_content_url ~object_base_url
          reference.composition_object_key );
    ]

let option_story_art_reference ~object_base_url = function
  | None -> `Null
  | Some reference -> story_art_reference_json ~object_base_url reference

let story_art_reference_list ~object_base_url references =
  `List (List.map (story_art_reference_json ~object_base_url) references)

let story_media_reference_json ~object_base_url
    (reference : story_media_reference) =
  `Assoc
    [
      ("id", `String reference.media_id);
      ("kind", `String reference.kind);
      ("contentType", option_string reference.content_type);
      ( "byteSize",
        match reference.byte_size with
        | None -> `Null
        | Some byte_size -> `Intlit (Int64.to_string byte_size) );
      ( "contentUrl",
        match reference.object_key with
        | None -> `Null
        | Some object_key ->
            `String (content_url ~object_base_url object_key) );
    ]

let story_media_reference_list ~object_base_url references =
  `List
    (List.map
       (story_media_reference_json ~object_base_url)
       references)

let media_asset_json ~object_base_url (asset : media_asset) =
  let option_float = function None -> `Null | Some value -> `Float value in
  let option_int = function None -> `Null | Some value -> `Int value in
  `Assoc
    [
      ("id", `String asset.id);
      ("kind", `String asset.kind);
      ("contentType", `String asset.content_type);
      ("byteSize", `Intlit (Int64.to_string asset.byte_size));
      ("duration", option_float asset.duration);
      ("width", option_int asset.width);
      ("height", option_int asset.height);
      ("frameRate", option_float asset.frame_rate);
      ("frameCount", option_int asset.frame_count);
      ("contentUrl", `String (content_url ~object_base_url asset.object_key));
    ]

let collection_parent_json = function
  | Score_parent { movement_id; movement_name; section_id; section_name } ->
      `Assoc
        [
          ("kind", `String "score");
          ("movementID", `String movement_id);
          ("movementName", `String movement_name);
          ("sectionID", `String section_id);
          ("sectionName", `String section_name);
        ]
  | Archive_parent { archive_kind; group_id; group_name } ->
      `Assoc
        [
          ("kind", `String "archive");
          ("archiveKind", `String archive_kind);
          ("groupID", `String group_id);
          ("groupName", `String group_name);
        ]

let story_fields (story : story) =
  [
    ("id", `String story.id);
    ("tag", `String story.tag);
    ("tagText", `String story.tag_text);
    ("code", `String story.code);
    ("name", `String story.name);
    ("info", `String story.info);
  ]

let story_summary_json ~object_base_url (summary : story_summary) =
  `Assoc
    (story_fields summary.story
    @ [
        ( "representativeArtReference",
          option_story_art_reference ~object_base_url
            summary.representative_art_reference );
        ( "previewArtReferences",
          story_art_reference_list ~object_base_url
            summary.preview_art_references );
      ])

let story_detail_json ~object_base_url (detail : story_detail) =
  `Assoc
    (story_fields detail.story
    @ [
        ("parent", collection_parent_json detail.parent);
        ("text", `String detail.story.text);
        ( "media",
          story_media_reference_list ~object_base_url
            detail.story.media_references );
        ( "artReferences",
          story_art_reference_list ~object_base_url
            detail.story.art_references );
      ])

let score_image_reference_json ~object_base_url (reference : score_image_reference)
    =
  `Assoc
    [
      ("id", `String reference.id);
      ( "image",
        match reference.image with
        | None -> `Null
        | Some image -> image_metadata_json ~object_base_url image );
    ]

let option_score_image_reference ~object_base_url = function
  | None -> `Null
  | Some reference -> score_image_reference_json ~object_base_url reference

let score_video_reference_json ~object_base_url (reference : score_video_reference)
    =
  `Assoc
    [
      ("id", `String reference.id);
      ( "video",
        match reference.video with
        | None -> `Null
        | Some video -> video_metadata_json ~object_base_url video );
    ]

let option_score_video_reference ~object_base_url = function
  | None -> `Null
  | Some reference -> score_video_reference_json ~object_base_url reference

let gallery_artwork_json ~object_base_url (artwork : gallery_artwork) =
  `Assoc
    [
      ("position", `Int artwork.position);
      ("cgID", `String artwork.cg_id);
      ("artID", `String artwork.art_id);
      ("category", `String artwork.category);
      ( "thumbnailContentUrl",
        option_thumbnail_content_url ~object_base_url
          artwork.composition_object_key );
    ]

let gallery_display_json ~object_base_url (display : gallery_display) =
  `Assoc
    [
      ("id", `String display.id);
      ("position", `Int display.position);
      ("name", `String display.name);
      ("description", `String display.description);
      ("relatedStoryID", option_string display.related_story_id);
      ("relatedStageID", option_string display.related_stage_id);
      ( "artworks",
        `List (List.map (gallery_artwork_json ~object_base_url) display.artworks)
      );
    ]

let gallery_fields (gallery : gallery) =
  [
    ("id", `String gallery.id);
    ("name", `String gallery.name);
    ("description", `String gallery.description);
    ("parent", collection_parent_json gallery.parent);
  ]

let gallery_json ~object_base_url (gallery : gallery) =
  `Assoc
    (gallery_fields gallery
    @ [
        ( "displays",
          `List
            (List.map (gallery_display_json ~object_base_url) gallery.displays) );
      ])

let option_gallery ~object_base_url = function
  | None -> `Null
  | Some gallery -> gallery_json ~object_base_url gallery

let gallery_summary_json ~object_base_url (summary : gallery_summary) =
  `Assoc
    (gallery_fields summary.gallery
    @ [
        ( "previewThumbnailContentUrls",
          `List
            (List.map
               (fun object_key ->
                 `String (thumbnail_content_url ~object_base_url object_key))
               summary.preview_composition_object_keys) );
      ])

let movement_fields ~object_base_url (movement : movement) =
  [
    ("id", `String movement.id);
    ("name", `String movement.name);
    ("type", `String movement.movement_type);
    ("position", `Int movement.position);
    ("sectionCount", `Int movement.section_count);
    ("startTime", `Intlit (Int64.to_string movement.start_time));
    ("icon", option_score_image_reference ~object_base_url movement.icon);
    ("logo", option_score_image_reference ~object_base_url movement.logo);
    ( "background",
      option_score_image_reference ~object_base_url movement.background );
    ( "backgroundVideo",
      option_score_video_reference ~object_base_url movement.background_video );
  ]

let movement_json ~object_base_url movement =
  `Assoc (movement_fields ~object_base_url movement)

let movement_section_fields ~object_base_url (section : movement_section) =
  [
    ("id", `String section.id);
    ("name", `String section.name);
    ("description", `String section.description);
    ("type", `String section.section_type);
    ("position", `Int section.position);
    ("sortByYear", `Int section.sort_by_year);
    ("sortWithinYear", `Int section.sort_within_year);
    ("storyCount", `Int section.story_count);
    ( "keyVisual",
      option_score_image_reference ~object_base_url section.key_visual );
    ( "titleImage",
      option_score_image_reference ~object_base_url section.title_image );
    ( "background",
      option_score_image_reference ~object_base_url section.background );
    ( "decoration",
      option_score_image_reference ~object_base_url section.decoration );
    ( "retroBackground",
      option_score_image_reference ~object_base_url section.retro_background );
    ( "openingMedia",
      story_media_reference_list ~object_base_url
        section.opening_media_references );
  ]

let movement_section_json ~object_base_url section =
  `Assoc (movement_section_fields ~object_base_url section)

let movement_item_json ~object_base_url = function
  | Movement_split split ->
      `Assoc
        [
          ("kind", `String "split");
          ("id", `String split.id);
          ("position", `Int split.position);
          ("subName", `String split.sub_name);
          ("icon", option_score_image_reference ~object_base_url split.icon);
          ("video", option_score_video_reference ~object_base_url split.video);
        ]
  | Movement_section { position; section } ->
      `Assoc
        [
          ("kind", `String "section");
          ("position", `Int position);
          ("section", movement_section_json ~object_base_url section);
        ]

let movement_detail_json ~object_base_url (detail : movement_detail) =
  `Assoc
    (movement_fields ~object_base_url detail.movement
    @ [
        ( "items",
          `List (List.map (movement_item_json ~object_base_url) detail.items) );
      ])

let movement_section_detail_json ~object_base_url
    (detail : movement_section_detail) =
  `Assoc
    (movement_section_fields ~object_base_url detail.section
    @ [
        ( "activeBackgroundVideo",
          option_score_video_reference ~object_base_url
            detail.active_background_video );
        ( "stories",
          `List
            (List.map (story_summary_json ~object_base_url) detail.stories) );
        ( "artReferences",
          story_art_reference_list ~object_base_url detail.art_references );
        ("gallery", option_gallery ~object_base_url detail.gallery);
      ])

let archive_index_entry_json (entry : archive_index_entry) =
  `Assoc
    [ ("kind", `String entry.kind); ("groupCount", `Int entry.group_count) ]

let archive_group_fields (group : archive_group) =
  [
    ("id", `String group.id);
    ("name", `String group.name);
    ("kind", `String group.kind);
    ("type", `String group.group_type);
  ]

let archive_group_summary_json ~object_base_url (summary : archive_group_summary)
    =
  `Assoc
    (archive_group_fields summary.group
    @ [
        ( "representativeArtReference",
          option_story_art_reference ~object_base_url
            summary.representative_art_reference );
        ( "previewArtReferences",
          story_art_reference_list ~object_base_url
            summary.preview_art_references );
      ])

let archive_group_detail_json ~object_base_url (detail : archive_group_detail) =
  `Assoc
    (archive_group_fields detail.group
    @ [
        ( "representativeArtReference",
          option_story_art_reference ~object_base_url
            detail.representative_art_reference );
        ( "previewArtReferences",
          story_art_reference_list ~object_base_url
            detail.preview_art_references );
        ( "stories",
          `List
            (List.map (story_summary_json ~object_base_url) detail.stories) );
        ( "artReferences",
          story_art_reference_list ~object_base_url detail.art_references );
        ( "openingMedia",
          story_media_reference_list ~object_base_url
            detail.opening_media_references );
        ("gallery", option_gallery ~object_base_url detail.gallery);
      ])

let art_sibling_json ~object_base_url (sibling : art_sibling) =
  `Assoc
    [
      ("artID", `String sibling.art_id);
      ("names", string_list sibling.names);
      ( "thumbnailContentUrl",
        `String
          (thumbnail_content_url ~object_base_url sibling.composition_object_key)
      );
    ]

let art_occurrence_json (occurrence : art_occurrence) =
  `Assoc
    [
      ("parent", collection_parent_json occurrence.parent);
      ("storyID", `String occurrence.story_id);
      ("storyName", `String occurrence.story_name);
      ("storyCode", `String occurrence.story_code);
      ("storyTagText", `String occurrence.story_tag_text);
    ]

let art_context_json ~object_base_url (context : art_context) =
  `Assoc
    [
      ("names", string_list context.names);
      ( "siblings",
        `List (List.map (art_sibling_json ~object_base_url) context.siblings) );
      ( "textures",
        `List (List.map (art_sibling_json ~object_base_url) context.textures) );
      ("occurrences", `List (List.map art_occurrence_json context.occurrences));
    ]

let search_result_json ~object_base_url (result : search_result) =
  `Assoc
    [
      ("kind", `String result.kind);
      ("id", `String result.id);
      ("category", option_string result.category);
      ("title", `String result.title);
      ("subtitle", option_string result.subtitle);
      ( "thumbnailContentUrl",
        match result.thumbnail_object_key with
        | None -> `Null
        | Some object_key ->
            `String (thumbnail_content_url ~object_base_url object_key) );
      ( "parent",
        match result.parent with
        | None -> `Null
        | Some parent -> collection_parent_json parent );
    ]
