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

type gallery_entry = {
  id : string;
  position : int;
  name : string;
  description : string;
  art_id : string;
}

type gallery = {
  id : string;
  name : string;
  description : string;
  entries : gallery_entry list;
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

let reference_json (reference : art_reference) =
  `Assoc
    [
      ("artID", `String reference.art_id);
      ("kind", `String reference.kind);
      ("category", `String reference.category);
      ("title", option_string reference.title);
      ("subtitle", option_string reference.subtitle);
      ("names", string_list reference.names);
    ]

let story_json (story : story) =
  `Assoc
    [
      ("id", `String story.id);
      ("groupID", `String story.group_id);
      ("tag", `String story.tag);
      ("tagText", `String story.tag_text);
      ("code", `String story.code);
      ("name", `String story.name);
      ("info", `String story.info);
      ("artReferences", `List (List.map reference_json story.art_references));
    ]

let story_group_json (group : story_group) =
  `Assoc
    [
      ("id", `String group.id);
      ("name", `String group.name);
      ("type", `String group.group_type);
    ]

let gallery_entry_json (entry : gallery_entry) =
  `Assoc
    [
      ("id", `String entry.id);
      ("position", `Int entry.position);
      ("name", `String entry.name);
      ("description", `String entry.description);
      ("artID", `String entry.art_id);
    ]

let gallery_fields (gallery : gallery) =
  [
    ("id", `String gallery.id);
    ("name", `String gallery.name);
    ("description", `String gallery.description);
  ]

let gallery_summary_json gallery = `Assoc (gallery_fields gallery)

let gallery_json (gallery : gallery) =
  `Assoc
    (gallery_fields gallery
    @ [ ("entries", `List (List.map gallery_entry_json gallery.entries)) ])
