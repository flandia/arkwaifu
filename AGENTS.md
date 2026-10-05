# Work in the Arkwaifu repository

## Scope and instruction priority

Follow system and developer instructions and the user's explicit task instructions. Within project guidance, applicable repository contracts take precedence over generic skill advice. More-specific repository instructions govern their own directories.

Skills guide implementation within the task's scope. Adapt bundled examples and fetched guidelines to this project and follow the user's requested output. Skill instructions do not independently authorize commits or publication.

Keep third-party skill packages unmodified. Put project-specific guidance in repository instructions and manage skill selection by adding or removing whole skills.

Use Ponytail to find the simplest clear solution that satisfies the complete request. Preserve behavior during refactoring and avoid unrelated cleanup. Apply relevant composition, performance, and transition patterns to the affected code and user flows. Reuse the existing transition/router integration and preserve navigation semantics and reduced-motion behavior. Choose dependencies and API changes for the task's needs, not merely to match a skill example.

## Application boundaries and authoritative references

- `apps/updateloop/`: Python 3.14 archive writer; owns upstream acquisition, extraction, rendering, schemas, and publication.
- `apps/service/`: OCaml 5.5 Dream service; reads published SQLite generations and serves metadata.
- `apps/web/`: React 19, React Router, and Vite frontend; read-only. Preserve the installed framework and dependency pins when applying generic React skills.

The Arknights archive uses `arkwaifu.sqlite3` and schema version 2. These source, identity, and version rules describe Arknights. If a feature checkout contains a separate product, follow that product's own schema and documentation instead of applying Arknights-specific rules automatically.

Before changing a contract, read its owning reference and keep the affected writer, service, frontend, and documentation consistent:

| Contract | Owning reference |
| --- | --- |
| Arknights terminology and asset identity | [GLOSSARY.md](GLOSSARY.md) |
| Arknights SQLite schema | `apps/updateloop/src/arkwaifu.sql` |
| Publication, object keys, caching, resource limits | [Publication and storage](apps/updateloop/docs/publication.md) |
| Source provenance and story ownership | [Upstream data](apps/updateloop/docs/upstream-data.md) |
| Updater commands and configuration | [Updater guide](apps/updateloop/README.md) |
| Service configuration and refresh lifecycle | [Service guide](apps/service/README.md) |
| HTTP contract | [API reference](apps/service/API.md) |
| Frontend setup | [Web guide](apps/web/README.md) |
| Local object storage | `dev/compose.yaml` |

The Go v1 API and global server-side search remain outside scope. Use v1.9.4 only as a behavioral reference for unclear frontend details; do not copy its API or database format without a current requirement.

## Local development

Run application commands from their application directory and Docker Compose from `dev/`. Never create a repository-root `.cache/`. Keep machine-specific tasks in ignored `.vscode/tasks.json`.

For the local runtime, Docker runs only MinIO. From `dev/`, start it with `docker compose up -d minio minio-init`; run the service and Vite on the host. The local MinIO `arkwaifu` bucket is the sole development archive. Do not create a second filesystem archive or repository-owned static runtime server. MinIO must serve object metadata, conditional requests, and media byte ranges. Local bucket versioning remains suspended.

For the Arknights preview, use `ARKWAIFU_DATABASE_URL=http://127.0.0.1:59000/arkwaifu/arkwaifu.sqlite3`, `ARKWAIFU_OBJECT_BASE_URL=http://127.0.0.1:59000/arkwaifu`, service port `5174`, and `VITE_API_BASE_URL=http://127.0.0.1:5174`. Follow the service guide for the complete launch commands and process-private cache directory.

The updater's ignored `.env` targets local MinIO. Keep production credentials in ignored `.env.prod` and select them explicitly with `uv run --env-file .env.prod ...`.

## Publication and identity invariants

Publication uses a fixed database object, without PostgreSQL, release tables, staged rows, or activation pointers.

- Run one logical writer per bucket; publication has no lock or compare-and-swap protection.
- For Arknights, detect requested versions concurrently, complete any requested wrapper archival, pull or initialize the database, prepare changed units concurrently, and apply their changes in one local SQLite transaction. Upload required immutable media and derived thumbnails with bounded concurrency, then upload `arkwaifu.sqlite3` last. The database overwrite publishes metadata.
- Immutable composition/source PNG and original media keys are create-only. Accept existing objects only when the metadata required by the publication contract matches; fail on conflicts. Derived WebP thumbnails are replaceable and use store/CDN cache defaults.
- A failed media batch may leave unreachable objects or partially replaced thumbnails, but must not publish new database metadata. Retain historical prefixes and unreachable immutable objects. Production bucket versioning supplies database rollback; local MinIO is the deliberate exception.
- Arknights asset identity is `(namespace, category, id)`. Keep narrative, material, and presentation identities distinct. Preserve logical IDs and existing object keys for unchanged records; use the contributing art `resVersion` in versioned keys. Do not encode a compensating asset's source platform into its variant or key. Follow the publication reference for `ART/`, `SCORE/`, escaping, and thumbnail layouts.
- Persist Arknights upstream `resVersion` values, not repository URLs or commit identifiers.
- Arknights requires schema version 2 and the current schema shape. Beta schema changes have no migration or compatibility layer: recreate the development database when necessary. The only in-place repair is the additive `story_narrative_image_references_by_asset (locale, category, asset_id)` index. Use SQLite statement/commit constraints and schema probes; do not add separate `quick_check`, `integrity_check`, or post-write `foreign_key_check` operations.

## Arknights updater constraints

- Locale units may be rebuilt in full. For a breaking artwork change, process only the changed resource diff manually unless the user explicitly requests a full artwork rebuild. Runbook examples of complete mode do not independently authorize one.
- `--force` is locale-only. `run artwork --complete` processes recorded Windows history from oldest to current and may backfill the current version; never combine it with `--force` or another unit. Preserve unchanged historical keys and process only changed bundles after the first version.
- Keep one-off recovery behavior out of the supported CLI. Remove temporary recovery scripts and task-specific support after successful recovery when the remote has caught up.
- Warn and continue for representable incomplete upstream data. `--suppress-incomplete-upstream-warnings` suppresses only those warnings.
- Keep story-path ownership in `locale/story.py`; follow the upstream-data reference for classification order and exclusions. Do not duplicate ownership logic in callers or add a generic source-adapter layer.
- Preserve the four independently reusable cache stages: `fetched`, `unwrapped`, `extracted`, and `rendered`. Use one run-scoped, version-validated locale snapshot. `--no-cache` uses the same layout in a temporary directory retained through publication.
- Keep rendered objects file-backed. Bound downloads and extraction separately. Each extraction process handles one resource with one extractor worker and `max_tasks_per_child=1`. Preserve the LZ4AK decoder patch, `dyn/` normalization, and missing-MonoScript fallback when updating UnityPy.

## Native service

Use the project-local OCaml 5.5.0 opam switch and the dependencies in `apps/service/arkwaifu_service.opam`. Run every native build, test, and service through `opam exec`. On Windows, prepend `C:\opt\msys64\mingw64\bin` after entering the opam environment so modern SQLite and compatible OpenSSL DLLs are loaded.

For initial setup, run once from `apps/service/`:

```powershell
opam switch create . ocaml-base-compiler.5.5.0 --no-install
opam install . --deps-only --with-test
```

Verify the switch with `opam exec -- ocaml --version` and `opam exec -- dune --version`. If opam itself cannot start, repair its installation or Windows shim first.

Do not run the built executable or switch's `dune.exe` directly. Do not use `ucrt64`, LibreOffice DLLs, or DLL copies beside the executable. A `STRICT` schema error can indicate the old opam SQLite runtime; fix launch order rather than changing the schema.

Each service process owns a private writable database cache. Download and validate the selected product's database before accepting traffic; open it read-only. Poll with `If-None-Match`, switch only to a valid replacement, and keep the previous generation available after refresh failure.

## Verification

Use the existing test frameworks. Add focused regression coverage for changed parser, extraction, rendering, SQLite, publication, or refresh behavior. Keep ordinary tests deterministic and offline. Run the affected applications' required checks; exercise both sides of changed shared contracts. Repeat or broaden checks only for a new change, failure, or unresolved concern.

Run these commands in the indicated working directory:

| Working directory | Commands |
| --- | --- |
| `apps/updateloop/` | `uv sync --group dev`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run pytest` |
| `apps/service/` | The native Windows command below |
| `apps/web/` | `bun ci`; `bun run lint`; `bun run format:check`; `bun test`; `bun run build` |

```powershell
cmd.exe /d /c 'opam exec -- cmd.exe /d /v:on /c "set PATH=C:\opt\msys64\mingw64\bin;!PATH!& dune build @runtest"'
```

MinIO startup is preview/integration setup, not an offline unit-test prerequisite. Verify changed user-visible behavior in the running application. Run live CDN and game-data smoke updates manually before deployment.

Preserve unrelated working-tree changes. Do not commit credentials, downloaded bundles, generated media, local databases, caches, or virtual environments.
