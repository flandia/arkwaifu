# Arkwaifu service

This package is the OCaml 5.5 Dream read service. It downloads the fixed
`arkwaifu.sqlite3` object, checks its schema version, opens a local read-only
SQLite generation through Caqti, and serves it until a newer valid generation
is available. It never downloads game data, writes database rows, processes
images, or needs updater/S3 credentials.

## HTTP interface

| Method and path | Result |
| --- | --- |
| `GET /health` | Current local SQLite connectivity |
| `GET /api/arts/:category/:id` | Selected composition metadata with direct composition and thumbnail object-store URLs |
| `GET /api/source-arts/:id` | Original body, face, or whole-body layer metadata with a direct object-store URL |
| `GET /api/:locale/arts/:category/:id/context` | Localized names, related character variants, and every story occurrence of an available art |
| `GET /api/:locale/story-groups` | Ordered story groups with rotating-card preview references |
| `GET /api/:locale/story-groups/:id` | One group with previews and all available, deduplicated `artReferences` |
| `GET /api/:locale/story-groups/:id/stories` | Ordered story summaries with rotating-card previews; `artReferences` remains empty |
| `GET /api/:locale/stories/:id` | Story metadata and ordered art references |
| `GET /api/:locale/galleries` | Gallery summaries |
| `GET /api/:locale/galleries/:id` | Gallery and ordered entries |

Locales are explicit and case-insensitive: `CN`, `EN`, `JP`, `KR`, and `TW`.
Unknown resources and locales return `404`. A database/schema failure returns a
small `503` response without exposing local paths or connection details.
An existing story group with no stories returns `200` with an empty JSON list.
Its group-detail route also returns `200`, with a `null`
`representativeArtReference`, an empty `previewArtReferences` list, and an empty
`artReferences` list. Missing groups return `404` from both routes.
All responses allow public cross-origin reads with
`Access-Control-Allow-Origin: *`. `OPTIONS` requests return `204` and advertise
the supported `GET, OPTIONS` methods.

Story-group and story-summary card backgrounds use this shape:

```json
{
  "representativeArtReference": {
    "artID": "avg_1",
    "kind": "picture",
    "category": "image",
    "title": null,
    "subtitle": null,
    "names": [],
    "thumbnailContentUrl": "https://objects.example/arkwaifu/ART/v1/thumbnail/image/avg_1.webp"
  },
  "previewArtReferences": [
    {
      "artID": "avg_1",
      "kind": "picture",
      "category": "image",
      "title": null,
      "subtitle": null,
      "names": [],
      "thumbnailContentUrl": "https://objects.example/arkwaifu/ART/v1/thumbnail/image/avg_1.webp"
    }
  ]
}
```

`previewArtReferences` contains at most three references in a stable,
pseudorandom-looking order seeded by the group or story ID. It contains only
references that resolve against `arts`. When at least one `image` is available,
the list contains illustrations only; otherwise it falls back to backgrounds.
The frontend rotates through this list. `representativeArtReference` remains for
backward compatibility and is always the first preview, or `null` when the list
is empty.

Illustration previews prefer art used by fewer distinct story groups (for group
cards) or stories (for stage cards). The stable shuffle only breaks rarity
ties. Background fallback uses the same ranking.

The art-context route returns deduplicated localized `names`, every distinct
localized story `occurrence`, and `siblings` for character art. A sibling is an
available character whose identifier has the same exact prefix before `#`; its
payload includes localized names and a direct `thumbnailContentUrl`. Other art
categories return an empty sibling list.

Every art-reference payload includes a nullable direct `thumbnailContentUrl`.
The group-detail `artReferences` list contains every resolvable reference across
the group's stories, preserves story/reference order, and deduplicates by
`category` plus `artID`. Story-detail references and gallery entries are
preserved even when unresolved, in which case `thumbnailContentUrl` is `null`.
This is populated by the existing SQL joins, without per-reference queries.

These fields are derived from the existing schema-version 2 relationship
`story_groups -> stories -> story_art_references`, with `arts` used as the
availability check. They add no table, column, materialized aggregate, or schema
migration.

The service exposes object-store locations through metadata and has no image
content or redirect endpoints, keeping it out of the image data path. Thumbnail
URLs point directly at the updater-published object-store key, derived during
JSON serialization from the joined composition key without another database
column: `ART/<resVersion>/thumbnail/<category>/<name>.webp`.
The former `/api/arts/:category/:id/content`,
`/api/arts/:category/:id/thumbnail/content`, and
`/api/source-arts/:id/content` paths are not routed and return `404`.

Before deploying a frontend that uses these URLs against an archive created
before thumbnails were introduced, run the one-time historical backfill:

```console
uv run updateloop run art --complete
```

Deploy the service after the backfill and before the frontend. Normal future
art runs publish thumbnails for their changed winners automatically.

Configure the bucket or CDN for public reads; original PNG objects are
published as `image/png` under
`ART/<resVersion>/<variant>/<category>/<name>.png`, with
`Cache-Control: public, max-age=31536000, immutable`. The version is the
snapshot which contributed that create-only object. One current database can
therefore reference several historical version prefixes. Public art metadata
includes object location, byte size, and dimensions, but no redundant object
variant or PNG SHA. The path uses `composition` for final art and `source` for
retained character layers; the route already determines which kind is returned.

## Database refresh lifecycle

Startup is fail-closed:

1. Download `arkwaifu.sqlite3` into
   `ARKWAIFU_DATABASE_CACHE_DIR` using a unique `.part` file.
2. Rename the completed download locally.
3. Open SQLite with `write=false` and `create=false`.
4. Require schema version 2.
5. Start Dream only after that generation is healthy.

The service then polls at `ARKWAIFU_DATABASE_POLL_SECONDS`, sending the last ETag
as `If-None-Match`. HTTP `304` keeps the existing generation. A changed file is
downloaded and schema-checked before it replaces the current local
generation; the previous pool is drained and its file removed afterward. A
download, HTTP, open, or schema failure is logged and the last valid
generation continues serving. A failure on the initial download
prevents startup because there is no known-good in-memory generation yet.
The complete request and body stream are bounded by
`ARKWAIFU_DATABASE_DOWNLOAD_TIMEOUT_SECONDS`.

Each service process owns its own local database copy and refresh loop. The
cache directory is process-private; do not share it between service processes.
There is no shared database connection or coordination between instances.
Rolling the fixed object back to a previous S3 version produces another ETag
change, so instances adopt the restored file after their next successful poll.

The database is monolithic. A locale-only production-schema measurement was
234 MiB raw, and the complete database with art metadata is larger. Every
process transfers the whole file at startup and after any published change,
including a one-locale change. Allow room for both the current and incoming
generation during refresh. PostgreSQL connection pools and `COPY` tuning do not
apply.

## Configuration

- `ARKWAIFU_OBJECT_BASE_URL` — required public bucket or CDN base URL used to
  construct PNG links, for example `https://objects.example/arkwaifu`.
- `ARKWAIFU_DATABASE_URL` — database download URL; defaults to
  `<ARKWAIFU_OBJECT_BASE_URL>/arkwaifu.sqlite3`.
- `ARKWAIFU_DATABASE_CACHE_DIR` — writable local generation directory; defaults
  to `/var/lib/arkwaifu/database`.
- `ARKWAIFU_DATABASE_POLL_SECONDS` — positive polling interval; defaults to
  `30`.
- `ARKWAIFU_DATABASE_DOWNLOAD_TIMEOUT_SECONDS` — positive timeout for one full
  database HTTP transfer; defaults to `600`.
- `ARKWAIFU_INTERFACE` — listen address; defaults to `0.0.0.0`.
- `ARKWAIFU_PORT` — listen port; defaults to `8080`.

The database and PNG URLs must be readable by the service without S3 credentials
unless the deployment supplies an authenticated HTTP intermediary. Serve the
database with revalidation (`Cache-Control: no-cache`) and preserve ETag headers
for efficient conditional polling.

## Development

OCaml does not need to be installed on the host. Build and run tests in the
pinned OCaml 5.5 image:

```console
docker build --target build -t arkwaifu-service-build:dev apps/service
docker build -t arkwaifu-service:dev apps/service
```

CI also reruns the reader suite against the updater's sole production schema
through a named build context, without copying that SQL into this package:

```console
docker buildx build --target contract-test --build-context database-schema=apps/updateloop/src -f apps/service/Dockerfile apps/service
```

Start MinIO, run the Python updater once to publish `arkwaifu.sqlite3`, then run
the service profile:

```console
docker compose -f infra/compose.yaml up -d minio minio-init
docker compose -f infra/compose.yaml --profile service up -d --build
curl http://127.0.0.1:58080/health
```

For a native opam switch, install the locked dependency set from
`arkwaifu_service.opam`, then run `dune runtest` and
`dune exec arkwaifu-service`.

## Persistence seam

The SQLite schema shipped by the updater is the writer/reader contract. The
service's `Database` module is the persistence seam: HTTP handlers ask it for
domain records, while its live adapter hides SQLite queries, conditional
downloads, schema checks, and generation replacement. An in-memory adapter
supports deterministic tests. Dream remains limited to routing and
JSON responses.

There are no release tables, staged rows, active pointers, or PostgreSQL
settings. `unit_versions` contains only each unit's `resVersion`; HTTP reads use
the rows in the one current database generation.
