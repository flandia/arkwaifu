#!/usr/bin/env bash
# Offline lifecycle tests: no DigitalOcean credentials, network, or containers.
set -euo pipefail
script=$(cd "$(dirname "$0")" && pwd)/updateloop-droplet.sh
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
mkdir "$test_dir/bin"
export TEST_STATE="$test_dir" RUNNER_TEMP="$test_dir"
export GITHUB_OUTPUT="$test_dir/outputs"
export DROPLET_TAG=test-updateloop DROPLET_NAME=arkwaifu-123-1
export DIGITALOCEAN_ACCESS_TOKEN=test UPDATELOOP_ENV=test GH_TOKEN=test
export DROPLET_REGION=sgp1 DROPLET_SIZE=c-8 GITHUB_ACTOR=test
export UPDATELOOP_IMAGE=ghcr.io/flandia/arkwaifu/updateloop:latest
export PATH="$test_dir/bin:$PATH"

cat > "$test_dir/bin/doctl" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "$TEST_STATE/calls"
case "$1 $2 $3" in
  'compute droplet list')
    [[ ${LIST_ERROR:-false} == true ]] && exit 1
    if [[ ${HIDE_FROM_LIST:-false} == true ]]; then echo '[]'; else cat "$TEST_STATE/droplets.json"; fi ;;
  'compute ssh-key list') cat "$TEST_STATE/keys.json" ;;
  'compute droplet delete')
    [[ ${STUCK:-false} == true ]] && exit 0
    if [[ ${DELETE_FAIL_ONCE:-false} == true && ! -e $TEST_STATE/retried ]]; then
      touch "$TEST_STATE/retried"; exit 1
    fi
    jq --argjson id "$4" 'map(select(.id != $id))' "$TEST_STATE/droplets.json" > "$TEST_STATE/next.json"
    mv "$TEST_STATE/next.json" "$TEST_STATE/droplets.json" ;;
  'compute ssh-key delete') ;;
  *) echo "Unexpected doctl call: $*" >&2; exit 99 ;;
esac
MOCK
cat > "$test_dir/bin/curl" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
[[ ${API_ERROR:-false} == true ]] && { echo 503; exit; }
url=${!#}
id=${url##*/}
if jq -e --argjson id "$id" 'any(.[]; .id == $id)' "$TEST_STATE/droplets.json" >/dev/null; then
  echo 200
else
  echo 404
fi
MOCK
cat > "$test_dir/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
echo "docker $*" >> "$TEST_STATE/calls"
case $1 in
  login) cat >/dev/null ;;
  pull) ;;
  run) echo "${PREFLIGHT_JSON:-invalid}"; exit "${PREFLIGHT_STATUS:-0}" ;;
  *) exit 99 ;;
esac
MOCK
cat > "$test_dir/bin/updateloop" <<'MOCK'
#!/usr/bin/env bash
echo "$*" >> "$TEST_STATE/commands"
[[ $* != "${FAIL_COMMAND:-}" ]]
MOCK
# Stop the run at the provisioning boundary; these tests must never create keys.
printf '#!/usr/bin/env bash\nexit 97\n' > "$test_dir/bin/ssh-keygen"
printf '#!/usr/bin/env bash\nexit 0\n' > "$test_dir/bin/sleep"
chmod +x "$test_dir/bin/"*

reset_state() {
  printf '[]\n' > "$test_dir/droplets.json"
  printf '[]\n' > "$test_dir/keys.json"
  : > "$test_dir/calls"
  : > "$test_dir/outputs"
  : > "$test_dir/commands"
}
expect_failure() {
  if bash "$script" "$1" > "$test_dir/output" 2>&1; then
    echo "Expected $1 to fail" >&2; exit 1
  fi
}

reset_state
printf '[{"id":1,"name":"arkwaifu-123-1"},{"id":2,"name":"another-run"}]' > "$test_dir/droplets.json"
printf '[{"id":10,"name":"arkwaifu-123-1"},{"id":20,"name":"another-run"}]' > "$test_dir/keys.json"
bash "$script" cleanup
[[ $(jq -r '.[0].id' "$test_dir/droplets.json") == 2 ]]
grep -q 'compute ssh-key delete 10 --force' "$test_dir/calls"
if grep -q 'delete 20' "$test_dir/calls"; then exit 1; fi

reset_state
jq -n '[{id:1,name:"previous-run",created_at:(now | todateiso8601)}]' > "$test_dir/droplets.json"
expect_failure run
grep -q 'refusing another writer' "$test_dir/output"
if grep -q delete "$test_dir/calls"; then exit 1; fi

reset_state
printf '[{"id":1,"name":"expired-run","created_at":"2020-01-01T00:00:00Z"}]' > "$test_dir/droplets.json"
printf '[{"id":10,"name":"expired-run"}]' > "$test_dir/keys.json"
expect_failure run
[[ $(jq length "$test_dir/droplets.json") == 0 ]]
grep -q 'compute ssh-key delete 10 --force' "$test_dir/calls"

reset_state
printf '[{"id":1,"name":"arkwaifu-123-1"}]' > "$test_dir/droplets.json"
STUCK=true expect_failure cleanup
grep -q 'Could not confirm deletion' "$test_dir/output"

# Known IDs are checked directly even if they disappear from the tag listing.
reset_state
printf '[{"id":1,"name":"arkwaifu-123-1"}]' > "$test_dir/droplets.json"
HIDE_FROM_LIST=true DROPLET_IDS='[1]' DELETE_FAIL_ONCE=true bash "$script" cleanup
[[ $(jq length "$test_dir/droplets.json") == 0 ]]

reset_state
printf '[{"id":1,"name":"arkwaifu-123-1"}]' > "$test_dir/droplets.json"
API_ERROR=true expect_failure cleanup
grep -q 'Could not confirm deletion' "$test_dir/output"

reset_state
printf '[{"id":1,"name":"arkwaifu-123-1"}]' > "$test_dir/droplets.json"
LIST_ERROR=true DROPLET_IDS='[1]' expect_failure cleanup
[[ $(jq length "$test_dir/droplets.json") == 0 ]]

reset_state
printf '[{"id":1,"created_at":"invalid"}]' > "$test_dir/droplets.json"
expect_failure reap

# An independent sweep still removes expired writers without a preflight run.
reset_state
printf '[{"id":1,"name":"expired","created_at":"2020-01-01T00:00:00Z"}]' > "$test_dir/droplets.json"
bash "$script" reap
[[ $(jq length "$test_dir/droplets.json") == 0 ]]

for needed in false true; do
  reset_state
  PREFLIGHT_JSON="{\"update_needed\":$needed}" bash "$script" check
  grep -q "update_needed=$needed" "$test_dir/outputs"
  if grep -q 'compute droplet create' "$test_dir/calls"; then exit 1; fi
done
reset_state
PREFLIGHT_JSON='{"update_needed":false}' PREFLIGHT_STATUS=1 expect_failure check
[[ ! -s "$test_dir/outputs" ]]
reset_state
PREFLIGHT_JSON='{}' expect_failure check
[[ ! -s "$test_dir/outputs" ]]

for command in '' run 'run --archive'; do
  reset_state
  status=0
  FAIL_COMMAND="$command" sh "$(dirname "$script")/run-updateloop.sh" || status=$?
  if [[ -z $command ]]; then [[ $status == 0 ]]; else [[ $status == 1 ]]; fi
  [[ $(cat "$test_dir/commands") == $'run\nrun --archive' ]]
done

echo 'Droplet lifecycle tests passed'
