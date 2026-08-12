# Arkwaifu updateloop

The Python 3.14 writer downloads upstream game data, extracts Unity assets in a
bounded process pool, and publishes one monolithic SQLite database plus PNGs
under art-version prefixes in S3-compatible storage. It does not connect to
PostgreSQL and does not create staged, validated, active, or release-scoped
database records.

## Command

`run` is intentionally the only command:

```console
uv run updateloop run art
uv run updateloop run art --complete
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
becoming visible and makes the command exit nonzero. `--force` rebuilds selected
locales at their current versions. It is rejected when the request includes art,
because a forced full build would copy unchanged art into a new version prefix.
S3 object versioning, not a release table, retains the prior database generation.

`run art --complete` is an explicit historical backfill. It obtains the
recorded Windows `resVersion` sequence from oldest through the currently
detected version, builds the first version in full, and then builds only each
adjacent version's changed bundles. Every resulting record retains the version
which contributed it. Records accumulate across that sequence; the newest
occurrence of `(category, art_id)` or `source_art_id` wins, while art that
disappeared from later manifests remains available through its older object
key. The cumulative manifest records the current `resVersion` and enters the
ordinary transaction, PNG batch, and single final database PUT once. A listed
CDN version that cannot be read fails the run. `--complete` requires `art` to be
the sole unit and cannot be combined with `--force`. Unlike force, it is allowed
to backfill a database already recording the current art version.

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
   initialize schema version 2. An existing database must already declare
   version 2; recreate development databases made with an earlier schema.
3. Check the schema version, then read the database's unit `resVersion` values.
   Publication runs no `quick_check`, `integrity_check`, or post-write
   `foreign_key_check`.
4. Build every changed requested manifest concurrently and retain rendered PNGs
   as files.
5. Assign PNGs the full location
   `s3://arkwaifu/ART/<resVersion>/<variant>/<category>/<name>.png`.
   The bucket is `arkwaifu`; the object key begins with `ART/`. Each record uses
   the art version which produced that PNG, which can be older than the current
   art unit version after a cumulative build.
6. In one local `BEGIN IMMEDIATE` transaction, apply art first and replace each
   changed locale. SQLite enforces `STRICT`, `CHECK`, primary-key, unique, and
   foreign-key constraints on statements and commit.
7. After that transaction commits successfully, batch-upload every changed PNG
   with bounded concurrency and
   `Cache-Control: public, max-age=31536000, immutable`.
8. Overwrite `arkwaifu.sqlite3` once with `Cache-Control: no-cache`. The
   database PUT is always last.

There is no separate manifest-validation call, post-write integrity scan, or
stage/validate/activate publication sequence. SQLite's statement and commit
constraints are the local candidate gate; overwriting the object is
publication.

If work for a new `resVersion` fails before the database overwrite, readers
retain the previous database. A partially successful PNG batch leaves objects
under an as-yet-unreferenced version prefix, but does not change the keys used
by that database. The first version of a complete build is full. A later
version processes selected changed bundles, and the cumulative merge keeps the
newest record for each logical identity. The final manifest uploads only those
winners, each under the version which contributed it; superseded intermediate
revisions are not uploaded. Rows supplied only by unchanged bundles retain
their earlier object keys instead of being copied into the new prefix.
Same-version art forcing remains rejected because one version namespace has one
meaning. Bucket versioning provides inspection and recovery for the fixed
database object. Run only one logical writer per bucket because the database
adapter currently has no compare-and-swap protection.

Version prefixes are retained permanently by updater code, including prefixes
or individual PNGs left unreachable by a failed or superseded update. They form
a durable record of the art versions which contributed PNGs; a version with no
selected art output needs no empty marker. The updater does not list those
prefixes to discover history: complete mode still obtains its candidate version
sequence upstream and validates every selected bundle against the official CDN.

PNG keys are treated as create-only. Before uploading, the S3 adapter uses
`HEAD` to accept an object whose byte size, `image/png` content type, and
immutable cache policy already match. A mismatch fails the run instead of
replacing that object. There is deliberately no content hash, so this is an
object-metadata check rather than byte-for-byte content verification.

The selected object variant is `composition` for final consumer-facing art and
`source` for a retained pre-composition character layer. Character
`composition` objects assemble body and face; for `image`, `background`, and
`item`, the value means the validated final PNG rather than a literal
multi-layer composition.
`category` is one of `image`, `background`, `item`, and `character`. Source
objects currently use `character` and retain the `body`, `face`, and
`whole_body` roles. They are normalized PNG layers and may already include a
companion alpha merge; they are not the raw encoded Unity texture bytes. `name`
is the logical art identifier escaped as one path segment, not a hash. Final
art is identified by both `category` and `name`; equal names in different
categories are independent rows and objects. The leading `resVersion` belongs
to the individual record, so a database whose art unit is at version B may
legitimately refer to an unchanged object introduced under version A.

### Manual fallback art

Uploading a fallback PNG by itself does not make it visible: the service reads
the selected object key from SQLite. Upload the PNG to
`ART/<contributing-resVersion>/composition/<category>/<escaped-id>.png`, pull
`arkwaifu.sqlite3`, and insert or update the matching `arts` row identified by
`(category, art_id)`. Record the uploaded key, byte size, width, and height.

```sql
BEGIN IMMEDIATE;
INSERT INTO arts
    (category, art_id, object_key, byte_size, width, height)
VALUES
    (:category, :art_id, :object_key, :byte_size, :width, :height)
ON CONFLICT (category, art_id) DO UPDATE SET
    object_key = excluded.object_key,
    byte_size = excluded.byte_size,
    width = excluded.width,
    height = excluded.height;
COMMIT;
```

Optional retained fallback layers go to
`ART/<contributing-resVersion>/source/character/<escaped-source-id>.png`. Insert
or update each `source_arts` row with its character role and sprite variant,
object metadata, and stable source ID. For a character composition, replace
that art's `art_source_refs` rows using
`category = 'character'`, the composition `art_id`, zero-based `position`, and
the source IDs in composition order. A final composition remains usable with
no source rows if the original layers are unavailable. Make all SQLite edits
in one transaction, then upload the modified `arkwaifu.sqlite3` last. Do not
change the art unit's current `resVersion` merely for this manual compensation;
the object prefix identifies the upstream version which contributed the file.

ArknightsAssets2 publishes complete Android portraits, not the sprite-hub JSON
and separate body/face layers consumed by the Windows compositor. For that
fallback source, store the portrait itself as one `whole_body` source, use
`<base>:whole_body:<body>:<face>` as its source ID and `<body>:<face>` as its
sprite variant, and point the composition at that one source. The fallback
source and composition objects then intentionally contain the same PNG.

This selected-object model retains one object for each logical row; it does not
distinguish Windows and Android copies. Fallback art is used only when the
official Windows history cannot provide that identity. Thumbnail and
Real-ESRGAN variants remain unimplemented.

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

Art work emits structured JSON action records for `list`, `version`, `fetch`,
`unzip`, `extract`, `compose`, `apply`, `upload`, and `publish`. Each record
carries its `res_version`, status, elapsed milliseconds when measurable, and a
stable `current`/`total` ordinal for complete-mode versions or concurrent
resource work. A successful action emits one terminal record with
`status = "done"`; cache reuse emits `status = "cached"`, and failures emit
`status = "failed"`. The combined extraction/composition child reports exact
terminal stages without adding another worker or cross-process progress channel.

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

When `story_review_table.json` references text absent from the current branch,
the builder searches that locale directory's GitHub history newest-first and
uses the latest exact-path copy it can find. This lookup is best-effort and
bounded; a missing or failed historical lookup keeps the story metadata,
emits the usual incomplete-upstream warning, and continues without directives.
Recovered text is cached with the extracted locale data. Repository and commit
identifiers are never written to the database. Because that cache is keyed by
the game `resVersion`, a repository-only backfill at the same version is picked
up on a `--no-cache` run (or after removing that locale's extracted cache), not
by `--force` alone.

The Windows CDN locations remain configurable. Set
`ARKWAIFU_ART_VERSION_URL` and `ARKWAIFU_ART_ASSET_BASE_URL` together for a
compatible Windows mirror. Android extraction is not part of the automatic
pipeline; use the manual fallback procedure above for assets absent from
Windows.

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

- Art deltas contain every output of selected changed bundles and overlay
  existing rows by `(category, art_id)`. Unchanged rows retain their older
  versioned keys, including assets absent from later hot-update lists. Each
  changed locale is a complete replacement.
- All requested changed units enter one SQLite transaction and one database
  overwrite.
- SQLite enforces schema and foreign-key constraints on statements and commit;
  no runtime integrity scan follows the writes.
- PNGs batch-upload only after the local transaction commits, and all required
  create-or-verify operations finish before the final database PUT.
- Original character layers and composition images are both addressable.
- Historical, immutable art prefixes are retained. S3 bucket versioning retains
  overwritten database generations and supplies the database rollback path.
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
storage independently for retained art-version prefixes and database object
versions.
