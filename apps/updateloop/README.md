# Run the Arkwaifu updater

The Python 3.14 updater publishes upstream Arknights art and locale data as one SQLite database plus versioned image objects in S3-compatible storage. Use this guide to run, configure, and test the updater.

## Choose an update command

Run the updater from `apps/updateloop`. The `run` subcommand accepts `art` and the locale units `CN`, `EN`, `JP`, `KR`, and `TW`.

The following commands cover each supported update mode:

```console
uv run updateloop run art
uv run updateloop run art --complete
uv run updateloop run CN EN
uv run updateloop run
uv run updateloop run CN --force
uv run updateloop run art --no-cache
uv run updateloop run --suppress-incomplete-upstream-warnings
```

Choose a mode based on the data you need to publish:

- `run art` updates art that changed since the published art version
- `run art --complete` rebuilds the recorded Windows art history and retains the newest record for each logical identity
- `run CN EN` updates only the selected locales
- `run` updates art and all five locales
- `--force` rebuilds selected locales at their current versions
- `--no-cache` uses temporary storage without reading or writing `.cache`
- `--suppress-incomplete-upstream-warnings` hides expected warnings for missing upstream story text, art, or empty locale sections

The command removes duplicate units while preserving their first occurrence. It detects every requested unit concurrently and publishes nothing if detection or preparation fails.

`--complete` requires `art` as the only unit. You cannot combine it with `--force`. The command may backfill a database that already records the current art version.

`--force` supports locale-only updates. The updater rejects forced art updates because one art version prefix must keep one meaning.

## Understand the publication boundary

The updater applies every changed unit in one local SQLite transaction, uploads image objects, and overwrites `arkwaifu.sqlite3` last. This fixed database object is the only publication boundary.

These rules protect the visible database:

- A build or SQLite failure prevents all requested database changes from becoming visible
- Immutable Portable Network Graphics (PNG) objects upload only after the SQLite transaction commits
- Derived WebP thumbnails upload before the database overwrite
- A database upload failure leaves the previous database object current
- S3 bucket versioning retains overwritten database generations
- One logical writer must own each bucket because publication has no lock or compare-and-swap token

Missing upstream data remains publishable when the database can represent it. Missing story text removes directive-derived art references, unresolved art references remain in locale metadata, and empty story or gallery sections emit warnings.

Read [Publication and storage](docs/publication.md) for the transaction, object-key, cache, execution, and failure contracts.

## Configure object storage

The command-line interface (CLI) reads an optional `.env` file from its current working directory. Process environment variables override values from `.env`.

Set these required variables:

- `ARKWAIFU_S3_BUCKET`
- `ARKWAIFU_S3_ACCESS_KEY_ID`
- `ARKWAIFU_S3_SECRET_ACCESS_KEY`

Enable versioning on the bucket before the first publication. The updater does not configure bucket policy, versioning, or lifecycle rules.

Use these optional variables when their defaults do not fit the deployment:

- `ARKWAIFU_S3_ENDPOINT_URL`: use a custom endpoint such as MinIO
- `ARKWAIFU_S3_REGION`: defaults to `us-east-1`
- `ARKWAIFU_S3_PATH_STYLE`: defaults to `false`; enable it for local MinIO
- `ARKWAIFU_ART_VERSION_URL`: overrides the official Windows version endpoint
- `ARKWAIFU_ART_ASSET_BASE_URL`: overrides the official Windows asset root
- `ARKWAIFU_DOWNLOAD_WORKERS`: limits concurrent art bundle downloads and defaults to `16`
- `ARKWAIFU_EXTRACTION_WORKERS`: limits concurrent extraction and composition processes; Python selects the process-pool size when this variable is unset
- `ARKWAIFU_GITHUB_API_URL`: defaults to `https://api.github.com`
- `ARKWAIFU_GITHUB_TOKEN`: raises the GitHub REST API rate limit for requests such as art-version history; public story-history clones do not use it

Size `ARKWAIFU_EXTRACTION_WORKERS` for both CPU capacity and peak memory.

The repository includes local MinIO settings in `../../infra/dev.env.example`. Pass that file directly instead of copying it:

```console
uv run --env-file ../../infra/dev.env.example updateloop run
```

Set `ARKWAIFU_ART_VERSION_URL` and `ARKWAIFU_ART_ASSET_BASE_URL` together when you use a compatible Windows mirror. The automatic pipeline does not extract Android assets.

Read [Upstream data and locale classification](docs/upstream-data.md) for source provenance, version checks, story classification, and historical text recovery.

## Manage the cache

The updater stores reusable downloads and generated files under `.cache/` in its current working directory. It validates each cache entry before reuse and replaces corrupted entries automatically.

Run from the repository root when you want the cache there:

```console
uv run --project apps/updateloop updateloop run
```

Use `--no-cache` for an isolated run. The temporary cache remains available until the SQLite transaction, image uploads, and database upload finish.

A first complete art update can require substantial local storage. Historical runs used 10 to 12 GiB, so reserve at least 15 GiB for the project cache.

## Recover unavailable art manually

The service reads selected object keys from SQLite, so uploading an image without updating the database does not expose it. Use the manual procedure only when official Windows history cannot provide an art identity.

Follow [Add fallback art manually](docs/manual-fallback-art.md) to upload the image, update the relevant SQLite rows, and publish the database last.

## Run development checks

Install development dependencies, then run static checks and tests from `apps/updateloop`:

```console
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Ordinary tests run offline and produce deterministic results. Live content-delivery network (CDN) and game-data smoke updates remain deployment checks.

Start MinIO before you run the integration test:

```powershell
docker compose -f ../../infra/compose.yaml up -d minio minio-init
$env:ARKWAIFU_INTEGRATION = "1"
uv run pytest tests/integration/test_database_minio.py
```

Run one live end-to-end smoke update before the first deployment of a new SQLite schema or upstream parser path.
