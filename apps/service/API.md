# Use the Arkwaifu HTTP API

The service exposes read-only JSON metadata for narrative, material, and
presentation assets, plus the Score, Archive, and Gallery hierarchies. `CN`,
`EN`, `JP`, `KR`, and `TW` are supported locales. Locale path parameters are
case-insensitive.

Percent-encode every identifier as one complete path segment. For example,
`cg/part#1$2` is sent as `cg%2Fpart%231%242`; the service decodes it exactly
once and preserves the original ID.

All routes accept `GET`. `OPTIONS` returns HTTP 204. Public CORS headers are
included. Missing records and invalid route values return HTTP 404 with
`{"error":"not_found"}`. Database or metadata failures return HTTP 503 with
`{"error":"service_unavailable"}`.

## Routes

| Route | Result |
| --- | --- |
| `GET /health` | `{"status":"ok"}` |
| `GET /sitemap.txt` | UTF-8 text sitemap |
| `GET /api/assets/narrative/:asset-category/:asset-id` | One narrative image, video, or audio asset |
| `GET /api/assets/material/:asset-category/:asset-id` | One material image asset |
| `GET /api/:locale/assets/narrative/:asset-category/:asset-id/reverse-references` | Localized narrative reverse references |
| `GET /api/:locale/assets/presentation` | Presentation Asset Catalog |
| `GET /api/:locale/assets/presentation/:asset-category/:asset-id` | Presentation asset detail and reverse references |
| `GET /api/:locale/orphans` | All orphan narrative assets for one locale |
| `GET /api/:locale/search?q=...` | Up to 100 ranked metadata results |
| `GET /api/:locale/scores` | Movement summaries |
| `GET /api/:locale/scores/:movement-id` | Movement and ordered items |
| `GET /api/:locale/scores/:movement-id/:section-id` | Section detail |
| `GET /api/:locale/scores/:movement-id/:section-id/:story-id` | Score Story detail |
| `GET /api/:locale/archives` | Archive Category counts |
| `GET /api/:locale/archives/:archive-category` | Archive Group summaries |
| `GET /api/:locale/archives/:archive-category/:group-id` | Archive Group detail |
| `GET /api/:locale/archives/:archive-category/:group-id/:story-id` | Archive Story detail |
| `GET /api/:locale/galleries` | Gallery summaries |
| `GET /api/:locale/galleries/:gallery-id` | Gallery detail |

Archive categories are `events`, `operator-record`, `integrated-strategies`,
`reclamation-algorithm`, and `others`. The old Artwork, Source Layer, media,
and unreferenced routes do not exist.

## Asset model

Every complete asset record has the same identity and file fields:

```json
{
  "namespace": "narrative",
  "category": "character",
  "id": "char_220_grani#5$1",
  "format": "image",
  "mime": "image/png",
  "size": 1048576,
  "url": "https://objects.example/ART/v1/composition/character/char.png"
}
```

The identity is `(namespace, category, id)`. `format` is `image`, `video`, or
`audio`; it is not part of the identity. Images add `width` and `height`.
Videos add dimensions, `duration`, `frameRate`, and `frameCount`. Audio adds
`duration` and `sampleRate`. Unavailable optional format metadata is `null`.

A common Asset Reference contains identity only:

```json
{"namespace":"narrative","category":"illustration","id":"cg/part"}
```

Array order carries reference order. Database positions are not public fields.

## Narrative and material assets

Narrative image categories are `illustration`, `background`, `item`, and
`character`. A narrative image adds `previewUrl` and ordered material
references:

```json
{
  "namespace":"narrative",
  "category":"illustration",
  "id":"cg/part",
  "format":"image",
  "mime":"image/png",
  "size":123,
  "url":"https://…",
  "width":800,
  "height":600,
  "previewUrl":"https://…",
  "materials":[
    {"namespace":"material","category":"illustration","id":"panel_source"}
  ]
}
```

A Material Asset has the same common image fields, `materialType` (`character`
or `panel`), optional `characterID`, `role`, and `variant`, plus
`reverseReferences` to final narrative images.

Narrative media categories are `video` and `audio`; their category and format
are equal. Reverse references return `occurrences` for Stories and
`collections` for Sections or Archive Groups that directly use the media.
Narrative image reverse references return localized `names`,
`characterVariants`, `textures`, Story `occurrences`, and Gallery Group
`galleries`.

`GET /api/:locale/orphans` returns one discriminated array containing all six
narrative categories. Orphan status is calculated independently for the
requested locale and is not an error state. Every returned item keeps the
common identity and file fields.

## Story references and parents

A Story image reference wraps its Asset Reference and adds contextual fields:

```json
{
  "asset":{"namespace":"narrative","category":"character","id":"amiya"},
  "kind":"character",
  "names":["阿米娅"],
  "previewUrl":"https://…"
}
```

`isAnimeKV`, `title`, `subtitle`, `names`, and `previewUrl` are omitted when
they have no value.

A Story media reference contains `asset` and, for audio, `usage` (`sound` or
`music`). Published-file metadata adds `mime`, `size`, and `url`; fields without
values are omitted. The reference remains present when its asset file has not
been published.

Stories and galleries identify their hierarchy owner with either a Score or
Archive parent:

```json
{"kind":"score","movementID":"movement-a","movementName":"为了明日","sectionID":"section-a","sectionName":"方舟"}
```

```json
{"kind":"archive","archiveCategory":"events","groupID":"event-a","groupName":"孤星"}
```

Story summaries expose `representativeAssetReference` and
`previewAssetReferences`. Story details expose `parent`, source `text`, ordered
`media`, and ordered `imageReferences`.

## Presentation Asset Catalog

`GET /api/:locale/assets/presentation` returns every presentation image and
video. Optional query parameters are:

- `category`: one presentation category such as `key-visual` or `video`
- `format`: `image` or `video`
- `orphaned`: `true` for zero references or `false` for referenced assets

Each summary contains the common identity and file metadata, dimensions or
duration, `previewUrl`, and `referenceCount`. Detail adds `url`, video frame
metadata, and `reverseReferences`:

```json
{
  "ownerType":"section",
  "ownerID":"section-a",
  "movementID":"movement-a",
  "role":"key-visual",
  "name":"方舟"
}
```

`ownerType` is `movement`, `section`, or `movement-divider`. The role uses
kebab-case, including `key-visual` and `retro-background`.

## Scores, Archives, Galleries, and search

Movement detail adds ordered Section and Movement Divider items. Section
detail adds its active presentation video, Story summaries, aggregate `media`
and `imageReferences`, and an optional Gallery. Archive Group detail exposes
the same Story and asset aggregates.

Gallery summaries contain `previewUrls`. Gallery detail contains ordered
Groups, and each Group contains ordered `references`. A Gallery Reference has
`cgID`, a nested narrative image `asset`, and nullable `previewUrl`.

Search results have `kind`, `id`, nullable `category`, `title`, nullable
`subtitle`, nullable `previewUrl`, and nullable `parent`. Kinds are `story`,
`movement`, `section`, `archive_group`, `gallery`, and `narrative_asset`.

## Sitemap and object URLs

`GET /sitemap.txt` includes canonical locale, Score, Archive, Gallery,
Presentation Asset Catalog, Orphan Narrative Asset, and About pages. It omits
individual assets, Stories, and query URLs.

Returned object URLs use the configured public origin. When the optional China
origin is configured, exact `X-Forwarded-Host: api.cn.arkwaifu.cc` selects that
origin. Clients should use returned URLs instead of rebuilding them.
