# Understand publication and storage

The updater converts selected upstream data into one SQLite database, immutable PNG objects, and replaceable WebP thumbnails. This reference explains its transaction boundary, object contracts, cache, and resource limits.

## Follow the end-to-end publication sequence

The updater completes these steps in order:

1. Detect every requested unit’s current upstream `resVersion` concurrently
2. Download `arkwaifu.sqlite3` to a temporary directory, or create schema version 2 when the object does not exist
3. Validate the schema version, read each published unit version, and restore the additive `story_art_references_by_art (locale, art_id)` index when necessary
4. Build every changed manifest concurrently and retain rendered PNGs as files
5. Assign each image an object key under `ART/<resVersion>/<variant>/<category>/`
6. Apply art changes first, then replace each changed locale in one local `BEGIN IMMEDIATE` transaction
7. Upload every referenced PNG with bounded concurrency
8. Generate and upload every derived thumbnail
9. Overwrite `arkwaifu.sqlite3` with `Cache-Control: no-cache`

SQLite enforces strict tables, checks, primary keys, unique keys, and foreign keys during statements and commit. Publication does not run `quick_check`, `integrity_check`, or a post-write `foreign_key_check`.

An existing database must declare schema version 2 and match the current table shape. Recreate a development database after a schema or constraint change. Restoring the additive read index is the only in-place repair.

## Preserve visibility during failures

The database overwrite makes prepared metadata visible. Before that overwrite, readers continue to use the previous database.

Failure behavior depends on the completed work:

- A preparation or SQLite failure exposes none of the requested database changes
- A partial PNG batch may leave unreferenced immutable objects under a new version prefix
- A partial thumbnail batch may replace thumbnails referenced by the previous database
- A database upload failure leaves the previous object current
- S3 bucket versioning preserves overwritten database generations for inspection and recovery

Run one logical writer per bucket. The fixed-key publication adapter has no compare-and-swap protection.

## Identify art objects

Each art object uses this key structure:

```text
ART/<contributing-resVersion>/<variant>/<category>/<escaped-id>.png
```

The `variant` identifies the stored representation:

- `composition`: final consumer-facing art
- `source`: a retained character layer before composition

Character compositions combine body and face layers. For `image`, `background`, and `item`, `composition` means the validated final PNG.

The `category` is `image`, `background`, `item`, or `character`. Source objects use `character` and retain a `body`, `face`, or `whole_body` role. The escaped identifier is one path segment, not a content hash.

The database identifies final art by both category and identifier. Equal identifiers in different categories remain independent rows and objects.

## Apply incremental and complete art updates

An incremental art manifest overlays records from changed bundles on the published database. Unchanged rows retain their existing object keys, including objects introduced under older versions.

A complete update processes the recorded Windows version sequence from oldest to newest. It builds the first version in full, compares each later version with its immediate predecessor, and retains the newest occurrence of each `(category, art_id)` or `source_art_id`.

Complete mode preserves art that disappears from later manifests. It uploads only final winners, using the version that contributed each winner. A version with no selected output needs no empty marker.

The updater never discovers history by listing object prefixes. It obtains candidate versions upstream and validates each selected bundle against the official content-delivery network (CDN).

## Enforce image object contracts

PNG keys are immutable and create-only. Before upload, the S3 adapter uses `HEAD` to accept an existing object only when byte size, `image/png` content type, and immutable cache policy match.

The metadata check does not compare image bytes. A metadata mismatch fails the run instead of replacing the object.

PNG uploads use this cache policy:

```text
Cache-Control: public, max-age=31536000, immutable
```

The updater fits each final art winner within 512 by 512 pixels without cropping or upscaling. It encodes the result as WebP at quality 75 and stores it under this mutable key:

```text
ART/<resVersion>/thumbnail/<category>/<escaped-id>.webp
```

Thumbnail uploads set `image/webp` and use the object store’s cache defaults. Source layers do not receive thumbnails.

## Process art with bounded resources

Each selected art resource passes through four cache stages. These stage names describe cache products, not CLI commands.

The stages run in this order:

1. `fetched`: download the CDN `.dat` wrapper through a bounded download slot
2. `unwrapped`: extract the inner Unity bundle at its original relative path
3. `extracted`: export the Unity asset tree in a process-pool worker
4. `rendered`: compose final and source PNGs, then write a per-resource manifest

Downloads for later resources can overlap extraction and rendering for earlier resources. Locale acquisition and parsing can also run while the art pipeline is active.

The process pool uses `max_tasks_per_child=1`. Each outer worker runs the resource extractor with `workers=1`, which avoids a nested process pool. The parent retains paths and metadata instead of all PNG bytes.

Structured JSON logs use actions such as `list`, `version`, `fetch`, `unzip`, `extract`, `compose`, `apply`, `thumbnail`, `upload`, and `publish`. Each record identifies its `res_version` and status. Measurable work also reports elapsed milliseconds, and concurrent or complete-history work reports a stable `current` and `total` ordinal.

A terminal record uses `done`, a cache hit uses `cached`, and a failure uses `failed`.

## Reuse validated cache entries

The updater writes cache entries atomically and validates them before reuse. It replaces corrupted files or directories instead of treating them as cache hits.

Art cache entries use the percent-encoded upstream resource name and published MD5 value:

```text
.cache/<resVersion>/art/
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
                |   `-- <png-files>
                `-- manifest.json
```

Each stage depends only on the previous stage and records a format fingerprint. Completed entries remain until an operator removes them.

Locales share `.cache/game-data/archive.zip`. The updater validates the archive against every requested locale version before reuse. Extracted locale data remains under `.cache/<resVersion>/game-data/<unit>/extracted/`.

## Account for database and storage costs

The updater always uploads the complete SQLite object, even for a small locale change. Each service replica then downloads that complete object.

An offline schema run with all five locales produced a 234 MiB database before complete art metadata. Complete art builds also retain historical image prefixes and overwritten database versions, so plan object storage separately from local cache capacity.
