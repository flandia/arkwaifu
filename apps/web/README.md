# Develop and deploy Arkwaifu web

This private React 19 app renders the Arkwaifu archive with React Router. Use Bun 1.3.14 to develop and verify it, then deploy the Vite output as a static site.

## Run the app locally

Install the committed lockfile and start the Vite development server:

```console
bun ci
bun run dev
```

Vite listens on `http://127.0.0.1:5173`.

### Configure the archive service

Builds use `https://api.arkwaifu.cc` as the application programming interface (API) origin by default. Create `.env.local` to use a local or preview service:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:58080
```

Vite embeds this value at build time. Changing the deployed service origin requires a new build. The app renders object-storage addresses from API metadata: cards use `thumbnailContentUrl`, while detail views and source layers use `image.contentUrl`.

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

Deploy the matching service before this web build. The client calls the canonical `/api/unreferenced-arts` route; the service keeps `/api/unclassified-arts` only for older clients.
