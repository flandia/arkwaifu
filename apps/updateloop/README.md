# Run the Arkwaifu updater

The Python 3.14 updater publishes upstream Arknights artwork and locale data as one SQLite database plus versioned image and Score-video objects in S3-compatible storage. Use this guide to run, configure, and test the updater.

## Choose an update command

Run the updater from `apps/updateloop`. The `run` subcommand accepts `artwork` and the locale units `CN`, `EN`, `JP`, `KR`, and `TW`.

The following commands cover each supported update mode:

```console
uv run updateloop run artwork
uv run updateloop run artwork --complete
uv run updateloop run artwork --archive
uv run updateloop run artwork --complete --archive
uv run updateloop run CN EN
uv run updateloop run
uv run updateloop run CN --force
uv run updateloop run artwork --no-cache
uv run updateloop run --suppress-incomplete-upstream-warnings
```

Choose a mode based on the data you need to publish:

- `run artwork` updates artwork that changed since the published artwork version
- `run artwork --complete` rebuilds the recorded Windows artwork history and retains the newest record for each logical identity
- `run artwork --archive` archives every missing historical CN/Windows asset-bundle wrapper
- `run artwork --complete --archive` archives history, then rebuilds the database from the same version sequence
- `run CN EN` updates only the selected locales
- `run` updates artwork and all five locales
- `--force` rebuilds selected locales at their current versions
- `--no-cache` uses temporary storage without reading or writing `.cache`
- `--suppress-incomplete-upstream-warnings` hides expected warnings for missing upstream story text, artwork, or empty locale sections

The command removes duplicate units while preserving their first occurrence. It detects every requested unit concurrently and publishes nothing if detection or preparation fails.

`--complete` requires `artwork` as the only unit. You cannot combine it with `--force`. The command may backfill a database that already records the current artwork version.

`--archive` requires a request containing `artwork`; a bare `run --archive` is valid because the default request includes artwork. The first archive starts with a full snapshot of the oldest recorded Windows version, then stores only new or changed wrappers for each later version. Later runs resume after the newest archived `hot_update_list.json`. Archive preparation must finish before database publication begins.

`--force` supports locale-only updates. The updater rejects forced artwork updates because one artwork version prefix must keep one meaning.

## Understand the publication boundary

The updater applies every changed unit in one local SQLite transaction, uploads image objects, and overwrites `arkwaifu.sqlite3` last. This fixed database object is the only publication boundary.

These rules protect the visible database:

- A build or SQLite failure prevents all requested database changes from becoming visible
- An asset-bundle archive failure prevents a new database generation from being published
- Immutable Portable Network Graphics (PNG), audio, and video objects upload only after the SQLite transaction commits
- Derived WebP thumbnails upload before the database overwrite
- A database upload failure leaves the previous database object current
- S3 bucket versioning retains overwritten database generations
- One logical writer must own each bucket because publication has no lock or compare-and-swap token

Missing upstream data remains publishable when the database can represent it. Missing story text removes directive-derived artwork references, unresolved artwork references remain in locale metadata, and empty story or gallery sections emit warnings.

Read [Publication and storage](docs/publication.md) for the transaction, object-key, cache, execution, and failure contracts.

## Configure object storage

The command-line interface (CLI) reads an optional `.env` file from its current working directory. Process environment variables override values from `.env`.

Set these required variables:

- `ARKWAIFU_S3_BUCKET`
- `ARKWAIFU_S3_ACCESS_KEY_ID`
- `ARKWAIFU_S3_SECRET_ACCESS_KEY`

Enable versioning on production buckets before the first publication. The updater does not configure bucket policy, versioning, or lifecycle rules. The repository's local development MinIO bucket is the deliberate exception: it suspends versioning and is the sole development archive ground truth.

Use these optional variables when their defaults do not fit the deployment:

- `ARKWAIFU_S3_ENDPOINT_URL`: use a custom endpoint such as MinIO
- `ARKWAIFU_S3_REGION`: defaults to `us-east-1`
- `ARKWAIFU_S3_PATH_STYLE`: defaults to `false`; enable it for local MinIO
- `ARKWAIFU_ARCHIVE_S3_ENDPOINT_URL`: defaults to `https://sgp1.digitaloceanspaces.com`
- `ARKWAIFU_ARCHIVE_S3_REGION`: defaults to `sgp1`
- `ARKWAIFU_ARCHIVE_S3_BUCKET`: defaults to `arkwaifu-ab`
- `ARKWAIFU_ARCHIVE_S3_PATH_STYLE`: defaults to `false`
- `ARKWAIFU_ARTWORK_VERSION_URL`: overrides the official Windows version endpoint
- `ARKWAIFU_ARTWORK_ASSET_BASE_URL`: overrides the official Windows asset root
- `ARKWAIFU_DOWNLOAD_WORKERS`: limits concurrent artwork bundle downloads and defaults to `16`
- `ARKWAIFU_EXTRACTION_WORKERS`: limits concurrent extraction and Artwork rendering processes; Python selects the process-pool size when this variable is unset
- `ARKWAIFU_GITHUB_API_URL`: defaults to `https://api.github.com`
- `ARKWAIFU_GITHUB_TOKEN`: raises the GitHub REST API rate limit for requests such as artwork-version history; public story-history clones do not use it

Size `ARKWAIFU_EXTRACTION_WORKERS` for both CPU capacity and peak memory.

The asset-bundle archive reuses `ARKWAIFU_S3_ACCESS_KEY_ID` and `ARKWAIFU_S3_SECRET_ACCESS_KEY`; it does not require a second credential pair. Archive objects use `CN/Windows/<resVersion>/<CDN-filename>.dat`, with `hot_update_list.json` uploaded last for each completed version.

Set the `ARKWAIFU_ARCHIVE_S3_*` variables in the environment that should receive the archive, then use `--archive` for an archive run.

Create the ignored development environment from the committed local MinIO template. The CLI reads `.env` automatically:

```powershell
Copy-Item .env.example .env
```

Keep production credentials in the ignored `.env.prod` and opt into them explicitly:

```console
uv run --env-file .env.prod updateloop run
```

Set `ARKWAIFU_ARTWORK_VERSION_URL` and `ARKWAIFU_ARTWORK_ASSET_BASE_URL` together when you use a compatible Windows mirror. The automatic pipeline does not extract Android assets.

The updater reads the `ARKWAIFU_ARTWORK_*` mirror variables above. The older `ARKWAIFU_ART_*` names are no longer supported and are ignored.

Read [Upstream data and locale classification](docs/upstream-data.md) for source provenance, version checks, story classification, and historical text recovery.

## Manage the cache

The updater stores reusable downloads and generated files under `.cache/` in its current working directory. It validates each cache entry before reuse and replaces corrupted entries automatically.

Run from `apps/updateloop/`; never start the updater from the repository root:

```console
uv run updateloop run
```

Use `--no-cache` for an isolated run. The temporary cache remains available until the SQLite transaction, image uploads, and database upload finish.

A first complete artwork update can require substantial local storage. Historical artwork runs used 10 to 12 GiB, so reserve at least 15 GiB for the project cache. A first asset-bundle archive downloads every bundle changed across the recorded history and can require considerably more network transfer and object storage.

## Recover unavailable artwork manually

The service reads selected object keys from SQLite, so uploading an image without updating the database does not expose it. Use the manual procedure only when official Windows history cannot provide an artwork identity.

Follow [Add fallback artwork manually](docs/manual-fallback-artwork.md) to upload the image, update the relevant SQLite rows, and publish the database last.

## Run development checks

Install development dependencies, then run static checks and tests from `apps/updateloop`:

```console
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Ordinary tests run offline and produce deterministic results. Live content-delivery network (CDN) and game-data smoke updates remain deployment checks.

Start MinIO from `dev/` before you run the integration test:

```powershell
Push-Location ../../dev
docker compose up -d minio minio-init
Pop-Location
$env:ARKWAIFU_INTEGRATION = "1"
uv run pytest tests/integration/test_database_minio.py
```

Run one live end-to-end smoke update before the first deployment of a new SQLite schema or upstream parser path.
