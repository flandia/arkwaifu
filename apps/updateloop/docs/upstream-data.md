# Understand upstream data and locale classification

The updater combines official Windows art data with locale snapshots and selected historical story text. This reference explains source provenance, version admission, and story classification.

## Read the configured upstream sources

Art versions and bundles come from the official Windows client content-delivery network (CDN). The updater uses the [Windows version endpoint](https://ak-conf.hypergryph.com/config/prod/official/Windows/version) and [Windows asset root](https://ak.hycdn.cn/assetbundle/official/Windows/assets) by default.

Story and gallery metadata for `CN`, `EN`, `JP`, `KR`, and `TW` comes from the `master` branch of `ArknightsAssets/ArknightsGamedata`.

For each locale, the updater reads `hot_update_list.json` and uses its non-empty `versionId` as the `resVersion`. It rejects a downloaded branch snapshot when the embedded locale version differs from the detected value.

The manifest, cache identity, and database store only `resVersion`. They do not store repository URLs, branches, commits, or other repository provenance.

## Discover complete Windows version history

The official client endpoint exposes only the current `resVersion`. Complete art mode reads the `pfyy/OpenBachelorS` observation ledger to discover older official versions, then validates the resulting chronological sequence.

The ledger is not an authoritative archive. The updater always includes the current version supplied by the official endpoint and requires it to be the final version processed.

The persistent cache stores only the ordered `resVersion` values. Repository revisions remain transient lookup details.

## Validate extracted paths and gallery schemas

The locale extractor rejects absolute paths, parent traversal, Windows drive paths, and paths that resolve outside its workspace. It applies the same checks to downloaded archives, historical story paths, and game-data references.

The gallery parser supports the older archive layout and the current composite computer-graphics (CG) layout. It keeps the existing explicit and fallback ordering rules unchanged.

## Classify story groups

The updater assigns stories to explicit semantic groups before it uses the `others` fallback. This precedence prevents one script from appearing in multiple groups.

The classification order is:

1. Story-review groups
2. Official Integrated Strategies ending catalogs
3. Reclamation Algorithm topics
4. Remaining story scripts under `others`

`story_review_table.json` supplies main stories, major events, minor events, and Operator Records. Entries marked `NONE` belong to Operator Records when `handbook_info_table.json` owns the same group identifier.

## Parse Integrated Strategies endings

The `integrated_strategies` type contains official endings, grouped by topic. Legacy `rogue_1` endings come from `story_review_meta_table.json` entries whose `contentPath` matches `level_rogue1_ending_*`.

Later endings come from `roguelike_topic_table.json` catalogs. The parser preserves topic order and ending `sortId` order from those catalogs.

Monthly-squad `chatStoryId` paths remain reserved but unpublished because their scripts contain no indexed art. Opening, tutorial, and preload helpers in the same theme directories do not fall through to `others`.

## Parse Reclamation Algorithm stories

Reclamation Algorithm topics come from `sandbox_perm_table.json`. The parser scans each topic’s `story/obt/sandboxperm/` directory and publishes only stories with parsed art references.

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
