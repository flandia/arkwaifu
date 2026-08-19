# Understand publication and storage

The updater converts selected upstream data into one SQLite database, immutable PNG, audio, and video objects, and replaceable WebP thumbnails. This reference explains its transaction boundary, object contracts, cache, and resource limits.

## Follow the end-to-end publication sequence

The updater completes these steps in order:

1. Detect every requested unit’s current upstream `resVersion` concurrently
2. When `--archive` is enabled, archive every missing historical CN/Windows wrapper and publish each version manifest last
3. Download `arkwaifu.sqlite3` to a temporary directory, or create schema version 2 when the object does not exist
4. Validate the schema version, read each published unit version, and restore the additive `story_narrative_image_references_by_asset (locale, category, asset_id)` index when necessary
5. Build every changed manifest concurrently and retain rendered PNGs, audio, and videos as files
6. Assign Narrative Image and Material keys below `ART/` and dedicated Presentation visual keys below `SCORE/`
7. Apply artwork changes first, then replace each changed locale in one local `BEGIN IMMEDIATE` transaction
8. Upload every referenced immutable PNG, audio, and video with bounded concurrency
9. Generate and upload every derived thumbnail
10. Overwrite `arkwaifu.sqlite3` with `Cache-Control: no-cache`

SQLite enforces strict tables, checks, primary keys, unique keys, and foreign keys during statements and commit. Publication does not run `quick_check`, `integrity_check`, or a post-write `foreign_key_check`.

An existing database must declare schema version 2 and match the current table shape. Recreate a development database after a schema or constraint change. Restoring the additive read index is the only in-place repair.

## Preserve visibility during failures

The database overwrite makes prepared metadata visible. Before that overwrite, readers continue to use the previous database.

Failure behavior depends on the completed work:

- A preparation or SQLite failure exposes none of the requested database changes
- A partial asset-bundle archive can leave immutable wrappers without a completion manifest; the database remains unchanged
- A partial PNG, audio, or video batch may leave unreferenced immutable objects under a new version prefix
- A partial thumbnail batch may replace thumbnails referenced by the previous database
- A database upload failure leaves the previous object current
- S3 bucket versioning preserves overwritten database generations for inspection and recovery

Run one logical writer per bucket. The fixed-key publication adapter has no compare-and-swap protection.

## Identify Narrative Image and Material objects

Each final image or material object uses this key structure:

```text
ART/<contributing-resVersion>/<variant>/<category>/<escaped-id>.png
```

The `variant` identifies the stored resource kind:

- `composition`: final consumer-facing Narrative Image Asset
- `source`: a retained character material or Gallery panel material

Character images combine body and face materials. Panel-based Gallery images combine ordered illustration or background materials. For every category, `composition` means the validated final PNG.

The `category` is `illustration`, `background`, `item`, or `character`. Character Materials use `character` and retain a `body`, `face`, or `whole_body` role. Panel Materials preserve the final image's category. The pair `(category, asset_id)` identifies a Material Asset within the `material` namespace. The escaped identifier is one path segment, not a content hash; an ID containing `/` is escaped as that one segment.

The database identifies every asset by namespace, category, and identifier. Equal category and identifier pairs in different namespaces remain independent rows and objects.

## Identify Score objects

Dedicated Score images and background videos use separate immutable key spaces:

```text
SCORE/<contributing-resVersion>/<asset-kind>/<escaped-id>.png
SCORE/<contributing-resVersion>/video/<escaped-id>.webm
```

Image categories are `icon`, `logo`, `background`, `key-visual`, `title`, `decoration`, `retro-background`, and `divider`. Score metadata references `(category, asset_id)` so an equal identifier in two categories remains unambiguous.

The Windows client supplies CRI USM containers for the animated Main Theme backgrounds. The updater parses their VP9 payload, writes deterministic IVF, and losslessly remuxes it to a muted WebM through PyAV. It validates dimensions, frame rate, and packet count before publication. PNG and WebM Score keys are create-only and use the same immutable cache policy as ordinary PNGs.

## Apply incremental and complete artwork updates

An incremental asset manifest overlays Narrative Images, Materials, Presentation images, and Presentation videos from changed bundles on the published database. Unchanged rows retain their existing object keys, including objects introduced under older versions.

A complete update processes the recorded Windows version sequence from oldest to newest. It builds the first version in full, compares each later version with its immediate predecessor, and retains the newest occurrence of each namespace-qualified `(category, asset_id)`.

Complete mode preserves artwork that disappears from later manifests. It uploads only final winners, using the version that contributed each winner. A version with no selected output needs no empty marker.

The updater never discovers history by listing object prefixes. It obtains candidate versions upstream and validates each selected bundle against the official content-delivery network (CDN).

## Archive original asset-bundle wrappers

`--archive` stores the exact `.dat` ZIP wrappers from the official CN Windows CDN in a dedicated S3-compatible bucket. It preserves companion files carried inside a wrapper and does not replace the normal artwork extraction pipeline.

Archive keys have this structure:

```text
CN/Windows/<resVersion>/<flat-CDN-filename>.dat
CN/Windows/<resVersion>/hot_update_list.json
```

On an empty archive, the updater reads the same ordered Windows history used by `--complete`. It uploads every wrapper in the oldest version, then uploads only resources whose `(name, md5)` pair differs from the immediate predecessor. This records bundles that appear temporarily and disappear from later manifests.

On later runs, the newest archived manifest in that ordered history is the baseline. The updater resumes with every subsequent recorded version, so skipping `--archive` for one or more ordinary updates does not lose intermediate changes. `--complete --archive` deliberately uses one history sequence for both operations.

For each version, wrapper downloads and uploads are bounded by `ARKWAIFU_DOWNLOAD_WORKERS`. The updater uploads `hot_update_list.json` only after every selected wrapper succeeds. That manifest is the completion marker and becomes the baseline for a later run. A failed batch can leave reusable wrapper objects but cannot mark the version complete or publish a new database generation.

Wrappers and manifests are immutable and create-only. Existing objects are accepted only when their byte size, content type, immutable cache policy, and SHA-256 metadata match. Wrapper metadata also records the digest string from the official manifest. Most resources provide a full inner-bundle MD5; the exceptional `anon/*.bin` entries provide a four-digit value and rely on successful ZIP member and CRC validation instead. Conflicts fail the run.

## Enforce immutable object contracts

PNG, audio, and video keys are immutable and create-only. Before upload, the S3 adapter uses `HEAD` to accept an existing object only when byte size, content type, and immutable cache policy match. PNGs use `image/png`; media uses the source-derived audio or video content type.

The metadata check does not compare image bytes. A metadata mismatch fails the run instead of replacing the object.

Immutable uploads use this cache policy:

```text
Cache-Control: public, max-age=31536000, immutable
```

The updater fits each final artwork winner within 512 by 512 pixels without cropping or upscaling. It encodes the result as WebP at quality 75 and stores it under this mutable key:

```text
ART/<resVersion>/thumbnail/<category>/<escaped-id>.webp
```

Thumbnail uploads set `image/webp` and use the object store’s cache defaults. Material Assets do not receive thumbnails.

## Process artwork with bounded resources

Each selected artwork resource passes through four cache stages. These stage names describe cache products, not CLI commands.

The stages run in this order:

1. `fetched`: download the CDN `.dat` wrapper through a bounded download slot
2. `unwrapped`: extract the inner Unity bundle at its original relative path
3. `extracted`: export the Unity asset tree in a process-pool worker
4. `rendered`: render Narrative Image and Material PNGs, remux Presentation videos, then write a per-resource manifest

Downloads for later resources can overlap extraction and rendering for earlier resources. Locale acquisition and parsing can also run while the artwork pipeline is active.

The process pool uses `max_tasks_per_child=1`. Each outer worker runs the resource extractor with `workers=1`, which avoids a nested process pool. The parent retains paths and metadata instead of all PNG bytes.

Structured JSON logs use actions such as `list`, `version`, `fetch`, `archive`, `unzip`, `extract`, `compose`, `apply`, `thumbnail`, `upload`, and `publish`. Each record identifies its `res_version` and status. Measurable work also reports elapsed milliseconds, and concurrent or complete-history work reports a stable `current` and `total` ordinal.

A terminal record uses `done`, a cache hit uses `cached`, and a failure uses `failed`.

## Reuse validated cache entries

The updater writes cache entries atomically and validates them before reuse. It replaces corrupted files or directories instead of treating them as cache hits.

Artwork cache entries use the percent-encoded upstream resource name and published MD5 value:

```text
.cache/<resVersion>/artwork/
|-- hot_update_list.json
`-- resources/
    `-- <percent-encoded-resource-name>/
        `-- <upstream-md5>/
            |-- fetched/
            |   `-- wrapper.dat
            |-- unwrapped/
            |   `-- <relative-bundle-path>
            |-- extracted/
            |   `-- <unity-exports>
            `-- rendered/
                |-- processed/
                |   `-- <png-audio-and-video-files>
                `-- manifest.json
```

Each stage depends only on the previous stage and records a format fingerprint. Completed entries remain until an operator removes them.

Locales share `.cache/game-data/archive.zip`. The updater validates the archive against every requested locale version before reuse. Extracted locale data remains under `.cache/<resVersion>/game-data/<unit>/extracted/`.

## Account for database and storage costs

The updater always uploads the complete SQLite object, even for a small locale change. Each service replica then downloads that complete object.

An offline schema run with all five locales produced a 234 MiB database before complete artwork metadata. Complete artwork builds also retain historical image prefixes and overwritten database versions, so plan object storage separately from local cache capacity.
