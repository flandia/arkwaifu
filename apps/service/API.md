# Use the Arkwaifu HTTP API

The Arkwaifu Hypertext Transfer Protocol (HTTP) application programming interface (API) exposes read-only JavaScript Object Notation (JSON) metadata and the public text sitemap. It covers composed artwork, source layers, localized stories, and galleries. This reference defines every route, response shape, ordering guarantee, error, cross-origin policy, and direct object Uniform Resource Locator (URL).

## Send API requests

All routes accept `GET`. Every response includes public cross-origin resource sharing (CORS) headers:

- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, OPTIONS`
- `Access-Control-Allow-Headers: Accept, Content-Type`
- `Access-Control-Max-Age: 86400`

An `OPTIONS` request returns HTTP 204 without a body before path routing. Successful and application-error JSON responses use `application/json`; the sitemap uses UTF-8 `text/plain`. Missing resources and unsupported locales return HTTP 404 with `{"error":"not_found"}`. Database failures return HTTP 503 with `{"error":"service_unavailable"}` and do not expose local paths or connection details.

An unmatched path or unsupported method returns the Dream router’s HTTP 404 response. Clients should not depend on a JSON body for that router-level response.

Localized routes accept `CN`, `EN`, `JP`, `KR`, and `TW`. Locale values are case-insensitive. An unsupported locale returns HTTP 404.

Routes use these path parameters:

| Parameter | Meaning |
| --- | --- |
| `:locale` | One supported archive locale |
| `:category` | Exact artwork category: `image`, `background`, `item`, or `character` |
| `:id` | Exact, case-sensitive lowercase logical identifier for the artwork, source layer, story group, story, or gallery selected by the route |

Percent-encode reserved characters in path parameters. Collection routes return HTTP 200 with `[]` when a supported locale has no matching rows.

## Read health status

`GET /health` checks the current SQLite generation. A healthy reader returns HTTP 200:

```json
{"status":"ok"}
```

A failed SQLite check returns the standard HTTP 503 error body.

## Read the sitemap

`GET /sitemap.txt` renders a text sitemap from the current SQLite generation.
It contains absolute canonical `https://arkwaifu.cc` URLs for the five locale
homes, all story-section indexes and story groups, all gallery indexes and
galleries, and the canonical CN About and Unreferenced Artwork pages. Database
refreshes are reflected on the next request; no static web rebuild is needed.

## Read artwork

Artwork routes identify a composition by its exact `category` and `id`. Categories include `image`, `background`, `item`, and `character`.

| Route | HTTP 200 result |
| --- | --- |
| `GET /api/arts/:category/:id` | Composed artwork |
| `GET /api/source-arts/:id` | Source artwork |
| `GET /api/unreferenced-arts` | Unreferenced artwork array |
| `GET /api/:locale/arts/:category/:id/context` | Artwork context |

The composed-art response includes `id`, `category`, `thumbnailContentUrl`, `image`, and `sourceArtIDs`. Source artwork identifiers follow composition order. The `image` object includes `byteSize`, `width`, `height`, and `contentUrl`. Sizes use bytes, and dimensions use pixels.

The global unreferenced-art list contains compact objects with `id`, `category`, and `thumbnailContentUrl`. It orders rows by `image`, `background`, `item`, and `character`, then by artwork ID. An archive without unreferenced artwork returns HTTP 200 and `[]`.

The context response contains `names`, `siblings`, and `occurrences`. Names preserve first-occurrence order without duplicates. Character siblings share the exact identifier prefix before `#` and are ordered by artwork ID. Each sibling’s names preserve their first occurrence without duplicates. Other categories return an empty sibling list. Occurrences follow stored group and story positions and contain unique stories.

## Interpret response fields

Every object uses the fields and nullability in this table. Fields not marked nullable are always present with the listed JSON type.

| Object | Fields |
| --- | --- |
| Image metadata | `byteSize: number` in bytes, `width: number` in pixels, `height: number` in pixels, `contentUrl: string` |
| Composed artwork | `id: string`, `category: string`, `thumbnailContentUrl: string`, `image: Image metadata`, `sourceArtIDs: string[]` |
| Source artwork | `id: string`, `characterID: string`, `role: "body" \| "face" \| "whole_body"`, `variant: string`, `image: Image metadata` |
| Unreferenced artwork | `id: string`, `category: string`, `thumbnailContentUrl: string` |
| Artwork reference | `artID: string`, `kind: "picture" \| "character"`, `category: string`, `title: string \| null`, `subtitle: string \| null`, `names: string[]`, `thumbnailContentUrl: string \| null` |
| Artwork sibling | `artID: string`, `names: string[]`, `thumbnailContentUrl: string` |
| Artwork occurrence | `groupID: string`, `groupName: string`, `groupType: string`, `storyID: string`, `storyName: string`, `storyCode: string`, `storyTagText: string` |
| Artwork context | `names: string[]`, `siblings: Artwork sibling[]`, `occurrences: Artwork occurrence[]` |
| Story metadata | `id: string`, `groupID: string`, `tag: "before" \| "after" \| "interlude"`, `tagText: string`, `code: string`, `name: string`, `info: string` |
| Story summary | All Story metadata fields, `artReferences: []`, `representativeArtReference: Artwork reference \| null`, `previewArtReferences: Artwork reference[]` |
| Story detail | All Story metadata fields, `artReferences: Artwork reference[]` |
| Story-group summary | `id: string`, `name: string`, `type: string`, `representativeArtReference: Artwork reference \| null`, `previewArtReferences: Artwork reference[]` |
| Story-group detail | All Story-group summary fields, `artReferences: Artwork reference[]` |
| Gallery summary | `id: string`, `name: string`, `description: string`, `previewThumbnailContentUrls: string[]` |
| Gallery entry | `id: string`, `position: number`, `name: string`, `description: string`, `artID: string`, `category: string`, `thumbnailContentUrl: string \| null` |
| Gallery detail | `id: string`, `name: string`, `description: string`, `entries: Gallery entry[]` |

`title`, `subtitle`, and `thumbnailContentUrl` remain present when their value is null. A null thumbnail means the logical story reference or gallery entry has no matching composed artwork. Only `representativeArtReference` becomes null because its preview list is empty. Artwork-reference `names` preserve source order.

## Read story groups

Story-group routes return localized groups in stored position order. Each group has `id`, `name`, and a schema-defined `type`:

- `main_story`
- `major_event`
- `minor_event`
- `operator_record`
- `integrated_strategies`
- `reclamation_algorithm`
- `others`

`integrated_strategies` groups official Integrated Strategies ending stories by topic. `reclamation_algorithm` includes only Reclamation Algorithm stories with artwork references.

`others` groups the remaining eligible non-`[uc]` scripts by source directory. It includes tutorial and control scripts, and the singular `other` is not valid.

The story-group routes are:

| Route | HTTP 200 result |
| --- | --- |
| `GET /api/:locale/story-groups` | Story-group summary array |
| `GET /api/:locale/story-groups/:id` | Story-group detail |
| `GET /api/:locale/story-groups/:id/stories` | Story summary array |
| `GET /api/:locale/stories/:id` | Story detail |

An existing group without stories returns HTTP 200 and `[]` from its story-list route. Its detail route returns HTTP 200 with `representativeArtReference: null`, `previewArtReferences: []`, and `artReferences: []`. A missing group returns HTTP 404 from both routes.

Story summaries include `id`, `groupID`, `tag`, `tagText`, `code`, `name`, `info`, `artReferences`, `representativeArtReference`, and `previewArtReferences`. `artReferences` is always an empty list in summaries for compatibility. Story detail includes the complete `artReferences` list in stored source-reference position and omits preview fields.

## Use preview references

Story-group and story summaries include up to three stable card backgrounds in `previewArtReferences`. Each artwork reference has this shape:

```json
{
  "artID": "avg_1",
  "kind": "picture",
  "category": "image",
  "title": null,
  "subtitle": null,
  "names": [],
  "thumbnailContentUrl": "https://objects.example/arkwaifu/ART/v1/thumbnail/image/avg_1.webp"
}
```

Previews include only references that resolve against composed artwork. If a summary has an available `image`, the list contains only illustrations; otherwise it uses available `background` references. The service ranks artwork used by fewer distinct groups or stories first, then applies a stable ID-seeded shuffle for ties.

`representativeArtReference` is the first preview for compatibility. It is `null` when `previewArtReferences` is empty.

Group-detail `artReferences` preserves stored story and reference order and deduplicates by `category` plus `artID`. It includes only available artwork. Story-detail references remain present when unavailable, with `thumbnailContentUrl: null`.

## Read galleries

Gallery routes return localized metadata. They preserve gallery-entry position without adding per-gallery or per-entry queries.

| Route | HTTP 200 result |
| --- | --- |
| `GET /api/:locale/galleries` | Gallery summary array ordered by gallery ID |
| `GET /api/:locale/galleries/:id` | Gallery detail |

A gallery summary contains `id`, `name`, `description`, and `previewThumbnailContentUrls`. The preview array contains at most three direct thumbnail URLs. It uses available illustrations when possible and backgrounds only when no illustration is available. Selection orders artwork by a deterministic score seeded by the gallery ID, then by artwork ID, and removes duplicate object keys.

A gallery detail contains `id`, `name`, `description`, and `entries`. Each entry includes `id`, nonnegative stored `position`, `name`, `description`, `artID`, `category`, and `thumbnailContentUrl`. Unavailable entries remain in position with `thumbnailContentUrl: null`.

## Fetch direct object URLs

Metadata responses point directly to public bucket or CDN objects. The service percent-encodes each object-key path segment and removes one trailing slash from the configured base URL.

Composed and source Portable Network Graphics (PNG) objects use `ART/<resVersion>/<variant>/<category>/<name>.png`, where `variant` is `composition` or `source`. These PNG objects are create-only, so a current database can reference several historical `resVersion` prefixes.

Thumbnail WebP objects use `ART/<resVersion>/thumbnail/<category>/<name>.webp`. They are mutable, use `Content-Type: image/webp`, and keep the object store’s default cache policy.

Configure the object store for public reads. Published PNG objects use `Content-Type: image/png` and `Cache-Control: public, max-age=31536000, immutable`.

The former image-proxy routes are intentionally absent and return HTTP 404:

- `/api/arts/:category/:id/content`
- `/api/arts/:category/:id/thumbnail/content`
- `/api/source-arts/:id/content`
