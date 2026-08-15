# Use the Arkwaifu HTTP API

The service exposes read-only JSON metadata for composed artwork, Scores,
Archives, and galleries. `CN`, `EN`, `JP`, `KR`, and `TW` are the supported
locales; locale path parameters are case-insensitive. Percent-encode every
identifier used as one path segment. In particular, a composite artwork ID may
contain `/` and must be sent as `%2F`.

All routes accept `GET`. `OPTIONS` returns HTTP 204. Responses include public
cross-origin resource sharing headers. A missing record, invalid locale, or
invalid Archive kind returns HTTP 404 with `{"error":"not_found"}`. A database
or metadata failure returns HTTP 503 with
`{"error":"service_unavailable"}`.

## Routes

| Route | Result |
| --- | --- |
| `GET /health` | `{"status":"ok"}` |
| `GET /sitemap.txt` | UTF-8 text sitemap |
| `GET /api/arts/:category/:id` | Composed artwork |
| `GET /api/source-arts/:category/:id` | Category-qualified source artwork |
| `GET /api/unreferenced-arts` | Unreferenced artwork array |
| `GET /api/:locale/arts/:category/:id/context` | Localized artwork context |
| `GET /api/:locale/scores` | Movement summaries |
| `GET /api/:locale/scores/:movementID` | Movement and ordered items |
| `GET /api/:locale/scores/:movementID/:sectionID` | Movement Section detail |
| `GET /api/:locale/scores/:movementID/:sectionID/:storyID` | Score Story detail |
| `GET /api/:locale/archives` | Archive kind counts |
| `GET /api/:locale/archives/:kind` | Archive Group summaries |
| `GET /api/:locale/archives/:kind/:groupID` | Archive Group detail |
| `GET /api/:locale/archives/:kind/:groupID/:storyID` | Archive Story detail |
| `GET /api/:locale/galleries` | Gallery summaries across the hierarchy |
| `GET /api/:locale/galleries/:id` | Gallery display hierarchy |

Archive `:kind` is one of `events`, `operator-record`,
`integrated-strategies`, `reclamation-algorithm`, or `others`. There are no
legacy story-group or shallow Movement/Section/Group endpoints.

## Common metadata

Image metadata is:

```json
{"byteSize":123,"width":800,"height":600,"contentUrl":"https://…"}
```

Video metadata adds `frameRate` and `frameCount`:

```json
{
  "byteSize":12345,
  "width":1920,
  "height":1080,
  "frameRate":29.97002997002997,
  "frameCount":900,
  "contentUrl":"https://…"
}
```

A declared Score image reference is either `null`, when the locale metadata has
no identifier, or `{"id":"…","image":ImageMetadata|null}`. Video references
use `{"id":"…","video":VideoMetadata|null}`. The nested null distinguishes a
declared upstream identifier whose object has not yet been published from an
identifier that was never declared.

Artwork references have this shape:

```json
{
  "artID":"…",
  "kind":"picture",
  "category":"image",
  "title":null,
  "subtitle":null,
  "names":[],
  "thumbnailContentUrl":"https://…"
}
```

`thumbnailContentUrl` is null when the logical reference has no corresponding
composition. Preview lists use available `image` references when present and
otherwise available `background` references. They preserve source order,
deduplicate `(category, artID)`, and contain at most three entries.

## Artwork and source artwork

A composed artwork returns:

```json
{
  "id":"cg/part",
  "category":"image",
  "thumbnailContentUrl":"https://…",
  "image":{"byteSize":123,"width":800,"height":600,"contentUrl":"https://…"},
  "sourceArts":[{"category":"image","id":"panel/source"}]
}
```

Source identities are category-qualified. Source `kind` is `character` or
`composite_panel`:

```json
{
  "id":"panel/source",
  "category":"image",
  "kind":"composite_panel",
  "characterID":null,
  "role":null,
  "variant":null,
  "image":{"byteSize":50,"width":400,"height":300,"contentUrl":"https://…"}
}
```

Character sources populate `characterID`, `role`, and `variant`; composite
panels leave all three null. Unreferenced artwork objects contain `id`,
`category`, and `thumbnailContentUrl`.

Artwork context contains `names`, character `siblings`, and `occurrences`.
Every occurrence carries the same discriminated `parent` described below plus
`storyID`, `storyName`, `storyCode`, and `storyTagText`.

## Parents and Stories

Stories and galleries identify their hierarchy owner with one of:

```json
{
  "kind":"score",
  "movementID":"movement-a",
  "movementName":"为了明日",
  "sectionID":"section-a",
  "sectionName":"方舟"
}
```

```json
{
  "kind":"archive",
  "archiveKind":"events",
  "groupID":"event-a",
  "groupName":"孤星"
}
```

A Story summary contains `id`, `tag`, `tagText`, `code`, `name`, `info`,
`representativeArtReference`, and `previewArtReferences`. A Story detail
replaces the two preview fields with `parent` and the complete ordered
`artReferences` array. The deep route verifies that the Story belongs to the
Movement Section or Archive Group in its path.

## Scores

The `/scores` response is an ordered array of Movements:

```json
{
  "id":"movement-a",
  "name":"为了明日",
  "type":"continue",
  "position":0,
  "sectionCount":1,
  "startTime":1700000000,
  "icon":{"id":"icon-main","image":null},
  "logo":null,
  "background":null,
  "backgroundVideo":null
}
```

Movement `type` is `continue` or `discrete`; `sectionCount` is its number of
canonical Story Sections. Movement detail adds `items`. The
service stores the complete upstream placement graph but presents only
canonical `story_set` sections and `mainline_split` items, ordered by placement
position:

```json
[
  {
    "kind":"split",
    "id":"split-a",
    "position":0,
    "subName":"序曲",
    "icon":null,
    "video":null
  },
  {
    "kind":"section",
    "position":1,
    "section":{
      "id":"section-a",
      "name":"方舟",
      "description":"…",
      "type":"main_theme",
      "position":1,
      "sortByYear":0,
      "sortWithinYear":0,
      "storyCount":10,
      "keyVisual":null,
      "titleImage":null,
      "background":null,
      "decoration":null,
      "retroBackground":null
    }
  }
]
```

Section `type` is `main_theme`, `side_story`, or `vignette`. Section detail adds
`activeBackgroundVideo`, `stories`, aggregate `artReferences`, and
`gallery: GalleryDetail|null`. Its active video is the latest preceding
`mainline_split` video in the same Movement.

## Archives

The Archive index returns all five kinds, including zero counts:

```json
[{"kind":"events","groupCount":12}]
```

An Archive Group summary contains `id`, `name`, route `kind`, semantic `type`,
`representativeArtReference`, and `previewArtReferences`. Event `type` is
`side_story` or `vignette`; other values are `operator_record`,
`integrated_strategies`, `reclamation_algorithm`, or `others`. Group detail adds
`stories`, aggregate `artReferences`, and `gallery: GalleryDetail|null`.

## Galleries

Gallery summary objects contain `id`, `name`, `description`, discriminated
`parent`, and `previewThumbnailContentUrls`. Previews select the first artwork
from each distinct display in display order, skip unresolved compositions, and
stop after three displays. A later sibling in the same display is never used as
another summary preview.

Gallery detail owns the complete sibling hierarchy:

```json
{
  "id":"score-gallery",
  "name":"方舟画集",
  "description":"…",
  "parent":{"kind":"score","movementID":"…","movementName":"…","sectionID":"…","sectionName":"…"},
  "displays":[
    {
      "id":"display-one",
      "position":0,
      "name":"牺牲火炬",
      "description":"…",
      "relatedStoryID":"score-story",
      "relatedStageID":"0-1",
      "artworks":[
        {
          "position":0,
          "cgID":"upstream-first",
          "artID":"display-first",
          "category":"image",
          "thumbnailContentUrl":"https://…"
        }
      ]
    }
  ]
}
```

`cgID` is the upstream gallery member identifier. `artID` is the stable
composition identifier and may contain `/`. An unresolved member remains in
the display with a null thumbnail URL. There is no gallery-display endpoint;
clients select a display from this deep response.

## Sitemap and object URLs

`GET /sitemap.txt` contains canonical `https://arkwaifu.cc` locale, Score,
Archive, and gallery URLs. It contains no legacy `/stories` URLs. A successful
database refresh affects the next sitemap request.

Returned object URLs use the configured public origin. When the optional China
origin is configured, an exact `X-Forwarded-Host: api.cn.arkwaifu.cc` selects
that origin. Clients should use returned URLs rather than rebuilding them.
