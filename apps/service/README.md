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
| `GET /api/arts/:category/:id` | Selected composition metadata and version-scoped content URL |
| `GET /api/arts/:category/:id/content` | `303` redirect to the selected composition PNG |
| `GET /api/source-arts/:id` | Original body, face, or whole-body layer metadata |
| `GET /api/source-arts/:id/content` | `303` redirect to the original PNG |
| `GET /api/:locale/story-groups` | Ordered story groups |
| `GET /api/:locale/stories/:id` | Story metadata and ordered art references |
| `GET /api/:locale/galleries` | Gallery summaries |
| `GET /api/:locale/galleries/:id` | Gallery and ordered entries |

Locales are explicit and case-insensitive: `CN`, `EN`, `JP`, `KR`, and `TW`.
Unknown resources and locales return `404`. A database/schema failure returns a
small `503` response without exposing local paths or connection details.

Content endpoints redirect instead of proxying PNG bytes. This keeps the
service out of the image data path. Configure the bucket or CDN for public
reads; PNG objects are published as `image/png` under
`ART/<resVersion>/<variant>/<category>/<name>.png`, with
`Cache-Control: public, max-age=31536000, immutable`. The version is the
snapshot which contributed that create-only object. One current database can
therefore redirect to several historical version prefixes. Public art metadata
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
JSON/redirect responses.

There are no release tables, staged rows, active pointers, or PostgreSQL
settings. `unit_versions` contains only each unit's `resVersion`; HTTP reads use
the rows in the one current database generation.
