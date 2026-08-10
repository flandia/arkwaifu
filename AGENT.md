# Working notes for Arkwaifu

## Scope

Arkwaifu is undergoing a breaking rewrite. The repository has three
application packages:

- `apps/updateloop/` is the Python 3.14 writer and art/locale pipeline.
- `apps/service/` is the OCaml 5.5 Dream read service.
- `apps/web/` reserves space for a later JavaScript frontend rewrite.

Search, frontend implementation, and compatibility with the Go v1 API are
outside the current scope. Use v1.9.4 as a behavioral reference when a rewrite
detail is unclear.

Other important paths are:

- `apps/updateloop/src/arkwaifu.sql` — the sole SQLite schema source, embedded
  in the updater package.
- `infra/compose.yaml` — versioned MinIO for local development.

## Persistence and publication

The persisted database is the fixed S3 object `arkwaifu.sqlite3`. There is no
PostgreSQL service, release table, staging state, or activation pointer.
`updateloop run` is the updater's only public command; it accepts `art`,
`CN`, `EN`, `JP`, `KR`, and `TW`, and requests all six when no units
are supplied.

Keep this publication order:

1. Detect every requested unit's current upstream `resVersion` concurrently.
2. Pull or initialize `arkwaifu.sqlite3` and compare its unit versions.
3. Prepare every changed requested unit concurrently.
4. Apply the requested changes in one local SQLite transaction.
5. Batch-upload all required PNGs with bounded concurrency.
6. Upload `arkwaifu.sqlite3` last.

The final database PUT is the publication point. SQLite statement and commit
constraints validate writes; runtime code checks `user_version` but does not
run a separate `quick_check`, `integrity_check`, or
`foreign_key_check`.

Art object keys are
`ART/<resVersion>/<variant>/<category>/<name>.png`, where `variant` is
`composition` or `source`. Names are logical identifiers, not content
hashes. Persist only upstream `resVersion` values, not repository URLs or
commit identifiers.

Retain history. Bucket versioning is the rollback mechanism for overwritten
objects, and updater code must not garbage-collect old versions or unreachable
PNGs. Do not run more than one logical writer against the same bucket.

Incomplete upstream data is normal. Empty locale sections, missing story text,
or missing art references should warn and continue.
`--suppress-incomplete-upstream-warnings` suppresses only those expected
warnings. `--force` can rebuild locales at their current version and can force a
full art build for a new version. It cannot replace art at the already-published
`resVersion`, because those PNG keys are live before the database changes.

## Upstreams, extraction, and cache

Art comes from the official Windows client CDN. Locale data comes from the
unpinned `master` branch of `ArknightsAssets/ArknightsGamedata`; the
detected `versionId` is the locale's `resVersion`.

The default cache is `.cache/`. Art resources live below their `resVersion` and
retain four independently reusable products:

1. `fetched` — downloaded CDN wrapper.
2. `unwrapped` — inner Unity bundle.
3. `extracted` — uncomposed Unity exports.
4. `rendered` — composition/source PNGs and a resource manifest.

One run-scoped locale source owns the all-server game-data snapshot. It caches
exactly one `.cache/game-data/archive.zip`, admitted against all requested
locale `versionId` values, while locale-specific extracted files remain below
`.cache/<resVersion>/game-data/<unit>/extracted/`.

`--no-cache` uses the same layout under a run-scoped temporary directory that
must remain alive through PNG and database upload. Keep rendered PNGs
file-backed; do not retain the full art set in parent-process memory.

Downloads and extraction processes are independently bounded. Each process
handles one resource, invokes the extractor with one inner worker, and is
recycled with `max_tasks_per_child=1`. Preserve the LZ4AK decoder patch, the
`dyn/...` path normalization, and the missing-MonoScript fallback when
updating UnityPy.

## Read service

The service downloads `arkwaifu.sqlite3` before accepting traffic, requires
schema version 1, and opens it read-only. It polls with `If-None-Match`; a
successful replacement becomes the new local generation, while refresh errors
leave the last compatible generation serving. Each process owns a private
writable database cache directory. See `apps/service/README.md` for routes and
configuration.

## Development

```powershell
# Python updater
Push-Location apps/updateloop
uv sync --group dev
uv run ruff check .
uv run pytest
Pop-Location

# Local object storage
docker compose -f infra/compose.yaml up -d minio minio-init

# OCaml service without a host OCaml installation
docker build --target build -t arkwaifu-service-build:dev apps/service
docker compose -f infra/compose.yaml --profile service up -d --build
```

Ordinary tests must remain deterministic and offline. Live CDN/game-data smoke
updates are manual pre-deployment checks. Add focused regressions for parser,
extraction, image processing, SQLite writes, object publication, and refresh
behavior.

Do not commit downloaded bundles, generated PNGs, local databases, caches,
virtual environments, or credentials. Preserve unrelated working-tree changes.
