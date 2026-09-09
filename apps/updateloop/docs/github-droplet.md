# Schedule production updates on temporary Droplets

The `Run production updateloop` GitHub workflow checks for work every 15 minutes,
using `*/15 * * * *` (minutes 0, 15, 30, and 45 UTC), and supports manual dispatch from `master`.
It runs `updateloop check` using `ghcr.io/flandia/arkwaifu/updateloop:latest` on a GitHub-hosted runner.
Only a successful check reporting `update_needed: true` provisions a DigitalOcean
Droplet. The Droplet runs both update commands, then is destroyed.
GitHub schedules can be delayed or dropped under load; this is not an exact-time
scheduler. See [GitHub's scheduling guidance](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows).

## Configure GitHub

Add these repository Actions secrets:

| Secret | Value |
| --- | --- |
| `DIGITALOCEAN_ACCESS_TOKEN` | DigitalOcean API token allowed to list, create, and delete Droplets and SSH keys, and tag new Droplets |
| `UPDATELOOP_ENV` | Complete production environment in Docker env-file format: one literal `KEY=value` per line, without shell quoting or `export` |

The API token needs `droplet:read`, `droplet:create`, `droplet:delete`,
`ssh_key:read`, `ssh_key:create`, `ssh_key:delete`, and `tag:create`, together with
the dependent read scopes required by DigitalOcean's token editor. See
[DigitalOcean's create scope](https://docs.digitalocean.com/reference/api/scopes/droplet/create/).
The token stays on GitHub's runner. SSH keys are generated per invocation and
removed during cleanup; no long-lived SSH credential is needed.

Set `UPDATELOOP_ENV` using the production values described in the
[updater guide](../README.md#configure-object-storage), including the main S3
bucket, endpoint, region, access key, and secret key. Set archive destination
overrides when the defaults are unsuitable. Optional `ARKWAIFU_GITHUB_TOKEN`
raises the upstream API rate limit. Production bucket versioning must already
be enabled. Do not use the local MinIO environment.

Add these repository Actions variables:

| Variable | Value |
| --- | --- |
| `UPDATELOOP_REGION` | Optional; defaults to `sgp1` |
| `UPDATELOOP_SIZE` | Optional; defaults to `c-8` (8 dedicated vCPUs, 16 GiB RAM, 100 GiB disk) |

The workflow sets `UPDATELOOP_IMAGE` to `ghcr.io/flandia/arkwaifu/updateloop:latest`;
no repository image variable is required. Both preflight and the Droplet pull
`latest` before execution. Publishing a new image updates subsequent pulls,
including the Droplet's pull if a new image appears after preflight. The image
must include the `check` command; older images fail before provisioning.
The repository's `GITHUB_TOKEN` needs read access to the GHCR package; grant
this repository Actions access in the package settings if necessary.
Region capacity and size availability are checked by DigitalOcean at creation.

The regular CPU-Optimized 8-vCPU plan is listed at $0.25/hour as of September
2026. Ten minutes of total Droplet lifetime costs approximately $0.042 in
compute. Only checks finding pending work incur Droplet compute costs. If every
15-minute check needed a ten-minute Droplet, 30 days would cost approximately $120
in Droplet compute.
Boot, package installation, image pulls, execution, and cleanup all count.
These examples exclude object storage, transfer overages, and any GitHub Actions
charges. Check [current Droplet pricing](https://www.digitalocean.com/pricing/droplets).

## Execution and publication

The preflight reuses the updater's version detectors for artwork and all five
locales, downloads the published SQLite database into temporary storage, and
compares the recorded versions. Missing databases and required additive-index
repair also trigger a run. Archive-only backlog does not trigger a Droplet;
the archive catches up when a database update triggers both commands. An upstream,
storage, or schema error fails the check and prevents provisioning.

The preflight performs no bundle extraction, rendering, or remote writes. It does
download the full database on each check; budget that transfer and GitHub runner
time separately. It is a snapshot
decision: the Droplet detects upstream versions again before updating.

Each needed update uses Ubuntu 24.04, installs Docker, pulls the latest updater image,
and runs these two commands sequentially:

```sh
updateloop run
updateloop run --archive
```

The first publishes ordinary artwork and locale changes without waiting for
wrapper archival. The second catches up historical wrappers and then also checks
ordinary updates through the existing CLI. Both commands are attempted; either
failure makes the job fail. The first command's successful publication remains
visible if archival later fails. Neither uses `--complete` or `--force`.
The container retains its `/app` working directory and mounts a disposable
Droplet directory at `/app/.cache`, owned by UID 10001.

The initial limits are four extraction workers and sixteen download workers.
The larger CPU allocation also leaves room for locale processing, thumbnails,
and the coordinator. These are initial settings, not benchmarked requirements;
measure peak memory and elapsed time before raising extraction concurrency.

The cache is discarded with the Droplet. Published versions in SQLite still
drive incremental updates; losing the cache does not request a full artwork
rebuild. However, retries must download and prepare uncached work again.
Initial wrapper archival can be much larger than ordinary updates.

Production credentials are streamed over SSH into a root-readable env file.
The host key is generated by the runner and installed through cloud-init, so
SSH verifies a known key before sending credentials. S3 and GHCR credentials
are not embedded in user data. The DO token is never sent to the Droplet.

The workflow uses one repository-wide concurrency group with
`cancel-in-progress: false`. Other production workflows must use the same group;
manual writers on other machines must not run at the same time. Before creating
a Droplet, the workflow checks the repository-specific tag and refuses to start
if another unexpired updater Droplet exists. See the
[single-writer publication contract](publication.md#follow-the-end-to-end-publication-sequence).

## Logs, timeouts, and cleanup

The aggregate exit status of both commands determines the GitHub job result. The
preflight decision is retained in a separate artifact. Streamed updater
output, image-pull output, bootstrap status, and basic Droplet identification are
retained as a GitHub artifact for 14 days, including on failure when the runner
can upload them. Artifacts do not include the env file, SSH keys, or user data.

The remote systemd service stops the two-command sequence after 150 minutes total and forcibly
removes its container even if the SSH client disappears. The GitHub update job
has a 180-minute timeout. Cleanup runs immediately when the provisioning script
exits and again in a separate `always()` job. It checks the recorded Droplet IDs
as well as every Droplet matching this invocation's exact name within the repository
tag, retries deletion, and removes the invocation's SSH key. Only a direct
DigitalOcean `GET /v2/droplets/<id>` returning 404 confirms deletion; disappearance
from a tag listing is insufficient. If deletion cannot be confirmed, cleanup fails
visibly instead of reporting success. It attempts all matched IDs even when one
deletion fails.

The independent `Clean up updater Droplets` workflow retries exact-run cleanup
after the production workflow completes, including failure or cancellation.
It checks out trusted `master` scripts, never code or artifacts from the triggering
run. It also uses `*/15 * * * *`, and supports manual
dispatch to delete tagged updater Droplets older than four hours and their matching
SSH keys. This sweep operates even when preflight finds no work or fails. The
provisioning script performs the same expired-Droplet sweep before starting;
younger leftovers block another writer.

Force cancellation, GitHub outages, or DigitalOcean API outages can still prevent
immediate cleanup. No workflow can guarantee deletion while those services are
unavailable; the independent sweep retries after service recovers.
If GitHub schedules stop or credentials fail, delete leftovers manually in
DigitalOcean using the workflow's `arkwaifu-updateloop-<repository-id>` tag and
run-specific `arkwaifu-<run-id>-<attempt>` name. An SSH key orphaned before
Droplet creation also needs manual removal if normal cleanup never ran.
Never apply this tag to unrelated Droplets.

Stopping the remote process or powering off the Droplet does not stop billing;
the Droplet must be destroyed. See [DigitalOcean billing](https://docs.digitalocean.com/products/droplets/details/pricing/).

Before enabling routine production execution, dispatch one observed run after
reviewing the latest image and credentials. Check publication success, resource
use, logs, and confirmed Droplet deletion. Provisioning and production publishing
cannot be validated by the offline tests.

## Offline checks

Run the lifecycle tests manually when changing the workflow scripts. Scheduled
runs start directly with update detection and do not run linters or tests:

```sh
bash .github/scripts/test-updateloop-droplet.sh
```

The tests mock DigitalOcean and stop before provisioning. They cover
preflight decisions and failures, both update commands and their exit
statuses, exact-run cleanup, refusal to overlap a live writer, expired writer
cleanup, transient deletion failure, API failure, and deletion that never completes.
The updater's pytest suite also covers read-only version checks, schema errors,
index repair detection, and archive-only work.
