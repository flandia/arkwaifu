# Working notes for arkwaifu

## Project overview

`arkwaifu` is the Go backend for serving Arknights story data and extracted
story art. The update loop downloads game resources and game data, extracts
images, processes them, and writes art/story records to PostgreSQL. The
frontend is maintained separately.

The Go module path is `github.com/flandiayingman/arkwaifu` and the project
currently targets Go 1.24.

## Repository map

- `cmd/` contains service and update-loop entrypoints.
- `internal/app/` contains application services, the update loop, and art/story
  persistence logic.
- `internal/pkg/arkassets/` downloads and unpacks the official Android asset
  bundles from the Arknights CDN.
- `internal/pkg/arkdata/` downloads story data from the game-data repository.
- `internal/pkg/arkparser/` parses story directives and character references.
- `internal/pkg/arkscanner/` converts extracted JSON/type-tree files into art
  models.
- `internal/pkg/arkprocessor/` decodes, composites, and resizes art images.
- `tools/extractor/` is the Python UnityPy-based asset extractor.
- `deploy/docker-compose.yml` describes the service, update loop, PostgreSQL,
  frontend, and reverse proxy containers.

## Asset extraction details

The asset flow is:

1. Download CDN `.dat` files.
2. Extract the outer ZIP into Unity asset bundles (`.ab`).
3. Run `tools/extractor/main.py`.
4. Scan the resulting `assets/torappu/dynamicassets/...` tree and process the
   referenced images.

Arknights resource bundles after the Unity upgrade use the custom LZ4AK format.
`tools/extractor/lz4ak.py` patches UnityPy's reserved compression flags 4 and 5:
the token nibbles are reversed and match offsets are big-endian. Keep this
patch active when changing the UnityPy version; the standard UnityPy LZHAM
decoder is not compatible with these bundles.

Some current bundles use an internal `dyn/...` container prefix. The extractor
maps it to `assets/torappu/dynamicassets/...`, which is the path expected by the
Go scanner. Character bundles may reference a shared MonoScript CAB that is not
included in the bundle; the extractor falls back to the serialized type-tree
shape for character hub names so image data can still be exported.

Directory extraction deliberately recycles a worker after each bundle and waits
for every submitted future. UnityPy/native image allocations can otherwise
accumulate over a large art batch; an OOM-killed worker must fail the update
rather than silently leaving bundles unextracted and advancing the art version
marker.

Use `-w 1` while debugging extraction so output and failures are deterministic.
Do not commit downloaded bundles, generated images, virtual environments, or
credentials. This checkout locally excludes `.cache/` and `.env.local` via
`.git/info/exclude`; keep those patterns local rather than adding them to the
shared `.gitignore`. The `.cache/` directory is the preferred location for
temporary CDN/debug artifacts and should be reused to avoid duplicate fetches.

## Common commands

```powershell
# Go formatting and tests
gofmt -w <changed-go-files>
go test ./...

# Python extractor tests (from the repository root)
python -m unittest discover -s tools/extractor -p 'test_*.py' -v

# Extract a cached/debug bundle set
python tools/extractor/main.py -w 1 <bundle-root> <output-root>
```

The existing Go asset/data tests perform network-backed fetches. For an
offline compile-only check, use `go test ./... -run '^$'` with Go caches under
`.cache/`. The update loop expects `POSTGRES_DSN` and `ROOT`; a temporary
PostgreSQL container can be used for local integration debugging, but do not
modify the live deployment unless explicitly requested.

## Change guidelines

- Preserve unrelated working-tree changes, especially local environment files.
- Keep CDN and database operations bounded and cache repeated downloads.
- When changing extraction, verify both the Python extractor and the Go
  scanner/processor path; successful UnityPy object loading alone is not
  sufficient.
- Add a focused regression test for parser, extraction, or processing behavior
  that changes.
