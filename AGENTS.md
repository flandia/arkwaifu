# Work in the Arkwaifu repository

Arkwaifu v2 contains three applications that publish and read one SQLite archive. Follow this reference when you change their shared storage, publication, or API contracts.

## Keep application responsibilities separate

Each application owns one part of the system:

- `apps/updateloop/`: Python 3.14 archive writer with art and locale pipelines
- `apps/service/`: OCaml 5.5 Dream read service
- `apps/web/`: React 19 and React Router read-only frontend

The Go v1 API and global server-side search are outside the current scope. Use v1.9.4 only as a behavioral reference for unclear frontend details. Do not copy its API or database format without a current requirement.

## Run applications from their directories

Never run an application command with the repository root as its working directory. Run the updater from `apps/updateloop/`, the service from `apps/service/`, and the web app from `apps/web/`. Run Docker Compose commands from `dev/`. This keeps application caches, generated files, and tool state out of the repository root; in particular, do not recreate a root-level `.cache/` directory.

Docker is only for local MinIO. Start it from `dev/` with `docker compose up -d minio minio-init`; run the service and Vite on the host from their respective application directories. The local MinIO `arkwaifu` bucket is the sole development archive ground truth. Do not create or serve a second filesystem archive in the repository or under `E:\arkwaifu\dev-runtime`.

For a complete host preview, configure the host service with `ARKWAIFU_DATABASE_URL=http://127.0.0.1:59000/arkwaifu/arkwaifu.sqlite3` and `ARKWAIFU_OBJECT_BASE_URL=http://127.0.0.1:59000/arkwaifu`, then start it on port `5174` and start Vite with `VITE_API_BASE_URL=http://127.0.0.1:5174`. The updater's ignored `apps/updateloop/.env` points to this same MinIO bucket and is its default development target. Keep production credentials separately in ignored `.env.prod` and select them explicitly with `uv run --env-file .env.prod ...`. Do not add a repository-owned static runtime server; MinIO supplies object metadata, conditional requests, and byte-range responses used by media seeking. The development bucket deliberately suspends versioning and does not retain old object generations.

## Run the native OCaml service inside its opam switch

The native Windows service requires OCaml `5.5.0` and the exact dependencies in `apps/service/arkwaifu_service.opam`. Do not launch `_build/default/bin/main.exe` directly, and do not use a random system-wide `dune` environment. The process also needs one compatible MinGW runtime containing OpenSSL and a modern SQLite. A local development task must enter the opam switch first, then prepend the MSYS2 `mingw64` runtime for those native DLLs. Keep machine-specific tasks in the ignored `.vscode/tasks.json`. Do not work around a missing DLL by adding the LibreOffice directory to `PATH` or by copying DLLs beside the executable.

Create a project-local switch once from `apps/service/`; the generated `apps/service/_opam/` directory is ignored by Git:

```powershell
Push-Location apps/service
opam switch create . ocaml-base-compiler.5.5.0 --no-install
opam install . --deps-only --with-test
Pop-Location
```

Use `opam exec` for every native build, test, or service process so the command inherits the selected switch environment. The opam-managed MinGW sysroot currently contains SQLite 3.34, but schema version 2 uses `STRICT` tables and requires SQLite 3.37 or newer. On this Windows development machine, prepend the MSYS2 `mingw64` runtime after entering the opam environment; prepending it before `opam exec` does not work because opam prepends its own runtime again. Use the following commands directly or copy them into your ignored `.vscode/tasks.json`:

```powershell
Push-Location apps/service
cmd.exe /d /c 'opam exec -- cmd.exe /d /v:on /c "set PATH=C:\opt\msys64\mingw64\bin;!PATH!& dune build @runtest"'

$env:ARKWAIFU_OBJECT_BASE_URL = "http://127.0.0.1:59000/arkwaifu"
$env:ARKWAIFU_DATABASE_URL = "http://127.0.0.1:59000/arkwaifu/arkwaifu.sqlite3"
$env:ARKWAIFU_DATABASE_CACHE_DIR = "E:\arkwaifu\service-database"
$env:ARKWAIFU_PORT = "5174"
cmd.exe /d /c 'opam exec -- cmd.exe /d /v:on /c "set PATH=C:\opt\msys64\mingw64\bin;!PATH!& dune exec arkwaifu-service"'
Pop-Location
```

Do not use the `ucrt64` runtime for this MinGW-built executable. If the service reports `malformed database schema ... near "STRICT"`, it loaded opam's SQLite 3.34 DLL; inspect the running process and fix the launch order instead of changing the database schema or copying DLLs beside the executable.

For an interactive PowerShell session, opam can apply the same switch environment explicitly:

```powershell
(& opam env --switch=. --set-switch --shell=powershell) -split '\r?\n' |
  ForEach-Object { Invoke-Expression $_ }
```

Verify the active toolchain with `opam exec -- ocaml --version` and `opam exec -- dune --version`. If `opam` itself cannot start, repair the opam installation or its Windows shim first; running the switch's `dune.exe` directly is not an equivalent fix for missing runtime DLLs.

Two repository paths define shared infrastructure:

- `apps/updateloop/src/arkwaifu.sql`: sole SQLite schema source, embedded in the updater package
- `dev/compose.yaml`: MinIO configuration for local development

## Preserve the publication boundary

The updater publishes the fixed S3-compatible object `arkwaifu.sqlite3`. The system has no PostgreSQL service, release table, staging state, or activation pointer. `updateloop run` accepts `art`, `CN`, `EN`, `JP`, `KR`, and `TW`; it requests all six units when none are supplied.

Locale story/index units (`CN`, `EN`, `JP`, `KR`, and `TW`) may be rebuilt in full during ordinary updates. An art update is different: when an art change contains a breaking change, update it manually and process only the changed resource diff. Do not run a full art rebuild for a breaking change unless the user explicitly requests one.

Manual recovery scripts for a lagging remote are temporary tools. Do not add their one-off behavior, flags, or code paths to `updateloop`'s supported interface. Keep such a script only until the remote data catches up; after using it successfully, delete the script and any task-specific support.

Keep this publication order:

1. Detect each requested unit’s upstream `resVersion` concurrently
2. Pull or initialize `arkwaifu.sqlite3` and compare unit versions
3. Prepare each changed unit concurrently
4. Apply all requested changes in one local SQLite transaction
5. Upload required Portable Network Graphics (PNG) objects and derived thumbnails with bounded concurrency
6. Upload `arkwaifu.sqlite3` last

The final database upload publishes metadata. Image uploads occur after the local transaction and before that final upload. Store each image below the contributing art `resVersion`.

Treat composition and source PNG keys as create-only. Accept an existing object only when its size, content type, and immutable cache policy match. Fail when an existing object conflicts. Derived WebP thumbnails are replaceable and use the object store and content delivery network (CDN) cache defaults.

A failed image batch can leave unreachable PNG objects or partially replace thumbnails referenced by the current database. It cannot publish new database metadata. SQLite statement and commit constraints validate writes; runtime code checks `user_version` and probes the required schema without running separate `quick_check`, `integrity_check`, or post-write `foreign_key_check` operations.

The updater creates schema version 2 and rejects every other declared version. Beta schema changes have no table migration or compatibility layer. Recreate a development database when its shape or constraints differ, even when it declares version 2. The sole in-place exception is the additive `story_art_references_by_art (locale, art_id)` index, which the updater restores and republishes once when absent.

## Keep image identity stable

Composition and source keys use `ART/<resVersion>/<variant>/<category>/<name>.png`. Use `composition` for final art and `source` for retained character layers. Derived thumbnails use `ART/<resVersion>/thumbnail/<category>/<name>.webp`.

Do not encode the source platform in a compensating asset’s variant or object key. Names are logical identifiers, not content hashes. The pair `(category, art_id)` identifies final art, and each story or gallery reference carries both fields.

The version segment identifies the art version that contributed a PNG. One cumulative database can reference several historical version prefixes. Persist upstream `resVersion` values, but do not persist repository URLs or commit identifiers.

Retain historical version prefixes and unreachable PNG keys. A complete build processes its first version in full, processes only selected changed bundles in later versions, and keeps the newest record for each logical identity. Unchanged database rows retain their existing object keys. Bucket versioning provides rollback for the overwritten database object in production. The local development MinIO bucket is the explicit exception and keeps versioning suspended.

Run one logical writer per bucket. The publisher has no lock or compare-and-swap token.

## Handle incomplete upstream data explicitly

Empty locale sections, missing story text, and missing art references are expected upstream conditions. Warn and continue when the database can represent the result. `--suppress-incomplete-upstream-warnings` suppresses only those warnings.

`--force` rebuilds locales at their current version. Do not allow it for a request containing art because a full art rebuild would copy unchanged records into a new version prefix. `run art --complete` is the explicit exception: it processes recorded Windows versions from oldest to current and can backfill a database that already records the current `resVersion`. Do not combine it with `--force` or another unit.

## Preserve upstream and cache semantics

Art comes from the official Windows client CDN. Locale data comes from the unpinned `master` branch of `ArknightsAssets/ArknightsGamedata`; its detected `versionId` becomes the locale `resVersion`.

The default cache is `.cache/` relative to the application working directory (for example, `apps/updateloop/.cache/`); never create it at the repository root. Each art resource retains four independently reusable products:

1. `fetched`: downloaded CDN wrapper
2. `unwrapped`: inner Unity bundle
3. `extracted`: uncomposed Unity exports
4. `rendered`: composition and source PNG objects plus a resource manifest

One run-scoped locale source owns the all-server game-data snapshot. It caches one `.cache/game-data/archive.zip` admitted against every requested locale `versionId`. Locale-specific extracted files remain below `.cache/<resVersion>/game-data/<unit>/extracted/`.

Story groups use `main_story`, `major_event`, `minor_event`, `operator_record`, `integrated_strategies`, `reclamation_algorithm`, and `others`. Keep story-path ownership in `locale/story.py`. Apply ownership in this order: story review, official Integrated Strategies ending catalogs, Reclamation Algorithm, then the remaining-file scan.

Publish only Reclamation Algorithm stories with art references. Claim and exclude Integrated Strategies monthly-squad scripts because they contain no indexed visual-novel art. Reserve Integrated Strategies theme directories for official endings, preventing opening, tutorial, and preload helpers from falling through to `others`. Publish every other remaining non-`[uc]` story text under its source directory; `[uc]` files are descriptions, not stories.

Do not add a generic source-adapter layer or duplicate story ownership logic in callers. `--no-cache` uses the same layout below a run-scoped temporary directory that remains available through image and database upload. Keep rendered PNG objects file-backed instead of retaining the full art set in parent-process memory.

Bound downloads and extraction independently. Each process handles one resource, invokes the extractor with one worker, and exits after one task through `max_tasks_per_child=1`. Preserve the LZ4AK decoder patch, `dyn/` path normalization, and missing-MonoScript fallback when you update UnityPy.

## Keep the read service generation-safe

The service downloads `arkwaifu.sqlite3` before it accepts traffic, requires schema version 2, and opens the file read-only. It polls with `If-None-Match`. A valid replacement becomes the current generation; refresh failures leave the previous generation available.

Each service process owns a private writable database cache directory. Read the [service guide](apps/service/README.md) for deployment configuration and the [application programming interface (API) reference](apps/service/API.md) for the HTTP contract.

## Run the repository checks

Run checks from the repository root with the commands below. Keep ordinary tests deterministic and offline.

```powershell
# Python updater
Push-Location apps/updateloop
uv sync --group dev
uv run ruff check .
uv run pytest
Pop-Location

# Local object storage
Push-Location dev
docker compose up -d minio minio-init
Pop-Location

# OCaml service
Push-Location apps/service
cmd.exe /d /c 'opam exec -- cmd.exe /d /v:on /c "set PATH=C:\opt\msys64\mingw64\bin;!PATH!& dune build @runtest"'
Pop-Location

# React frontend
Push-Location apps/web
bun ci
bun run lint
bun run format:check
bun test
bun run build
Pop-Location
```

Run live CDN and game-data smoke updates manually before deployment. Add focused regression tests for parsers, extraction, image processing, SQLite writes, object publication, and refresh behavior.

Do not commit downloaded bundles, generated PNG objects, local databases, caches, virtual environments, or credentials. Preserve unrelated working-tree changes.
