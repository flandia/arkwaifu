type object_metadata = {
  object_key : string;
  byte_size : int64;
  width : int;
  height : int;
}

type art = {
  id : string;
  category : string;
  image : object_metadata;
  source_art_ids : string list;
}

type source_art = {
  id : string;
  character_id : string;
  role : string;
  variant : string;
  image : object_metadata;
}

type art_reference = {
  art_id : string;
  kind : string;
  category : string;
  title : string option;
  subtitle : string option;
  names : string list;
  composition_object_key : string option;
}

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

type story_group = {
  id : string;
  name : string;
  group_type : string;
}

type story_summary = {
  story : story;
  representative_art_reference : art_reference option;
  preview_art_references : art_reference list;
}

type story_group_summary = {
  group : story_group;
  representative_art_reference : art_reference option;
  preview_art_references : art_reference list;
}

type story_group_detail = {
  group : story_group;
  representative_art_reference : art_reference option;
  preview_art_references : art_reference list;
  art_references : art_reference list;
}

type gallery_entry = {
  id : string;
  position : int;
  name : string;
  description : string;
  art_id : string;
  category : string;
  composition_object_key : string option;
}

type gallery = {
  id : string;
  name : string;
  description : string;
  entries : gallery_entry list;
}

type gallery_summary = {
  gallery : gallery;
  preview_composition_object_keys : string list;
}

type art_sibling = {
  art_id : string;
  names : string list;
  composition_object_key : string;
}

type art_occurrence = {
  group_id : string;
  group_name : string;
  group_type : string;
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

let object_json ~object_base_url (image : object_metadata) =
  `Assoc
    [
      ("byteSize", `Intlit (Int64.to_string image.byte_size));
      ("width", `Int image.width);
      ("height", `Int image.height);
      ("contentUrl", `String (content_url ~object_base_url image.object_key));
    ]

let art_json ~object_base_url (art : art) =
  `Assoc
    [
      ("id", `String art.id);
      ("category", `String art.category);
      ( "thumbnailContentUrl",
        `String
          (thumbnail_content_url ~object_base_url art.image.object_key) );
      ("image", object_json ~object_base_url art.image);
      ("sourceArtIDs", string_list art.source_art_ids);
    ]

let source_art_json ~object_base_url (source : source_art) =
  `Assoc
    [
      ("id", `String source.id);
      ("characterID", `String source.character_id);
      ("role", `String source.role);
      ("variant", `String source.variant);
      ("image", object_json ~object_base_url source.image);
    ]

let option_thumbnail_content_url ~object_base_url = function
  | None -> `Null
  | Some object_key ->
      `String (thumbnail_content_url ~object_base_url object_key)

let reference_json ~object_base_url (reference : art_reference) =
  `Assoc
    [
      ("artID", `String reference.art_id);
      ("kind", `String reference.kind);
      ("category", `String reference.category);
      ("title", option_string reference.title);
      ("subtitle", option_string reference.subtitle);
      ("names", string_list reference.names);
      ( "thumbnailContentUrl",
        option_thumbnail_content_url ~object_base_url
          reference.composition_object_key );
    ]

let option_reference ~object_base_url = function
  | None -> `Null
  | Some reference -> reference_json ~object_base_url reference

let reference_list ~object_base_url references =
  `List (List.map (reference_json ~object_base_url) references)

let story_fields ~object_base_url (story : story) =
  [
    ("id", `String story.id);
    ("groupID", `String story.group_id);
    ("tag", `String story.tag);
    ("tagText", `String story.tag_text);
    ("code", `String story.code);
    ("name", `String story.name);
    ("info", `String story.info);
    ("artReferences", reference_list ~object_base_url story.art_references);
  ]

let story_json ~object_base_url story =
  `Assoc (story_fields ~object_base_url story)

let story_summary_json ~object_base_url (summary : story_summary) =
  `Assoc
    (story_fields ~object_base_url summary.story
    @ [
        ( "representativeArtReference",
          option_reference ~object_base_url summary.representative_art_reference );
        ( "previewArtReferences",
          reference_list ~object_base_url summary.preview_art_references );
      ])

let story_group_fields (group : story_group) =
  [
    ("id", `String group.id);
    ("name", `String group.name);
    ("type", `String group.group_type);
  ]

let story_group_summary_json ~object_base_url (summary : story_group_summary) =
  `Assoc
    (story_group_fields summary.group
    @ [
        ( "representativeArtReference",
          option_reference ~object_base_url summary.representative_art_reference );
        ( "previewArtReferences",
          reference_list ~object_base_url summary.preview_art_references );
      ])

let story_group_detail_json ~object_base_url (detail : story_group_detail) =
  `Assoc
    (story_group_fields detail.group
    @ [
        ( "representativeArtReference",
          option_reference ~object_base_url detail.representative_art_reference );
        ( "previewArtReferences",
          reference_list ~object_base_url detail.preview_art_references );
        ( "artReferences",
          reference_list ~object_base_url detail.art_references );
      ])

let gallery_entry_json ~object_base_url (entry : gallery_entry) =
  `Assoc
    [
      ("id", `String entry.id);
      ("position", `Int entry.position);
      ("name", `String entry.name);
      ("description", `String entry.description);
      ("artID", `String entry.art_id);
      ("category", `String entry.category);
      ( "thumbnailContentUrl",
        option_thumbnail_content_url ~object_base_url
          entry.composition_object_key );
    ]

let gallery_fields (gallery : gallery) =
  [
    ("id", `String gallery.id);
    ("name", `String gallery.name);
    ("description", `String gallery.description);
  ]

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

let gallery_json ~object_base_url (gallery : gallery) =
  `Assoc
    (gallery_fields gallery
    @ [
        ( "entries",
          `List
            (List.map
               (gallery_entry_json ~object_base_url)
               gallery.entries) );
      ])

let art_sibling_json ~object_base_url (sibling : art_sibling) =
  `Assoc
    [
      ("artID", `String sibling.art_id);
      ("names", string_list sibling.names);
      ( "thumbnailContentUrl",
        `String
          (thumbnail_content_url ~object_base_url
             sibling.composition_object_key) );
    ]

let art_occurrence_json (occurrence : art_occurrence) =
  `Assoc
    [
      ("groupID", `String occurrence.group_id);
      ("groupName", `String occurrence.group_name);
      ("groupType", `String occurrence.group_type);
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
        `List
          (List.map (art_sibling_json ~object_base_url) context.siblings) );
      ( "occurrences",
        `List (List.map art_occurrence_json context.occurrences) );
    ]
