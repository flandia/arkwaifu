# Working notes for Arkwaifu

## Scope

Arkwaifu is undergoing a breaking rewrite. The repository has three
application packages:

- `apps/updateloop/` is the Python 3.14 writer and art/locale pipeline.
- `apps/service/` is the OCaml 5.5 Dream read service.
- `apps/web/` reserves space for a later JavaScript frontend rewrite.

Search, frontend implementation, and the Go v1 API are outside the current
scope. Use v1.9.4 as a behavioral reference when a rewrite detail is unclear,
but do not carry its API or database format into the rewrite without a current
requirement.

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

The final database PUT publishes the database metadata. PNG uploads happen
after the local transaction under the contributing art `resVersion` and before
the database PUT. Treat PNG keys as create-only: accept an existing object only
when its size, content type, and immutable cache policy match, and fail on a
conflict. A failed PNG batch can therefore leave unreachable objects, but it
does not change the keys referenced by the currently published database.
SQLite statement and commit constraints validate writes; runtime code checks
`user_version` but does not run a separate `quick_check`, `integrity_check`, or
post-write `foreign_key_check`. The updater creates schema version 2 and rejects
databases with any other declared schema version; recreate development databases
made with an earlier schema.

Art object keys are
`ART/<resVersion>/<variant>/<category>/<name>.png`. The implemented variants
are `composition` for final art and `source` for retained character layers.
The platform from which a compensating asset was obtained is not part of its
variant or object key. Names are logical identifiers, not content hashes. Final
art identity is `(category, art_id)`, and every story or gallery reference
carries both fields.
The version segment is the art version which contributed that particular PNG;
one cumulative database may consequently point into several historical version
prefixes. Persist upstream `resVersion` values, but do not persist repository
URLs or commit identifiers.

Retain history. The first version of a complete build is full; each later art
version processes only bundles selected as changed. The cumulative manifest
keeps the newest record for each logical identity and uploads each final winner
under the version which contributed it. It does not copy records from unchanged
bundles, so unchanged database rows keep their existing object keys. Updater
code must not garbage-collect old version prefixes or unreachable PNG keys.
Object storage therefore records the `resVersion` values which contributed
published PNGs, but the updater does not enumerate it to discover version
history. Bucket versioning remains the rollback mechanism for the overwritten
database object. Do not run more than one logical writer against the same
bucket.

Incomplete upstream data is normal. Empty locale sections, missing story text,
or missing art references should warn and continue.
`--suppress-incomplete-upstream-warnings` suppresses only those expected
warnings. `--force` can rebuild locales at their current version, but is not
supported for an update containing art: a full art rebuild would copy unchanged
records into a new version prefix. The
explicit `run art --complete` mode is a separate exception: it may cumulatively
process all recorded Windows versions from oldest to current and backfill art
even when the database already records the current `resVersion`; it cannot be
combined with `--force` or other units.

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
schema version 2, and opens it read-only. It polls with `If-None-Match`; a
successful replacement becomes the new local generation, while refresh errors
leave the last valid generation serving. Each process owns a private
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
