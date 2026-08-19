# Understand upstream data and locale classification

The updater combines official Windows artwork data with locale snapshots and selected historical story text. This reference explains source provenance, version admission, and story classification.

## Read the configured upstream sources

Artwork versions and bundles come from the official Windows client content-delivery network (CDN). The updater uses the [Windows version endpoint](https://ak-conf.hypergryph.com/config/prod/official/Windows/version) and [Windows asset root](https://ak.hycdn.cn/assetbundle/official/Windows/assets) by default.

Score, Archive, story, and gallery metadata for `CN`, `EN`, `JP`, `KR`, and `TW` comes from the `master` branch of `ArknightsAssets/ArknightsGamedata`.

For each locale, the updater reads `hot_update_list.json` and uses its non-empty `versionId` as the `resVersion`. It rejects a downloaded branch snapshot when the embedded locale version differs from the detected value.

The manifest, cache identity, and database store only `resVersion`. They do not store repository URLs, branches, commits, or other repository provenance.

## Discover complete Windows version history

The official client endpoint exposes only the current `resVersion`. Complete artwork mode and asset-bundle archive mode read the `pfyy/OpenBachelorS` observation ledger to discover older official versions, then validate the resulting chronological sequence.

The ledger is not an authoritative archive. The updater always includes the current version supplied by the official endpoint and requires it to be the final version processed.

The persistent cache stores only the ordered `resVersion` values. Repository revisions remain transient lookup details.

The ledger supplies version order, not bundle bytes. `--archive` still downloads each selected wrapper and exact `hot_update_list.json` from the official CDN, validates the wrapper's inner bundle against the manifest MD5, and stores the manifest last. An empty archive begins at the oldest recorded version; an existing archive resumes after its newest completed version.

## Validate extracted paths and gallery schemas

The locale extractor rejects absolute paths, parent traversal, Windows drive paths, and paths that resolve outside its workspace. It applies the same checks to downloaded archives, historical story paths, and game-data references.

The current gallery schema is authoritative. The parser retains its complete hierarchy:

1. `cgGalleryGroups` owns one story collection and becomes a Gallery
2. `cgGalleryDisplays` is the upstream table adapted into Gallery Groups
3. `cgGalleryCgs` identifies each Gallery Artwork and its optional panel layout
4. `compositeList` is the upstream field containing ordered Material panels and dimensions

Mapping keys and declared identifiers must agree case-insensitively. Referenced Galleries, Gallery Groups, Gallery Artwork, and panels are required; unknown enum values and empty current groups fail closed.

Older archive pictures are merged after the current hierarchy. Exact category-qualified overlaps are absorbed by the current Gallery Group, while each remaining legacy picture becomes a singleton Gallery Group. This preserves legacy-only Artwork without flattening current group relationships.

Vertical layouts stitch panels from top to bottom and horizontal layouts stitch them from left to right. A final Narrative Image's logical ID is the slash-joined ordered panel identifiers. The Gallery keeps the upstream CG identifier separately. Panels remain ordinary Narrative Image Assets when story scripts reference them and are also retained as category-qualified `panel` Materials of the stitched result.

Panel layouts participate in the rendered-cache fingerprint, but an incremental Artwork update visits only changed Windows bundles. Run `updateloop run artwork --complete` for the first hierarchy rollout and whenever locale metadata changes a layout whose panel bundle did not change; unresolved Artwork references otherwise remain publishable and produce an incomplete-upstream warning.

## Build Scores, Movements, and Sections

The public **Scores** module is the English client term for `曲谱`; it is a catalog rather than a stored parent record. Its hierarchy comes from `stage_table.json`:

- One `storylines` record is a **Movement** (`乐章`)
- One `storylineStorySets` record is a reusable **Section**
- One story-review record supplies the section's ordered story leaves

The updater preserves every Movement location in `sortId` order. Every Section must have exactly one `STORY_SET` canonical placement. `BEFORE` and `AFTER` place an existing Section in another Movement's chronology, and the upstream `MAINLINE_SPLIT` value becomes a Movement Divider with no Section. Keeping locations as relations avoids duplicating Sections and preserves cross-Movement placement.

Section ownership is resolved from `relevantActivityId`, `mainlineData.zoneId`, or the unique main-story review group reachable through `activity_table.zoneToActivity` and the stage table. A main-story review group must be claimed by exactly one section. Review groups outside Scores become Archive Groups.

Movement and Section metadata also retain their declared visual identifiers: Movement icon, logo, and background; Section key visual, title, background, decoration, and retrospective background; and Movement Divider icon. Upstream mainline-split identifiers map by numeric suffix to the corresponding `bg_mainline_<n>` video when the Movement declares video playback. Asset references deliberately remain valid when the Artwork unit has not published the bytes yet; publication reports them as incomplete upstream data.

The automatic artwork pipeline currently reads these dedicated Score visuals from the official CN Windows client. The logical identifiers are shared across locales, and the same CN visual objects serve all localized metadata until separate official client sources are configured. Text remains locale-specific.

## Classify Archive Groups and story ownership

The updater assigns stories to explicit semantic groups before it uses the `others` fallback. This precedence prevents one script from appearing in multiple groups.

The classification order is:

1. Story-review groups
2. Official Integrated Strategies ending catalogs
3. Reclamation Algorithm topics
4. Remaining story scripts under `others`

`story_review_table.json` supplies main stories, side stories, vignettes, and Operator Records. Main-story groups are claimed by Sections first. The remaining side stories and vignettes enter the `events` Archive Category. Entries marked `NONE` belong to Operator Records when `handbook_info_table.json` owns the same group identifier.

## Parse Integrated Strategies endings

The `integrated_strategies` type contains official endings, grouped by topic. Legacy `rogue_1` endings come from `story_review_meta_table.json` entries whose `contentPath` matches `level_rogue1_ending_*`.

Later endings come from `roguelike_topic_table.json` catalogs. The parser preserves topic order and ending `sortId` order from those catalogs.

Monthly-squad `chatStoryId` paths remain reserved but unpublished because their scripts contain no indexed artwork. Opening, tutorial, and preload helpers in the same theme directories do not fall through to `others`.

## Parse Reclamation Algorithm stories

Reclamation Algorithm topics come from `sandbox_perm_table.json`. The parser scans each topic’s `story/obt/sandboxperm/` directory and publishes only stories with parsed artwork references.

Training, user-interface, and challenge-guide scripts remain outside this category.

## Handle remaining story scripts

After explicit categories claim their scripts, the updater groups each remaining non-`[uc]` `story/**/*.txt` file by source directory under `others`. This fallback can include tutorials, control scripts, preload helpers, and other technical scripts.

Files marked `[uc]` are companion descriptions and never become separate stories. A script belongs only to the first matching category.

## Recover missing story text

When an explicit catalog references missing text, the updater searches partial Git histories in priority order. It selects the newest revision containing the exact file.

Repository priority depends on locale:

- `CN`: ArknightsAssets, then Kengxxiao
- `EN`, `JP`, and `KR`: ArknightsAssets, then YoStar, then Kengxxiao
- `TW`: ArknightsAssets, then aelurum

These repositories contain periodic snapshots rather than every official `resVersion`. A file introduced and removed between snapshots may remain unavailable.

If all repositories confirm that a file is absent, the updater keeps its story metadata, emits an incomplete-upstream warning, and continues without directives. Clone, history, and blob-read failures abort the locale build.

Git must be available on `PATH`. The updater container image installs it.

The extracted locale cache stores recovered text but no repository or commit identifiers. Because the cache uses the game `resVersion`, use `--no-cache` or remove that locale’s extracted cache to retry a repository-only backfill at the same version. `--force` alone reuses the cache.
