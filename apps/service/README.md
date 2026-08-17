# Run the Arkwaifu service

This package runs the OCaml 5.5 Dream read service. It downloads the published `arkwaifu.sqlite3`, validates schema version 2, and serves one local read-only generation through Caqti. See the [HTTP API reference](API.md) for the complete web contract.

## Understand the service boundary

The service reads published data and returns JavaScript Object Notation (JSON) metadata. It does not download game data, write database rows, process images, or require updater and object-store credentials.

The service returns direct public Uniform Resource Locators (URLs) for images and thumbnails. It has no image content or redirect endpoints, so browsers fetch image bytes from the bucket or content delivery network (CDN).

`GET /sitemap.txt` renders the website's text sitemap from the current SQLite generation. The main website's `robots.txt` may reference this cross-origin URL; a successful database refresh updates subsequent sitemap responses without a web rebuild.

## Configure the process

Set `ARKWAIFU_OBJECT_BASE_URL` before starting the service. The remaining settings have deployment defaults:

- **`ARKWAIFU_OBJECT_BASE_URL`**: Required absolute HTTP or HTTPS public bucket or CDN base URL used to construct image links, such as `https://objects.example/arkwaifu`
- **`ARKWAIFU_CN_OBJECT_BASE_URL`**: Optional public object base URL for the China mirror, such as `https://assets.cn.arkwaifu.cc`
- **`ARKWAIFU_DATABASE_URL`**: Absolute HTTP or HTTPS database download URL; defaults to `<ARKWAIFU_OBJECT_BASE_URL>/arkwaifu.sqlite3`
- **`ARKWAIFU_DATABASE_CACHE_DIR`**: Writable process-private generation directory; defaults to `/var/lib/arkwaifu/database`
- **`ARKWAIFU_DATABASE_POLL_SECONDS`**: Positive polling interval in seconds; defaults to `30`
- **`ARKWAIFU_DATABASE_DOWNLOAD_TIMEOUT_SECONDS`**: Positive timeout for one complete database transfer in seconds; defaults to `600`
- **`ARKWAIFU_INTERFACE`**: Listen address; defaults to `0.0.0.0`
- **`ARKWAIFU_PORT`**: Listen port from 1 through 65,535; defaults to `8080`

The service must read the database URL without S3 credentials unless your deployment supplies an authenticated HTTP intermediary. Configure database responses with `Cache-Control: no-cache`, and preserve ETag headers for conditional polling.

When `ARKWAIFU_CN_OBJECT_BASE_URL` is set, the service uses it only for a
request whose exact `X-Forwarded-Host` value is `api.cn.arkwaifu.cc`. Configure
ESA to overwrite that header on requests from the API mirror. Direct requests
to `api.arkwaifu.cc`, missing headers, and every other header value continue to
use `ARKWAIFU_OBJECT_BASE_URL`. The header selects only public image URLs; it
does not select a database or grant access to private data.

## Refresh the database safely

Startup fails closed so the service never accepts requests without a valid database. The startup sequence is:

1. Download `arkwaifu.sqlite3` into `ARKWAIFU_DATABASE_CACHE_DIR` with a unique `.part` filename.
2. Rename the completed download.
3. Open SQLite with `write=false` and `create=false`.
4. Require schema version 2 and successfully read the required schema. This also rejects SQLite runtimes too old to parse its `STRICT` tables.
5. Start Dream after the generation passes its schema check.

The service polls at `ARKWAIFU_DATABASE_POLL_SECONDS` and sends the last entity tag (ETag) as `If-None-Match`. Hypertext Transfer Protocol (HTTP) 304 preserves the current generation. For a changed object, the service downloads and validates the new file before switching readers.

A successful refresh drains the previous connection pool before removing its file. A download, HTTP, SQLite, or schema failure leaves the last valid generation serving. `ARKWAIFU_DATABASE_DOWNLOAD_TIMEOUT_SECONDS` bounds the complete request and response-body stream.

Each service process owns its cache directory and refresh loop. Do not share a cache directory between processes. A rolling deployment gives each process an independent current generation.

The database is monolithic, so each startup and published change transfers the complete file. Reserve space for the current and incoming generations during refresh.

## Prepare historical thumbnails

Archives published before thumbnail support need one backfill before the frontend can use direct thumbnail URLs. Run the updater from its application directory, then deploy the service before the frontend:

```console
Push-Location apps/updateloop
uv run updateloop run art --complete
Pop-Location
```

Future art updates publish thumbnails for changed compositions. Thumbnail keys follow `ART/<resVersion>/thumbnail/<category>/<name>.webp`.

## Build and test the service

The Docker build pins OCaml 5.5 and runs the reader tests. Build the test stage and runtime image with:

```console
Push-Location apps/service
docker build --target build -t arkwaifu-service-build:dev .
docker build -t arkwaifu-service:dev .
Pop-Location
```

The contract-test target reruns the reader suite against the updater-owned production schema. Supply that schema as a named build context:

```bash
docker buildx build --target contract-test \
  --build-context database-schema=../updateloop/src \
  -f Dockerfile .
```

For a native opam switch, install the dependencies from `arkwaifu_service.opam`. On Windows, use the command below so the process enters the project opam switch and then loads a modern MSYS2 `mingw64` SQLite runtime. You can copy the command into the ignored repository-local `.vscode/tasks.json`; do not commit machine-specific tasks. The opam-managed SQLite 3.34 DLL cannot parse schema version 2's `STRICT` tables.

## Run the local stack

Start MinIO in Docker and run this service natively from `apps/service/`:

```console
Push-Location dev
docker compose up -d minio minio-init
Pop-Location
```

After starting local MinIO, use its public `arkwaifu` bucket as the development archive ground truth:

```console
$env:ARKWAIFU_OBJECT_BASE_URL = "http://127.0.0.1:59000/arkwaifu"
$env:ARKWAIFU_DATABASE_URL = "http://127.0.0.1:59000/arkwaifu/arkwaifu.sqlite3"
$env:ARKWAIFU_DATABASE_CACHE_DIR = "E:\arkwaifu\service-database"
$env:ARKWAIFU_PORT = "5174"
cmd.exe /d /c 'opam exec -- cmd.exe /d /v:on /c "set PATH=C:\opt\msys64\mingw64\bin;!PATH!& dune exec arkwaifu-service"'
```

Check `http://127.0.0.1:5174/health` from another terminal.

## Maintain the persistence boundary

The updater-owned SQLite schema is the writer and reader contract. The `Database` module hides SQLite queries, conditional downloads, schema checks, and generation replacement from HTTP handlers. Tests use temporary SQLite databases through the same reader.

The design has no release tables, staged rows, active pointers, or PostgreSQL settings. `unit_versions` stores each unit’s `resVersion`, and HTTP queries read the current local generation.
