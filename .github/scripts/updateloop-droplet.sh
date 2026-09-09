#!/usr/bin/env bash
set -euo pipefail

droplets() {
  doctl compute droplet list --tag-name "$DROPLET_TAG" --output json \
    | jq -ce 'if type == "array" then . else error("invalid Droplet inventory") end'
}

destroy() {
  local id=$1 status attempt
  [[ $id =~ ^[0-9]+$ ]] || return 1
  for ((attempt = 0; attempt < 12; attempt++)); do
    status=$(curl --silent --show-error --connect-timeout 5 --max-time 15 \
      --output /dev/null --write-out '%{http_code}' \
      -H "Authorization: Bearer $DIGITALOCEAN_ACCESS_TOKEN" \
      "https://api.digitalocean.com/v2/droplets/$id") || status=000
    if [[ $status == 404 ]]; then
      echo "Confirmed Droplet $id is deleted (API returned 404)."
      return
    fi
    if [[ $status == 200 ]]; then
      doctl compute droplet delete "$id" --force --http-retry-max 0 || true
    fi
    sleep 5
  done
  echo "Could not confirm deletion of Droplet $id (last HTTP status: $status)" >&2
  return 1
}

delete_keys() {
  local name=$1 keys ids id result=0
  keys=$(doctl compute ssh-key list --output json) || return 1
  ids=$(jq -ce --arg name "$name" '[.[] | select(.name == $name) | .id]' <<< "$keys") || return 1
  while read -r id; do
    doctl compute ssh-key delete "$id" --force || result=1
  done < <(jq -r '.[]' <<< "$ids")
  return "$result"
}

cleanup() {
  local inventory id ids result=0
  inventory=$(droplets) || { inventory='[]'; result=1; }
  ids=$(jq -cn --argjson known "${DROPLET_IDS:-[]}" --argjson inventory "$inventory" \
    --arg name "$DROPLET_NAME" \
    '$known + [$inventory[] | select(.name == $name) | .id] | unique') || return 1
  while read -r id; do
    if ! destroy "$id"; then result=1; fi
  done < <(jq -r '.[]' <<< "$ids")
  delete_keys "$DROPLET_NAME" || result=1
  return "$result"
}

reap() {
  local inventory expired id name result=0
  inventory=$(droplets) || return 1
  expired=$(jq -ce 'map(select((now - (.created_at | fromdateiso8601)) > 14400))' <<< "$inventory") || return 1
  while IFS=$'\t' read -r id name; do
    if destroy "$id"; then
      delete_keys "$name" || result=1
    else
      result=1
    fi
  done < <(jq -r '.[] | [.id, .name] | @tsv' <<< "$expired")
  return "$result"
}

case ${1:-} in
  cleanup) cleanup; exit ;;
  reap) reap; exit ;;
  run|check) ;;
  *) echo 'Expected run, check, cleanup, or reap' >&2; exit 2 ;;
esac
mkdir -p "$RUNNER_TEMP/updateloop-logs"
work=$(mktemp -d "$RUNNER_TEMP/updateloop.XXXXXX")
chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT

if [[ $1 == check ]]; then
  printf '%s\n' "$UPDATELOOP_ENV" > "$work/.env.prod"
  chmod 600 "$work/.env.prod"
  printf '%s' "$GH_TOKEN" | docker login ghcr.io --username "$GITHUB_ACTOR" --password-stdin
  docker pull "$UPDATELOOP_IMAGE"
  docker run --rm --env-file "$work/.env.prod" "$UPDATELOOP_IMAGE" check \
    | tee "$RUNNER_TEMP/updateloop-logs/preflight.json"
  needed=$(jq -er '.update_needed | if type == "boolean" then tostring else error("invalid decision") end' \
    "$RUNNER_TEMP/updateloop-logs/preflight.json")
  printf 'update_needed=%s\n' "$needed" >> "${GITHUB_OUTPUT:?}"
  exit
fi
# A lost runner can leave a writer alive. Reap only this workflow's expired
# Droplets, then refuse to overlap any remaining writer, regardless of run ID.
reap
inventory=$(droplets)
if [[ $(jq length <<< "$inventory") != 0 ]]; then
  echo 'A previous updater Droplet still exists; refusing another writer.' >&2
  exit 1
fi

finish() {
  local result=$?
  trap - EXIT
  if ! cleanup; then result=1; fi
  rm -rf -- "$work"
  exit "$result"
}
trap finish EXIT

ssh-keygen -q -t ed25519 -N '' -f "$work/client"
ssh-keygen -q -t ed25519 -N '' -f "$work/host"
key_id=$(doctl compute ssh-key import "$DROPLET_NAME" \
  --public-key-file "$work/client.pub" --format ID --no-header)

# Pin the host key through the authenticated DO creation request. Production
# credentials are transferred later over SSH, never through Droplet user data.
jq -n --rawfile private "$work/host" --rawfile public "$work/host.pub" '{
  ssh_keys: {ed25519_private: $private, ed25519_public: $public},
  ssh_pwauth: false,
  package_update: true,
  packages: ["docker.io"],
  runcmd: [["systemctl", "enable", "--now", "docker"]]
}' > "$work/cloud-init.json"
{ echo '#cloud-config'; cat "$work/cloud-init.json"; } > "$work/cloud-init.yaml"

doctl compute droplet create "$DROPLET_NAME" \
  --image ubuntu-24-04-x64 --region "$DROPLET_REGION" --size "$DROPLET_SIZE" \
  --ssh-keys "$key_id" --tag-names "$DROPLET_TAG" \
  --user-data-file "$work/cloud-init.yaml" --output json \
  | jq '[.[] | {id, name, created_at}]' > "$RUNNER_TEMP/updateloop-logs/droplet.json"
DROPLET_IDS=$(jq -c '[.[].id]' "$RUNNER_TEMP/updateloop-logs/droplet.json")
printf 'droplet_ids=%s\n' "$DROPLET_IDS" >> "${GITHUB_OUTPUT:?}"

ip=''
for ((attempt = 0; attempt < 60; attempt++)); do
  inventory=$(droplets)
  ip=$(jq -r --arg name "$DROPLET_NAME" \
    '.[] | select(.name == $name and .status == "active") | .networks.v4[] | select(.type == "public") | .ip_address' <<< "$inventory")
  [[ -n $ip ]] && break
  sleep 5
done
[[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo 'Expected exactly one active Droplet with a public IPv4 address' >&2; exit 1;
}
printf '%s %s\n' "$ip" "$(cat "$work/host.pub")" > "$work/known_hosts"
ssh_options=(-i "$work/client" -o BatchMode=yes -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$work/known_hosts"
  -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=3)
remote() { ssh "${ssh_options[@]}" "root@$ip" "$@"; }

ready=false
for ((attempt = 0; attempt < 60; attempt++)); do
  if remote true 2>/dev/null; then ready=true; break; fi
  sleep 5
done
[[ $ready == true ]] || { echo 'SSH did not become ready' >&2; exit 1; }
timeout 15m ssh "${ssh_options[@]}" "root@$ip" 'cloud-init status --wait' 2>&1 \
  | tee "$RUNNER_TEMP/updateloop-logs/bootstrap.log"

printf '%s\n' "$UPDATELOOP_ENV" | remote 'umask 077; cat > /root/.env.prod'
printf '%s' "$GH_TOKEN" | remote "docker login ghcr.io --username '$GITHUB_ACTOR' --password-stdin"
remote "docker pull '$UPDATELOOP_IMAGE'" | tee "$RUNNER_TEMP/updateloop-logs/image.log"
remote 'docker logout ghcr.io; install -d -o 10001 -g 10001 /var/lib/arkwaifu-cache'
remote 'cat > /root/run-updateloop.sh; chmod 755 /root/run-updateloop.sh' \
  < "$(dirname "$0")/run-updateloop.sh"

# systemd owns the runtime deadline even if the SSH client or runner disappears.
# ExecStopPost also removes the daemon-owned container when the client is killed.
remote "systemd-run --unit=arkwaifu-updateloop --wait --pipe \
  -p RuntimeMaxSec=9000 \
  -p 'ExecStopPost=-/usr/bin/docker rm -f arkwaifu-updateloop' \
  /usr/bin/docker run --rm --name arkwaifu-updateloop --entrypoint /bin/sh \
  --env-file /root/.env.prod \
  -e ARKWAIFU_EXTRACTION_WORKERS=4 -e ARKWAIFU_DOWNLOAD_WORKERS=16 \
  -v /var/lib/arkwaifu-cache:/app/.cache \
  -v /root/run-updateloop.sh:/run-updateloop.sh:ro \
  '$UPDATELOOP_IMAGE' /run-updateloop.sh" 2>&1 \
  | tee "$RUNNER_TEMP/updateloop-logs/updateloop.log"
