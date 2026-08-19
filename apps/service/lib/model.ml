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
  | _ -> invalid_arg ("not a narrative image asset object key: " ^ object_key)

let thumbnail_content_url ~object_base_url object_key =
  content_url ~object_base_url (thumbnail_object_key object_key)

let option_string = function None -> `Null | Some value -> `String value
let string_list values = `List (List.map (fun value -> `String value) values)

let image_metadata_json ~object_base_url (image : image_metadata) =
  `Assoc
    [
      ("mime", `String "image/png");
      ("size", `Intlit (Int64.to_string image.size));
      ("width", `Int image.width);
      ("height", `Int image.height);
      ("url", `String (content_url ~object_base_url image.object_key));
    ]

let video_metadata_json ~object_base_url (video : video_metadata) =
  `Assoc
    [
      ("mime", `String "video/webm");
      ("size", `Intlit (Int64.to_string video.size));
      ("width", `Int video.width);
      ("height", `Int video.height);
      ("frameRate", `Float video.frame_rate);
      ("frameCount", `Int video.frame_count);
      ("url", `String (content_url ~object_base_url video.object_key));
    ]

let asset_reference_json (reference : asset_reference) =
  `Assoc
    [
      ("namespace", `String reference.namespace);
      ("category", `String reference.category);
      ("id", `String reference.id);
    ]

let narrative_image_asset_json ~object_base_url (narrative_image_asset : narrative_image_asset) =
  `Assoc
    [
      ("namespace", `String "narrative");
      ("category", `String narrative_image_asset.category);
      ("id", `String narrative_image_asset.id);
      ("format", `String "image");
      ("mime", `String "image/png");
      ("size", `Intlit (Int64.to_string narrative_image_asset.image.size));
      ("url", `String (content_url ~object_base_url narrative_image_asset.image.object_key));
      ("width", `Int narrative_image_asset.image.width);
      ("height", `Int narrative_image_asset.image.height);
      ( "previewUrl",
        `String (thumbnail_content_url ~object_base_url narrative_image_asset.image.object_key) );
      ("materials", `List (List.map asset_reference_json narrative_image_asset.material_assets));
    ]

let material_asset_json ~object_base_url (material : material_asset) =
  `Assoc
    [
      ("namespace", `String "material");
      ("category", `String material.category);
      ("id", `String material.id);
      ("format", `String "image");
      ("mime", `String "image/png");
      ("size", `Intlit (Int64.to_string material.image.size));
      ("url", `String (content_url ~object_base_url material.image.object_key));
      ("width", `Int material.image.width);
      ("height", `Int material.image.height);
      ("materialType", `String material.kind);
      ("characterID", option_string material.character_id);
      ("role", option_string material.role);
      ("variant", option_string material.variant);
      ( "reverseReferences",
        `List (List.map asset_reference_json material.narrative_image_asset_references) );
    ]

let orphan_narrative_image_asset_json ~object_base_url (narrative_image_asset : orphan_narrative_image_asset) =
  `Assoc
    [
      ("namespace", `String "narrative");
      ("category", `String narrative_image_asset.category);
      ("id", `String narrative_image_asset.id);
      ("format", `String "image");
      ("mime", `String "image/png");
      ("size", `Intlit (Int64.to_string narrative_image_asset.size));
      ("url", `String (content_url ~object_base_url narrative_image_asset.asset_object_key));
      ("width", `Int narrative_image_asset.width);
      ("height", `Int narrative_image_asset.height);
      ( "previewUrl",
        `String
          (thumbnail_content_url ~object_base_url narrative_image_asset.asset_object_key) );
    ]

let orphan_narrative_media_asset_json ~object_base_url (media : orphan_narrative_media_asset) =
  `Assoc
    [
      ("namespace", `String "narrative");
      ("category", `String media.kind);
      ("id", `String media.id);
      ("format", `String media.kind);
      ("mime", `String media.mime);
      ("size", `Intlit (Int64.to_string media.size));
      ("url", `String (content_url ~object_base_url media.object_key));
    ]

let option_thumbnail_content_url ~object_base_url = function
  | None -> `Null
  | Some object_key ->
      `String (thumbnail_content_url ~object_base_url object_key)

let story_narrative_image_reference_json ~object_base_url (reference : story_narrative_image_reference)
    =
  let fields =
    [
      ( "asset",
        `Assoc
          [
            ("namespace", `String "narrative");
            ("category", `String reference.category);
            ("id", `String reference.asset_id);
          ] );
      ("kind", `String reference.kind);
    ]
  in
  let fields =
    if reference.is_anime_kv then fields @ [ ("isAnimeKV", `Bool true) ] else fields
  in
  let fields =
    match reference.title with
    | None -> fields
    | Some value when String.length value = 0 -> fields
    | Some value -> fields @ [ ("title", `String value) ]
  in
  let fields =
    match reference.subtitle with
    | None -> fields
    | Some value when String.length value = 0 -> fields
    | Some value -> fields @ [ ("subtitle", `String value) ]
  in
  let fields =
    let names = List.filter (fun value -> String.length value > 0) reference.names in
    if names = [] then fields else fields @ [ ("names", string_list names) ]
  in
  let fields =
    match reference.asset_object_key with
    | None -> fields
    | Some _ ->
        fields
        @ [
            ( "previewUrl",
              option_thumbnail_content_url ~object_base_url
                reference.asset_object_key );
          ]
  in
  `Assoc fields

let option_story_narrative_image_reference ~object_base_url = function
  | None -> `Null
  | Some reference -> story_narrative_image_reference_json ~object_base_url reference

let story_narrative_image_reference_list ~object_base_url references =
  `List (List.map (story_narrative_image_reference_json ~object_base_url) references)

let story_narrative_media_reference_json ~object_base_url
    (reference : story_narrative_media_reference) =
  let fields =
    [
      ( "asset",
        `Assoc
          [
            ("namespace", `String "narrative");
            ( "category",
              `String
                (if String.equal reference.kind "video" then "video"
                 else "audio") );
            ("id", `String reference.asset_id);
          ] );
    ]
  in
  let fields =
    if String.equal reference.kind "video" then fields
    else fields @ [ ("usage", `String reference.kind) ]
  in
  let fields =
    match reference.mime with None -> fields | Some value -> fields @ [ ("mime", `String value) ]
  in
  let fields =
    match reference.size with
    | None -> fields
    | Some size -> fields @ [ ("size", `Intlit (Int64.to_string size)) ]
  in
  let fields =
    match reference.object_key with
    | None -> fields
    | Some object_key ->
        fields @ [ ("url", `String (content_url ~object_base_url object_key)) ]
  in
  `Assoc fields

let story_narrative_media_reference_list ~object_base_url references =
  `List
    (List.map
       (story_narrative_media_reference_json ~object_base_url)
       references)

let narrative_media_asset_json ~object_base_url (asset : narrative_media_asset) =
  let option_float = function None -> `Null | Some value -> `Float value in
  let option_int = function None -> `Null | Some value -> `Int value in
  `Assoc
    [
      ("namespace", `String "narrative");
      ("category", `String asset.kind);
      ("id", `String asset.id);
      ("format", `String asset.kind);
      ("mime", `String asset.mime);
      ("size", `Intlit (Int64.to_string asset.size));
      ("duration", option_float asset.duration);
      ("sampleRate", option_int asset.sample_rate);
      ("width", option_int asset.width);
      ("height", option_int asset.height);
      ("frameRate", option_float asset.frame_rate);
      ("frameCount", option_int asset.frame_count);
      ("url", `String (content_url ~object_base_url asset.object_key));
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
  | Archive_parent { archive_category; group_id; group_name } ->
      `Assoc
        [
          ("kind", `String "archive");
          ("archiveCategory", `String archive_category);
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
        ( "representativeAssetReference",
          option_story_narrative_image_reference ~object_base_url
            summary.representative_narrative_image_asset_reference );
        ( "previewAssetReferences",
          story_narrative_image_reference_list ~object_base_url
            summary.preview_narrative_image_asset_references );
      ])

let story_detail_json ~object_base_url (detail : story_detail) =
  `Assoc
    (story_fields detail.story
    @ [
        ("parent", collection_parent_json detail.parent);
        ("text", `String detail.story.text);
        ( "media",
          story_narrative_media_reference_list ~object_base_url
            detail.story.media_references );
        ( "imageReferences",
          story_narrative_image_reference_list ~object_base_url
            detail.story.narrative_image_asset_references );
      ])

let score_image_reference_json ~object_base_url (reference : score_image_reference)
    =
  `Assoc
    [
      ("namespace", `String "presentation");
      ("category", `String reference.category);
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
      ("namespace", `String "presentation");
      ("category", `String reference.category);
      ("id", `String reference.id);
      ( "video",
        match reference.video with
        | None -> `Null
        | Some video -> video_metadata_json ~object_base_url video );
    ]

let option_score_video_reference ~object_base_url = function
  | None -> `Null
  | Some reference -> score_video_reference_json ~object_base_url reference

let gallery_reference_json ~object_base_url (narrative_image_asset : gallery_reference) =
  `Assoc
    [
      ("cgID", `String narrative_image_asset.cg_id);
      ( "asset",
        `Assoc
          [
            ("namespace", `String "narrative");
            ("category", `String narrative_image_asset.category);
            ("id", `String narrative_image_asset.asset_id);
          ] );
      ( "previewUrl",
        option_thumbnail_content_url ~object_base_url
          narrative_image_asset.asset_object_key );
    ]

let gallery_group_json ~object_base_url (group : gallery_group) =
  `Assoc
    [
      ("id", `String group.id);
      ("position", `Int group.position);
      ("name", `String group.name);
      ("description", `String group.description);
      ("relatedStoryID", option_string group.related_story_id);
      ("relatedStageID", option_string group.related_stage_id);
      ( "references",
        `List (List.map (gallery_reference_json ~object_base_url) group.references)
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
        ( "groups",
          `List
            (List.map (gallery_group_json ~object_base_url) gallery.groups) );
      ])

let option_gallery ~object_base_url = function
  | None -> `Null
  | Some gallery -> gallery_json ~object_base_url gallery

let gallery_summary_json ~object_base_url (summary : gallery_summary) =
  `Assoc
    (gallery_fields summary.gallery
    @ [
        ( "previewUrls",
          `List
            (List.map
               (fun object_key ->
                 `String (thumbnail_content_url ~object_base_url object_key))
               summary.preview_asset_object_keys) );
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

let section_fields ~object_base_url (section : section) =
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
      story_narrative_media_reference_list ~object_base_url
        section.opening_media_references );
  ]

let section_json ~object_base_url section =
  `Assoc (section_fields ~object_base_url section)

let movement_item_json ~object_base_url = function
  | Divider divider ->
      `Assoc
        [
          ("kind", `String "divider");
          ("id", `String divider.id);
          ("position", `Int divider.position);
          ("subName", `String divider.sub_name);
          ("icon", option_score_image_reference ~object_base_url divider.icon);
          ("video", option_score_video_reference ~object_base_url divider.video);
        ]
  | Section { position; section } ->
      `Assoc
        [
          ("kind", `String "section");
          ("position", `Int position);
          ("section", section_json ~object_base_url section);
        ]

let movement_detail_json ~object_base_url (detail : movement_detail) =
  `Assoc
    (movement_fields ~object_base_url detail.movement
    @ [
        ( "items",
          `List (List.map (movement_item_json ~object_base_url) detail.items) );
      ])

let section_detail_json ~object_base_url
    (detail : section_detail) =
  `Assoc
    (section_fields ~object_base_url detail.section
    @ [
        ( "activeBackgroundVideo",
          option_score_video_reference ~object_base_url
            detail.active_background_video );
        ( "stories",
          `List
            (List.map (story_summary_json ~object_base_url) detail.stories) );
        ( "media",
          story_narrative_media_reference_list ~object_base_url
            detail.media_references );
        ( "imageReferences",
          story_narrative_image_reference_list ~object_base_url detail.narrative_image_asset_references );
        ("gallery", option_gallery ~object_base_url detail.gallery);
      ])

let archive_index_entry_json (entry : archive_index_entry) =
  `Assoc
    [
      ("archiveCategory", `String entry.category);
      ("groupCount", `Int entry.group_count);
    ]

let archive_group_fields (group : archive_group) =
  [
    ("id", `String group.id);
    ("name", `String group.name);
    ("archiveCategory", `String group.category);
    ("type", `String group.group_type);
  ]

let archive_group_summary_json ~object_base_url (summary : archive_group_summary)
    =
  `Assoc
    (archive_group_fields summary.group
    @ [
        ( "representativeAssetReference",
          option_story_narrative_image_reference ~object_base_url
            summary.representative_narrative_image_asset_reference );
        ( "previewAssetReferences",
          story_narrative_image_reference_list ~object_base_url
            summary.preview_narrative_image_asset_references );
      ])

let archive_group_detail_json ~object_base_url (detail : archive_group_detail) =
  `Assoc
    (archive_group_fields detail.group
    @ [
        ( "representativeAssetReference",
          option_story_narrative_image_reference ~object_base_url
            detail.representative_narrative_image_asset_reference );
        ( "previewAssetReferences",
          story_narrative_image_reference_list ~object_base_url
            detail.preview_narrative_image_asset_references );
        ( "stories",
          `List
            (List.map (story_summary_json ~object_base_url) detail.stories) );
        ( "media",
          story_narrative_media_reference_list ~object_base_url
            detail.media_references );
        ( "imageReferences",
          story_narrative_image_reference_list ~object_base_url detail.narrative_image_asset_references );
        ( "openingMedia",
          story_narrative_media_reference_list ~object_base_url
            detail.opening_media_references );
        ("gallery", option_gallery ~object_base_url detail.gallery);
      ])

let related_narrative_image_asset_json ~object_base_url (variant : related_narrative_image_asset) =
  `Assoc
    [
      ("assetID", `String variant.asset_id);
      ("names", string_list variant.names);
      ( "previewUrl",
        `String
          (thumbnail_content_url ~object_base_url variant.asset_object_key)
      );
    ]

let narrative_image_occurrence_json (occurrence : narrative_image_occurrence) =
  `Assoc
    [
      ("parent", collection_parent_json occurrence.parent);
      ("storyID", `String occurrence.story_id);
      ("storyName", `String occurrence.story_name);
      ("storyCode", `String occurrence.story_code);
      ("storyTagText", `String occurrence.story_tag_text);
    ]

let narrative_asset_gallery_reference_json (reference : narrative_asset_gallery_reference) =
  `Assoc
    [
      ("galleryID", `String reference.gallery_id);
      ("galleryName", `String reference.gallery_name);
      ("galleryDescription", `String reference.gallery_description);
      ("groupID", `String reference.group_id);
      ("groupName", `String reference.group_name);
      ("groupDescription", `String reference.group_description);
      ("cgID", `String reference.cg_id);
    ]

let narrative_media_asset_reverse_references_json (references : narrative_media_asset_reverse_references) =
  `Assoc
    [
      ("occurrences", `List (List.map narrative_image_occurrence_json references.occurrences));
      ("collections", `List (List.map collection_parent_json references.collections));
    ]

let narrative_image_asset_reverse_references_json ~object_base_url
    (references : narrative_image_asset_reverse_references) =
  `Assoc
    [
      ("names", string_list references.names);
      ( "characterVariants",
        `List
          (List.map (related_narrative_image_asset_json ~object_base_url)
             references.character_variants) );
      ( "textures",
        `List (List.map (related_narrative_image_asset_json ~object_base_url) references.textures) );
      ("occurrences", `List (List.map narrative_image_occurrence_json references.occurrences));
      ( "galleries",
        `List (List.map narrative_asset_gallery_reference_json references.galleries) );
    ]

let search_result_json ~object_base_url (result : search_result) =
  `Assoc
    [
      ("kind", `String result.kind);
      ("id", `String result.id);
      ("category", option_string result.category);
      ("title", `String result.title);
      ("subtitle", option_string result.subtitle);
      ( "previewUrl",
        match result.thumbnail_object_key with
        | None -> `Null
        | Some object_key ->
            `String (thumbnail_content_url ~object_base_url object_key) );
      ( "parent",
        match result.parent with
        | None -> `Null
        | Some parent -> collection_parent_json parent );
    ]

let option_int = function None -> `Null | Some value -> `Int value
let option_float = function None -> `Null | Some value -> `Float value

let presentation_asset_fields (asset : presentation_asset) =
  [
    ("namespace", `String "presentation");
    ("category", `String asset.category);
    ("id", `String asset.id);
    ("format", `String asset.format);
    ("mime", `String asset.mime);
    ("size", `Intlit (Int64.to_string asset.size));
    ("width", option_int asset.width);
    ("height", option_int asset.height);
    ("duration", option_float asset.duration);
    ("referenceCount", `Int asset.reference_count);
  ]

let presentation_asset_summary_json ~object_base_url asset =
  `Assoc
    (presentation_asset_fields asset
    @ [
        ( "previewUrl",
          if String.equal asset.format "image" then
            `String (content_url ~object_base_url asset.object_key)
          else `Null );
      ])

let presentation_reverse_reference_json
    (reference : presentation_reverse_reference) =
  `Assoc
    [
      ("ownerType", `String reference.owner_type);
      ("ownerID", `String reference.owner_id);
      ("movementID", `String reference.movement_id);
      ("role", `String reference.role);
      ("name", `String reference.name);
    ]

let presentation_asset_detail_json ~object_base_url detail =
  `Assoc
    (presentation_asset_fields detail.asset
    @ [
        ( "url",
          `String
            (content_url ~object_base_url detail.asset.object_key) );
        ("frameRate", option_float detail.asset.frame_rate);
        ("frameCount", option_int detail.asset.frame_count);
        ( "reverseReferences",
          `List
            (List.map presentation_reverse_reference_json
               detail.reverse_references) );
      ])
