# Develop and deploy Arkwaifu web

This private React 19 app renders the Arkwaifu archive with React Router. Use Bun 1.3.14 to develop and verify it, then deploy the Vite output as a static site.

## Run the app locally

Install the committed lockfile and start the Vite development server:

```console
bun ci
bun run dev
```

Vite listens on `http://127.0.0.1:5173`.

For the complete local archive preview, keep MinIO in Docker and run the remaining processes on the host. The public `arkwaifu` bucket is the sole development archive ground truth:

```console
Push-Location dev
docker compose up -d minio minio-init
Pop-Location
```

Run the service from `apps/service/` on port `5174` with
`ARKWAIFU_DATABASE_URL=http://127.0.0.1:59000/arkwaifu/arkwaifu.sqlite3` and
`ARKWAIFU_OBJECT_BASE_URL=http://127.0.0.1:59000/arkwaifu`. In another terminal, run
Vite from `apps/web/` with `VITE_API_BASE_URL=http://127.0.0.1:5174`:

```console
Push-Location apps/web
$env:VITE_API_BASE_URL = "http://127.0.0.1:5174"
bun run dev
```

Do not create or serve a second filesystem copy of the development archive.

### Configure the archive service

Builds use `https://api.arkwaifu.cc` as the application programming interface
(API) origin by default. The same build automatically uses
`https://api.cn.arkwaifu.cc` when loaded from `cn.arkwaifu.cc`. An explicit
`VITE_API_BASE_URL` overrides both defaults. Create `.env.local` to use a local
or preview service:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:5174
```

Vite embeds this value at build time. Changing the deployed service origin requires a new build. The app renders object-storage addresses from API metadata: cards use `thumbnailContentUrl`, while detail views and source layers use `image.contentUrl`.

### Configure Google Analytics

Set the Google Analytics 4 (GA4) web-stream measurement identifier at build time:

```dotenv
VITE_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

To obtain the identifier, create or select a GA4 property in Google Analytics, open **Admin → Data collection and modification → Data Streams**, and create a Web stream for `https://arkwaifu.cc`. Copy its **Measurement ID**, which starts with `G-`, into the deployment variable above.

`index.html` contains Google's standard `gtag.js` snippet. Under the stream's **Enhanced measurement → Page views → Show advanced settings**, keep **Page changes based on browser history events** enabled so React Router navigation is counted. The app does not contain a separate analytics adapter and does not use Google Tag Manager.

Rebuild and deploy after setting the variable, then navigate between several routes and verify the resulting `page_view` events in GA4 DebugView or Realtime.

The measurement identifier is public configuration, not a secret. Enabling the tag does not replace the site's privacy obligations: the operator remains responsible for an appropriate privacy disclosure, consent handling where required, and ensuring that route or event data contains no personally identifiable information.

### Sitemap

The read service generates `https://api.arkwaifu.cc/sitemap.txt` from its current SQLite generation. The web app keeps only `public/robots.txt`, which advertises that URL. Archive updates therefore appear in the sitemap after the service refreshes its database; they do not require regenerating or redeploying the static website.

The sitemap covers every locale home, Score index, Movement, Score section, Archive index, Archive kind, Archive group, gallery index, and gallery page, plus the canonical CN copies of About and Unreferenced Artwork. It deliberately omits individual stories, gallery display members, and artworks, as well as query URLs. It is a crawl hint, not an indexing rule; use page metadata such as `noindex` when a page must not appear in search results.

Each successful route publishes one absolute canonical URL without its query string, fragment, or trailing slash. Locale-specific pages are self-referential; the locale-independent About and Unreferenced Artwork pages use their CN paths as canonical. Redirect-only and missing routes are not sitemap entries. Do not add a fixed canonical to `index.html`: that file is the catch-all document for every route and would incorrectly make every page canonical to the same URL.

The China mirror keeps canonical URLs on `https://arkwaifu.cc` and adds a
client-side `noindex,follow` directive. Also configure ESA to add the HTTP
response header `X-Robots-Tag: noindex, follow` for `cn.arkwaifu.cc`; the edge
header covers crawlers that do not execute the application JavaScript. Do not
submit the mirror to Search Console or publish a mirror sitemap.

The static catch-all has one remaining limitation: the host returns `index.html` with HTTP status `200` before the client knows whether a route exists. The client marks missing records `noindex`, but that is not a real HTTP `404` response and can still be reported as a soft 404. Correct status codes require routing at the server or edge rather than additional client metadata.

### Run the verification suite

Run the same lint, formatting, test, and build gates used during development:

```console
bun run lint
bun run format:check
bun test
bun run build
```

## Deploy to DigitalOcean App Platform

Create a **Static Site** component with these settings:

- Source directory: `apps/web`
- Dockerfile path: `Dockerfile`
- Output directory: `dist`
- Catch-all document: `index.html`

App Platform builds the committed Dockerfile and extracts the static files from its final `dist` directory. The Dockerfile pins Bun and installs the committed lockfile before running Vite.

Set `VITE_API_BASE_URL` as a build-time variable when the deployment uses a non-production service. The Dockerfile passes it to Vite through a build argument. Keep `index.html` as the catch-all document so direct visits to React Router paths load the app.

Do not set `VITE_API_BASE_URL` for the shared production build. Leaving it
unset lets that one artifact select `api.arkwaifu.cc` or
`api.cn.arkwaifu.cc` from the browser hostname. A configured value is an
intentional override and disables that automatic selection.

Set `VITE_GA_MEASUREMENT_ID` as another build-time variable to enable GA4 in production. The Dockerfile passes it through a separate build argument; changing either Vite variable requires a new build.

When DigitalOcean App Platform builds this Dockerfile from the repository, open the app's **Settings**, select the web component, edit **Environment Variables**, and add `VITE_GA_MEASUREMENT_ID` with **Build Time** scope. Save and redeploy the component. If App Platform deploys the prebuilt GHCR image instead, the value must be set as the GitHub Actions repository variable `VITE_GA_MEASUREMENT_ID` before that image is built; a DigitalOcean runtime variable cannot change an already compiled Vite bundle.

Deploy the service version that exposes `/sitemap.txt` before deploying this web build. After that, normal database publications update the sitemap through the service's existing refresh flow.

After deployment, submit `https://api.arkwaifu.cc/sitemap.txt` in Google Search Console and inspect representative rendered routes there. Search Console reports discovery, crawling, canonical selection, and indexing; GA4 reports visitor activity. Configuring one does not configure or validate the other.

## Operate the China mirror

The production artifact supports three ESA hostnames without a separate build:

- `cn.arkwaifu.cc` retrieves the static site from `arkwaifu.cc`.
- `api.cn.arkwaifu.cc` retrieves the read API from `api.arkwaifu.cc`.
- `assets.cn.arkwaifu.cc` retrieves public objects directly from
  `arkwaifu.sgp1.digitaloceanspaces.com`.

Set each HTTPS origin's Host header and server name indication (SNI) to its
origin hostname. In an ESA-to-origin request-header rule for only
`api.cn.arkwaifu.cc`, overwrite `X-Forwarded-Host` with
`api.cn.arkwaifu.cc`. Set the service runtime variable
`ARKWAIFU_CN_OBJECT_BASE_URL=https://assets.cn.arkwaifu.cc`.

Use ESA cache rules to bypass the API host and HTML requests to the web host.
Leave hashed JavaScript, Cascading Style Sheets (CSS), images, and WebP
thumbnails on ESA's default static-resource policy; do not add a full-site
cache rule. Add an ESA-to-client response-header rule for `cn.arkwaifu.cc`
that overwrites `X-Robots-Tag` with `noindex, follow`. The application also
emits a matching robots meta directive and keeps canonical URLs on the main
domain. Do not add the mirror to the sitemap.
