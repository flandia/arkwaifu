# Arkwaifu updateloop

The Python 3.14 writer downloads upstream game data, extracts Unity assets in a
bounded process pool, and publishes one monolithic SQLite database plus
version-scoped PNGs to S3-compatible storage. It does not connect to PostgreSQL and
does not create staged, validated, active, or release-scoped database records.

## Command

`run` is intentionally the only command:

```console
uv run updateloop run art
uv run updateloop run CN EN
uv run updateloop run
uv run updateloop run CN --force
uv run updateloop run art --no-cache
uv run updateloop run --suppress-incomplete-upstream-warnings
```

With no units, `run` requests `art`, `CN`, `EN`, `JP`, `KR`, and `TW`. Duplicate
arguments are removed. Version detection starts for all requested units
concurrently; if any detection fails, nothing is published. The writer then
compares detected `resVersion` values with `unit_versions` in the downloaded
database. Unchanged units are skipped unless `--force` is set.

Every changed requested unit is materialized concurrently. The complete set is
then applied in one local SQLite transaction and published by one overwrite of
the fixed `arkwaifu.sqlite3` object. The set is all-or-nothing at the database
publication boundary: unlike the former release model, locales do not publish
independently. Any build or SQLite failure prevents all requested changes from
becoming visible and makes the command exit nonzero. `--force` rebuilds the
locales at their current version and requests a full art build when the detected
art version differs from the published one. Forcing art at the
already-published `resVersion` is rejected because its stable PNG keys are
already live. S3 object versioning, not a release table, retains the prior
database generation.

Game data commonly gets ahead of its story text and art files. Missing story
text publishes the story without directive-derived art references. References
to unavailable art remain in locale metadata so they can resolve after a later
art update. An empty story-group or gallery section also warns while remaining
publishable. Use
`--suppress-incomplete-upstream-warnings` to silence only these expected
warnings; other updater warnings remain visible.

## End-to-end publication

1. Detect every requested unit's current upstream `resVersion` concurrently.
2. Pull `arkwaifu.sqlite3` to a temporary directory. If it does not exist,
   initialize schema version 1.
3. Check the schema version, then read the database's unit `resVersion` values.
   No runtime `quick_check`, `integrity_check`, or `foreign_key_check` scan runs.
4. Build every changed requested manifest concurrently and retain rendered PNGs
   as files.
5. Assign PNGs the full location
   `s3://arkwaifu/ART/<resVersion>/<variant>/<category>/<name>.png`. The bucket
   is `arkwaifu`; the object key begins with `ART/`.
6. In one local `BEGIN IMMEDIATE` transaction, apply art first and replace each
   changed locale. SQLite enforces `STRICT`, `CHECK`, primary-key, unique, and
   foreign-key constraints on statements and commit.
7. After that transaction commits successfully, batch-upload every changed PNG
   with bounded concurrency and five-minute public caching.
8. Overwrite `arkwaifu.sqlite3` once with `Cache-Control: no-cache`. The
   database PUT is always last.

There is no separate manifest-validation call, post-write integrity scan, or
stage/validate/activate publication sequence. SQLite's statement and commit
constraints are the local candidate gate; overwriting the object is
publication.

If work for a new `resVersion` fails before the database overwrite, readers
retain the previous database. A partially successful PNG batch can leave
unreachable new-version objects, but no published database points to them.
Same-version art forcing is rejected because overwriting keys referenced by the
current database would violate this boundary. S3 clients may not be able to
distinguish a rejected overwrite from a response lost after the server accepted
it; bucket versioning provides inspection and recovery. Run only one logical
writer per bucket because the fixed-key adapter currently has no compare-and-swap
protection.

`variant` is `composition` for the final consumer-facing art and `source` for a
retained pre-composition character layer. Character `composition` objects
assemble body and face; for `image`, `background`, and `item`, the value means
the validated final PNG rather than a literal multi-layer composition.
`category` is one of `image`, `background`, `item`, and `character`. Source
objects currently use `character` and retain the `body`, `face`, and
`whole_body` roles. They are normalized PNG layers and may already include a
companion alpha merge; they are not the raw encoded Unity texture bytes. `name`
is the logical art identifier escaped as one path segment, not a hash.

## Art execution model

Each selected art resource moves independently through the existing bounded
download-to-process pipeline:

1. `fetched`: `_fetch_bundle` downloads the CDN `.dat` wrapper through a bounded
   download slot.
2. `unwrapped`: `_unzip_resource` extracts the inner Unity bundle from the
   wrapper at its original relative path.
3. `extracted`: `extract_assets` exports the uncomposed Unity asset tree in a
   process-pool worker.
4. `rendered`: `_render_art_resource` scans that tree, writes deterministic
   composition/source PNGs to disk, and writes a per-resource manifest.
5. Lightweight per-resource manifests merge into the final art manifest. PNG
   upload waits until the complete local SQLite transaction has committed.

The four stage names are cache vocabulary, not separately invokable commands.
On a cold miss, `_extract_and_render_art_resource` may run extraction and
rendering in one disposable child while still materializing independent cache
products. Downloads for later resources overlap extraction and rendering for
earlier resources. Locale archive acquisition, extraction, and parsing can run
while the art pipeline is active. The process pool uses
`max_tasks_per_child=1`, recycling each child after one complete resource so
UnityPy, Pillow, and native-library state do not accumulate during a full art
build. Each outer worker calls the resource extractor with `workers=1`, avoiding
a nested process pool. PNG bytes stay in rendered cache files; the parent keeps
only paths and metadata rather than the complete multi-gigabyte art set. After
the SQLite commit, a bounded batch uploads those files before the database PUT.

The database records PNG object keys, byte sizes, dimensions, categories, and
source relationships. PNG objects and public API models intentionally have no
SHA field or per-PNG hash metadata.

## Upstream cache

By default, `run` creates `.cache/` in its current working directory. It
validates and reuses downloaded art wrappers, unwrapped Unity bundles,
uncomposed assets, rendered PNGs, one all-server game-data archive, and selected
locale files. Cache files are written atomically; incomplete stage directories
are never treated as complete.
The commands above assume `apps/updateloop` as the working directory. To place
the cache at the repository root instead, run
`uv run --project apps/updateloop updateloop run` from that root.

Art entries are keyed by the percent-encoded full upstream resource name and
the upstream-provided MD5, not by a locally generated SHA. Each entry retains
four independent stage products:

```text
.cache/<resVersion>/art/
|-- hot_update_list.json
`-- resources/
    `-- <percent-encoded-upstream-resource-name>/
        `-- <upstream-md5>/
            |-- fetched/
            |   `-- wrapper.dat
            |-- unwrapped/
            |   `-- <original-relative-bundle-path>
            |-- extracted/
            |   `-- ... uncomposed Unity exports ...
            `-- rendered/
                |-- processed/
                |   `-- ... final and original-source PNGs ...
                `-- manifest.json
```

Each stage consumes only the preceding stage and has its own atomic completion
marker containing its recipe and the upstream resource MD5. This permits
independent tests and narrow rebuilds: rendering can reuse uncomposed
extraction, extraction can reuse the inner bundle, and unwrapping can reuse the
downloaded wrapper. Incomplete stage directories are never cache hits.
Completed entries are retained; abandoned temporary writes may be cleaned
separately.

Locales share `.cache/game-data/archive.zip`, which is admitted against every
requested locale's detected `versionId` before reuse. Their independently
reusable extracted files remain under
`.cache/<resVersion>/game-data/<unit>/extracted/`. One run-scoped locale source
owns the archive acquisition and releases its temporary state when the run
finishes; archive bytes are not retained in memory per locale.

Use `--no-cache` for an isolated run. It uses the identical staged directory
shape under a run-scoped temporary root, but neither reads nor writes `.cache`.
That root remains alive through the SQLite transaction, PNG batch, and final
database PUT so file-backed artifacts cannot disappear during upload. Upstream
version detection is always live so the cache cannot hide a newly published
version.

## Upstream sources

- Art version and bundles come from the official Windows client CDN:
  `https://ak-conf.hypergryph.com/config/prod/official/Windows/version` and
  `https://ak.hycdn.cn/assetbundle/official/Windows/assets`.
- CN, EN, JP, KR, and TW stories/gallery metadata come from the current
  `master` branch of `ArknightsAssets/ArknightsGamedata`.

For each locale, detection reads `hot_update_list.json` from `master` and uses
only its non-empty `versionId` as the `resVersion`. The builder downloads a
`master` snapshot rather than pinning a commit and rejects it if its embedded
locale version differs from the detected value. This catches a branch update
that races detection and download. The manifest, cache identity, and database
persist only the `resVersion`: they do not store the repository URL, branch,
commit SHA, or any other repository provenance.

The parser retains the tolerant current-CG behavior introduced by Go v1.9.4.
ZIP members are checked for absolute paths and parent traversal before selected
locale files are extracted.

The art CDN locations remain configurable. Set `ARKWAIFU_ART_VERSION_URL` and
`ARKWAIFU_ART_ASSET_BASE_URL` together to select another official client
platform or a compatible mirror. After changing to a platform with a different
`resVersion`, run:

```console
uv run updateloop run art --force --no-cache
```

The uncached forced run avoids reusing platform-agnostic cache identities and
builds every resource for the new version. If both platforms report the same
`resVersion`, use a separate bucket: the chosen stable key scheme has no platform
or generation component and therefore cannot switch that content atomically.

## Environment

`../../infra/dev.env.example` contains the local MinIO endpoint and development
credentials used by `infra/compose.yaml`. It is an opt-in example and is not
loaded automatically. From `apps/updateloop`, pass it explicitly when running
against that MinIO instance:

```console
uv run --env-file ../../infra/dev.env.example updateloop run
```

Required:

- `ARKWAIFU_S3_BUCKET`
- `ARKWAIFU_S3_ACCESS_KEY_ID`
- `ARKWAIFU_S3_SECRET_ACCESS_KEY`

Optional:

- `ARKWAIFU_S3_ENDPOINT_URL` — custom endpoint such as MinIO.
- `ARKWAIFU_S3_REGION` — defaults to `us-east-1`.
- `ARKWAIFU_S3_PATH_STYLE` — defaults to `false`; enable for local MinIO.
- `ARKWAIFU_ART_VERSION_URL` — overrides the official Windows version endpoint.
- `ARKWAIFU_ART_ASSET_BASE_URL` — overrides the official Windows asset root.
- `ARKWAIFU_DOWNLOAD_WORKERS` — maximum concurrent art bundle acquisitions;
  defaults to `16`.
- `ARKWAIFU_EXTRACTION_WORKERS` — maximum concurrent per-resource
  extraction/composition processes. When unset, Python chooses the process-pool
  size from available CPUs. Size this for both CPU and peak memory.
- `ARKWAIFU_GITHUB_API_URL` — defaults to `https://api.github.com`.
- `ARKWAIFU_GITHUB_TOKEN` — recommended in production to avoid anonymous API
  rate limits.

## Database guarantees and costs

- Art deltas overlay the existing art rows, retaining assets absent from later
  hot-update lists. Each changed locale is a complete replacement.
- All requested changed units enter one SQLite transaction and one database
  overwrite.
- SQLite enforces schema and foreign-key constraints on statements and commit;
  no runtime integrity scan follows the writes.
- PNGs batch-upload only after the local transaction commits, and all required
  uploads finish before the final database PUT.
- Original character layers and composition images are both addressable.
- S3 bucket versioning retains overwritten database generations and supplies the
  rollback path.
- The fixed-key writer is single-writer by deployment convention; it has no
  lock or compare-and-swap token.

An offline run of the production schema with all five locales produced a raw
234 MiB database; the complete database with art metadata is larger. Because the
object is monolithic, even a small locale-only change uploads the whole file,
and each service replica downloads the whole changed file. SQLite local bulk
inserts replace the old database staging path, so PostgreSQL `COPY`
optimization is moot.

## Development

Install and run checks:

```console
uv sync --group dev
uv run ruff check .
uv run pytest
```

Docker-backed database tests require only MinIO from `infra/compose.yaml`:

```console
docker compose -f ../../infra/compose.yaml up -d minio minio-init
$env:ARKWAIFU_INTEGRATION = "1"
uv run pytest tests/integration/test_database_minio.py
```

Ordinary tests are deterministic and offline. Live CDN/game-data smoke updates
remain manual deployment checks. The current SQLite and ArknightsAssets path
still requires a live end-to-end smoke run before its first deployment.

A first full art update is storage-intensive. Historical cache measurements
were about 10–12 GiB; reserve at least 15 GiB for the project cache. Plan object
storage independently for version-scoped PNG objects and retained S3 database
versions.
