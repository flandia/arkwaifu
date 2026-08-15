# Add fallback art manually

Use this recovery procedure only when official Windows history cannot provide an art identity. Prepare the composition and its thumbnail, update the local SQLite database, then publish the database last.

## Prepare the composition PNG

Prepare the final Portable Network Graphics (PNG) image for this key:

```text
ART/{contributing_res_version}/composition/{category}/{escaped_id}.png
```

Percent-encode each dynamic path segment exactly once. Use a lowercase logical identifier and a category of `image`, `background`, `item`, or `character`.

Record the object key, byte size, width, and height. Treat the key as create-only. When you publish it, use these headers:

```text
Content-Type: image/png
Cache-Control: public, max-age=31536000, immutable
```

Do not replace an existing PNG. Accept it only when its byte size, content type, and cache policy match; stop on a conflict.

## Prepare the derived thumbnail

Generate one thumbnail from the final composition. Convert the image to red, green, blue, and alpha (RGBA) while preserving its aspect ratio. Fit it within 512 by 512 pixels without cropping or upscaling. Use Lanczos resampling with `reducing_gap=3.0`, then encode lossy WebP at quality 75.

Store the thumbnail under the composition’s version, category, and identifier:

```text
ART/{contributing_res_version}/thumbnail/{category}/{escaped_id}.webp
```

The service derives every `thumbnailContentUrl` from the composition key, so this object must exist even though SQLite has no thumbnail row. Replace any existing thumbnail at this key with `Content-Type: image/webp`. Omit `Cache-Control`; the object store and content delivery network (CDN) determine the cache policy. Do not create thumbnails for source layers.

## Update the art row

Download `arkwaifu.sqlite3` and start one transaction. Insert or update the row identified by `(category, art_id)`:

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
```

Keep the transaction open until you record any source layers. Do not change the art unit’s current `resVersion`; the object prefix identifies the upstream version that contributed the image.

## Record optional source layers

Prepare each retained character layer for this key:

```text
ART/{contributing_res_version}/source/character/{escaped_source_id}.png
```

Apply the composition PNG's create-only rule, `Content-Type`, and `Cache-Control` policy to every source object. Record each source under `(category, source_art_id)` with `kind = 'character'`, plus its character identifier, role, sprite variant, object key, byte size, width, and height.

For a character composition, replace its `art_source_refs` rows in composition order. Use `category = 'character'`, the composition `art_id`, a zero-based `position`, `source_category = 'character'`, and each stable source identifier.

A final composition remains usable without source rows when the original layers are unavailable.

Gallery composite panels use the same tables but keep the final art category, set `kind = 'composite_panel'`, and leave character metadata null. Their source-reference order must match the vertical top-to-bottom or horizontal left-to-right recipe. Do not use `/` in a panel identifier; the final composite identity joins ordered panel identifiers with `/` before object-key escaping.

## Adapt Android portrait fallbacks

ArknightsAssets2 publishes complete Android portraits instead of the Windows sprite-hub data and separate body and face layers. Store the complete portrait as one `whole_body` source.

Build the source identifier by joining the base identifier, the literal `whole_body`, the body value, and the face value with colons:

```text
base_identifier:whole_body:body_value:face_value
```

Build the sprite variant by joining the body and face values:

```text
body_value:face_value
```

Point the composition at that source. The source and composition objects intentionally use the same PNG bytes in this fallback.

## Publish the database

Commit the local transaction after every art, source, and source-reference row is ready:

```sql
COMMIT;
```

Publish the completed artifacts in this order:

1. Upload the create-only composition and source PNG objects
2. Upload or replace the derived WebP thumbnail
3. Overwrite `arkwaifu.sqlite3` with `Content-Type: application/vnd.sqlite3` and `Cache-Control: no-cache`

Do not upload the database when an image upload fails. The final database upload makes the fallback metadata visible to the service.

Fallback art does not distinguish Windows and Android copies for one logical row. The updater does not implement Real-ESRGAN processing.
