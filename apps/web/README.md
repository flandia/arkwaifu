# Arkwaifu web

The React 19 and React Router frontend for the Arkwaifu read service.

## Development

Use Bun 1.3.14 and the committed Bun lockfile:

```console
bun ci
bun run dev
```

The Vite development server listens on `http://127.0.0.1:5173`. Builds use the
public API at `https://api.arkwaifu.cc` by default. To use a local or preview
service, create `.env.local` before starting or building the app:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:58080
```

Vite embeds this value at build time; it is not runtime configuration. Image
elements use the object-storage URLs returned in API metadata: cards use
`thumbnailContentUrl`, while detail views and source layers use
`image.contentUrl`. Missing thumbnails show the normal unavailable state; the
frontend does not call a service redirect as a fallback.

Run all local checks with:

```console
bun run lint
bun run format:check
bun test
bun run build
```

## DigitalOcean App Platform

Deploy the frontend as a **Static Site** component with these settings:

- Source directory: `apps/web`
- Dockerfile path: `Dockerfile`
- Output directory: `dist`
- Catch-all document: `index.html`

App Platform builds the committed Dockerfile and extracts the static files from
its final `dist` directory. The Dockerfile pins Bun and installs the committed
lockfile before running the Vite build. Set `VITE_API_BASE_URL` as a build-time
variable when deploying against a non-production service; the Dockerfile exposes
it to Vite through a build argument. The catch-all setting is required so direct
visits to React Router routes load the application instead of returning a
platform 404.

The build depends on the current service contract: story-group details,
representative artwork, and direct thumbnail object-storage URLs in art-reference
and gallery-entry metadata. `/:locale/unclassified` uses the global
`/api/unclassified-arts` index to show art that is referenced by neither a story
nor a gallery; the locale segment only controls presentation and artwork-detail
navigation.

Story navigation exposes the seven schema categories directly. The dedicated
sections are 主线、活动、故事集、干员密录、集成战略 · 结局、生息演算 and
其他; the last section is a literal directory-based fallback and may include
tutorial or control scripts as well as narrative scenes.
