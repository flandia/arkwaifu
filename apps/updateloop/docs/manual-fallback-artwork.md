# Add a fallback Narrative Image manually

Use this recovery procedure only when official Windows history cannot provide a Narrative Image identity. Prepare the final image and its thumbnail, update the local SQLite database, then publish the database last.

## Prepare the final PNG

Prepare the final Portable Network Graphics (PNG) image for this key:

```text
ART/{contributing_res_version}/composition/{category}/{escaped_id}.png
```

Percent-encode each dynamic path segment exactly once. Use a lowercase logical identifier and a category of `illustration`, `background`, `item`, or `character`.

Record the object key, byte size, width, and height. Treat the key as create-only. When you publish it, use these headers:

```text
Content-Type: image/png
Cache-Control: public, max-age=31536000, immutable
```

Do not replace an existing PNG. Accept it only when its byte size, content type, and cache policy match; stop on a conflict.

## Prepare the derived thumbnail

Generate one thumbnail from the final Narrative Image. Convert the image to red, green, blue, and alpha (RGBA) while preserving its aspect ratio. Fit it within 512 by 512 pixels without cropping or upscaling. Use Lanczos resampling with `reducing_gap=3.0`, then encode lossy WebP at quality 75.

Store the thumbnail under the Artwork's version, category, and identifier:

```text
ART/{contributing_res_version}/thumbnail/{category}/{escaped_id}.webp
```

The service derives every `previewUrl` from the final image key, so this object must exist even though SQLite has no thumbnail row. Replace any existing thumbnail at this key with `Content-Type: image/webp`. Omit `Cache-Control`; the object store and content delivery network (CDN) determine the cache policy. Do not create thumbnails for Material Assets.

## Update the Narrative Image row

Download `arkwaifu.sqlite3` and start one transaction. Insert or update the row identified by `(category, asset_id)` in the `narrative` namespace:

```sql
BEGIN IMMEDIATE;
INSERT INTO narrative_image_assets
    (category, asset_id, object_key, size, width, height)
VALUES
    (:category, :asset_id, :object_key, :size, :width, :height)
ON CONFLICT (category, asset_id) DO UPDATE SET
    object_key = excluded.object_key,
    size = excluded.size,
    width = excluded.width,
    height = excluded.height;
```

Keep the transaction open until you record any Materials. Do not change the artwork unit’s current `resVersion`; the object prefix identifies the upstream version that contributed the image.

## Record optional Materials

Prepare each retained character layer for this key:

```text
ART/{contributing_res_version}/source/character/{escaped_material_id}.png
```

Apply the final PNG's create-only rule, `Content-Type`, and `Cache-Control` policy to every Material object. Record each Material in `material_assets` under `(category, asset_id)` with `material_type = 'character'`, plus its character identifier, role, sprite variant, object key, size, width, and height.

For a Character Narrative Image, replace its `narrative_asset_material_references` rows in Material order. Use `category = 'character'`, the image `asset_id`, a zero-based `position`, `material_category = 'character'`, and each stable Material identifier.

A final Narrative Image remains usable without Material rows when the original inputs are unavailable.

Gallery panels use the same tables but keep the final Narrative Image category, set `material_type = 'panel'`, and leave character metadata null. Their Material Reference order must match the vertical top-to-bottom or horizontal left-to-right layout. Do not use `/` in a panel identifier; the final image ID joins ordered panel identifiers with `/` before object-key escaping.

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

Point the Narrative Image at that Material. The Material and final image objects intentionally use the same PNG bytes in this fallback.

## Publish the database

Commit the local transaction after every artwork, source, and source-reference row is ready:

```sql
COMMIT;
```

Publish the completed artifacts in this order:

1. Upload the create-only Narrative Image and Material PNG objects
2. Upload or replace the derived WebP thumbnail
3. Overwrite `arkwaifu.sqlite3` with `Content-Type: application/vnd.sqlite3` and `Cache-Control: no-cache`

Do not upload the database when an image upload fails. The final database upload makes the fallback metadata visible to the service.

Fallback artwork does not distinguish Windows and Android copies for one logical row. The updater does not implement Real-ESRGAN processing.
