#!/usr/bin/env bash
# Pocket Lab Lite Server Phone runtime-resilience qualification.
#
# Default mode is read-only. Fault modes are explicit, bounded, and reversible.
# Android reboot is intentionally operator-owned; --post-reboot only verifies
# the runtime after the operator has rebooted the phone.
set -Eeuo pipefail

MODE="${1:---read-only}"
SSH_ALIAS="${POCKETLAB_TERMUX_SSH_ALIAS:-pocketlab-termux}"

case "$MODE" in
  --read-only|--post-reboot)
    ;;
  --faults)
    [[ "${POCKETLAB_RUNTIME_FAULTS:-0}" == "1" ]] || {
      echo "ERROR: --faults requires POCKETLAB_RUNTIME_FAULTS=1" >&2
      exit 2
    }
    ;;
  --remote-access-fault)
    [[ "${POCKETLAB_ALLOW_REMOTE_ACCESS_FAULT:-0}" == "1" && "${POCKETLAB_SSH_OUT_OF_BAND:-0}" == "1" ]] || {
      echo "ERROR: remote-access fault requires POCKETLAB_ALLOW_REMOTE_ACCESS_FAULT=1 and POCKETLAB_SSH_OUT_OF_BAND=1" >&2
      exit 2
    }
    ;;
  *)
    echo "Usage: $0 [--read-only|--faults|--post-reboot|--remote-access-fault]" >&2
    exit 2
    ;;
esac

remote_read_only() {
  local mode="${1:---read-only}"
  ssh "$SSH_ALIAS" bash -s -- "$mode" <<'REMOTE'
set -Eeuo pipefail
mode="$1"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

required="pocket-nats pocket-opa pocket-worker pocket-api pocket-node-agent caddy-proxy pocketlab-core-supervisor pocketlab-runtime-reconciler"
legacy="vault mariadb gitea gitea-runner pocket-gatus gatus prometheus-db prometheus grafana-ui grafana loki-kms loki promtail-agent promtail"

[[ -x "$HOME/.termux/boot/pocketlab-lite" ]] || fail "Termux:Boot entry missing or not executable: ~/.termux/boot/pocketlab-lite"
echo "PASS Termux:Boot recovery entry installed"

pgrep -f "[r]untime-guardian.sh" >/dev/null 2>&1 || fail "external runtime guardian is not running"
echo "PASS external runtime guardian running"

pm2_home="${PM2_HOME:-$HOME/.pm2}"
[[ -s "$pm2_home/pm2.pid" ]] || fail "PM2 pid file missing or empty: $pm2_home/pm2.pid"
pm2_pid="$(cat "$pm2_home/pm2.pid" 2>/dev/null || true)"
[[ "$pm2_pid" =~ ^[0-9]+$ ]] || fail "PM2 pid file does not contain a numeric PID"
kill -0 "$pm2_pid" >/dev/null 2>&1 || fail "PM2 daemon PID $pm2_pid is not running"
echo "PASS PM2 daemon running"

curl -fsS --connect-timeout 1 --max-time 4 http://127.0.0.1:8080/health >/dev/null ||
  fail "Lite API /health is not reachable on 127.0.0.1:8080"
echo "PASS Lite API health reachable"

curl -fsS --connect-timeout 1 --max-time 4 http://127.0.0.1:8080/ready >/dev/null ||
  fail "Lite API /ready is not reachable on 127.0.0.1:8080"
echo "PASS Lite API readiness reachable"

pm2_json="$(pm2 jlist 2>/dev/null)" || fail "pm2 jlist failed while reading Lite runtime topology"
PM2_JSON="$pm2_json" REQUIRED="$required" LEGACY="$legacy" python3 - <<'PY'
import json
import os

items = json.loads(os.environ["PM2_JSON"])
statuses = {}
versions = {}
declared_versions = {}
for item in items if isinstance(items, list) else []:
    name = str(item.get("name") or "")
    env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
    statuses[name] = str(env.get("status") or item.get("status") or "unknown").lower()
    versions[name] = str(env.get("version") or "").strip()
    declared_versions[name] = str(env.get("POCKETLAB_SERVICE_VERSION") or "").strip()

required = os.environ["REQUIRED"].split()
missing = [name for name in required if statuses.get(name) != "online"]
legacy = [name for name in os.environ["LEGACY"].split() if name in statuses]
bad_versions = [
    name
    for name in required
    if not versions.get(name)
    or versions.get(name, "").lower() in {"n/a", "na", "unknown"}
    or versions.get(name) != declared_versions.get(name)
]
if missing:
    raise SystemExit("required Lite PM2 services not online: " + ",".join(missing))
if legacy:
    raise SystemExit("legacy PM2 services present in Lite runtime: " + ",".join(legacy))
if bad_versions:
    raise SystemExit("Lite PM2 version projection mismatch: " + ",".join(bad_versions))
print("PASS required Lite PM2 topology online")
print("PASS every required Lite PM2 service projects its exact installed version")
print("PASS legacy Pocket Lab PM2 services absent")
PY

ts_cmd=""
if command -v tailscale-cli >/dev/null 2>&1; then
  ts_cmd=tailscale-cli
elif command -v tailscale >/dev/null 2>&1; then
  ts_cmd=tailscale
fi

if [[ -n "$ts_cmd" ]]; then
  if pgrep -f tailscaled >/dev/null 2>&1 && "$ts_cmd" ip -4 >/dev/null 2>&1; then
    echo "PASS remote access ready"
  elif pgrep -f tailscaled >/dev/null 2>&1; then
    echo "INFO Remote access not ready; tailscaled is running and Lite remains local-ready"
  else
    fail "Tailscale is installed but tailscaled is not running"
  fi
else
  echo "INFO Remote access not ready; Tailscale command is not installed"
fi

photoprism_expected=0
if [[ -s "$HOME/.pocket_lab/lite/apps/photoprism/config/photoprism.env" ||
      -s "$HOME/.pocket_lab/lite/apps/photoprism/config/install-manifest.json" ]]; then
  photoprism_expected=1
fi

if [[ "$photoprism_expected" == "1" ]]; then
  command -v proot-distro >/dev/null 2>&1 ||
    fail "PhotoPrism is installed but proot-distro is unavailable"
  proot-distro login ubuntu -- true >/dev/null 2>&1 ||
    fail "PhotoPrism is installed but Ubuntu PRoot is unavailable"
  echo "PASS PhotoPrism PRoot runtime available"

  PM2_JSON="$pm2_json" python3 - <<'PY'
import json
import os

items = json.loads(os.environ["PM2_JSON"])
for item in items if isinstance(items, list) else []:
    if item.get("name") != "pocketlab-app-photoprism":
        continue
    env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
    if str(env.get("status") or item.get("status") or "").lower() != "online":
        raise SystemExit("PhotoPrism PM2 process is not online")
    version = str(env.get("version") or "").strip()
    declared = str(env.get("POCKETLAB_SERVICE_VERSION") or "").strip()
    if not version or version.lower() in {"n/a", "na", "unknown"} or version != declared:
        raise SystemExit("PhotoPrism PM2 version projection mismatch")
    print("PASS PhotoPrism PM2 ownership and exact version projection online")
    raise SystemExit(0)
raise SystemExit("PhotoPrism is installed but its PM2 process is missing")
PY

  if ! curl -fsS --connect-timeout 1 --max-time 5 \
    http://127.0.0.1:2342/apps/photoprism/api/v1/status >/dev/null 2>&1; then
    curl -fsS --connect-timeout 1 --max-time 5 \
      http://127.0.0.1:2342/apps/photoprism/ >/dev/null ||
      fail "PhotoPrism local runtime is not reachable on 127.0.0.1:2342"
  fi

  curl -fsS --connect-timeout 1 --max-time 5 \
    http://127.0.0.1:8443/apps/photoprism/ >/dev/null ||
    fail "PhotoPrism same-origin route is not reachable through Caddy"

  echo "PASS PhotoPrism PRoot/local/same-origin runtime ready"
fi

if [[ "$mode" == "--post-reboot" ]]; then
  evidence="$HOME/pocket-lab-lite/state/runtime-reconciler/last-convergence.json"
  test -s "$evidence"
  python3 - "$evidence" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
assert data.get("bootstrap_ran") is False
assert data.get("downloads_allowed") is False
assert data.get("legacy_services_allowed") is False
print("PASS post-reboot convergence evidence is runtime-only")
PY
fi
REMOTE
}

wait_pm2_service() {
  local service="$1"
  local attempts="${2:-70}"
  ssh "$SSH_ALIAS" bash -s -- "$service" "$attempts" <<'REMOTE'
set -Eeuo pipefail
service="$1"
attempts="$2"

pm2_status() {
  local name="$1" data
  data="$(pm2 jlist 2>/dev/null || printf '[]')"
  PM2_JSON="$data" SERVICE="$name" python3 - <<'PY'
import json
import os

try:
    items = json.loads(os.environ["PM2_JSON"])
except Exception:
    items = []
for item in items if isinstance(items, list) else []:
    if item.get("name") != os.environ["SERVICE"]:
        continue
    env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
    print(str(env.get("status") or item.get("status") or "unknown").lower())
    raise SystemExit(0)
print("missing")
PY
}

for _ in $(seq 1 "$attempts"); do
  [[ "$(pm2_status "$service")" == "online" ]] && exit 0
  sleep 3
done

echo "ERROR: service did not recover: $service" >&2
exit 1
REMOTE
}

fault_pm2_service() {
  local service="$1"
  echo "FAULT stopping $service"
  ssh "$SSH_ALIAS" bash -s -- "$service" <<'REMOTE'
set -Eeuo pipefail
service="$1"
pm2 stop "$service" >/dev/null
REMOTE
  wait_pm2_service "$service"
  echo "PASS recovered $service"
}

wait_pm2_daemon_without_starting_it() {
  ssh "$SSH_ALIAS" bash -s <<'REMOTE'
set -Eeuo pipefail
pm2_home="${PM2_HOME:-$HOME/.pm2}"
for _ in $(seq 1 70); do
  pid=""
  [[ -s "$pm2_home/pm2.pid" ]] && pid="$(cat "$pm2_home/pm2.pid" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" >/dev/null 2>&1; then
    exit 0
  fi
  sleep 3
done
echo "ERROR: PM2 daemon was not restored by the external guardian" >&2
exit 1
REMOTE
}

run_faults() {
  remote_read_only --read-only

  fault_pm2_service pocket-node-agent
  fault_pm2_service caddy-proxy
  fault_pm2_service pocket-nats

  if ssh "$SSH_ALIAS" "pm2 describe pocketlab-app-photoprism >/dev/null 2>&1"; then
    fault_pm2_service pocketlab-app-photoprism
  fi

  echo "FAULT killing PM2 daemon; the external guardian must resurrect saved state"
  ssh "$SSH_ALIAS" "pm2 kill >/dev/null 2>&1 || true"
  wait_pm2_daemon_without_starting_it
  wait_pm2_service pocketlab-runtime-reconciler
  echo "PASS PM2 daemon and desired-state reconciler recovered"

  remote_read_only --read-only
}

run_remote_access_fault() {
  remote_read_only --read-only
  echo "FAULT stopping tailscaled over explicitly declared out-of-band SSH"
  ssh "$SSH_ALIAS" "pkill -f '[t]ailscaled' >/dev/null 2>&1 || true"

  for _ in $(seq 1 70); do
    if ssh "$SSH_ALIAS" "pgrep -f tailscaled >/dev/null 2>&1"; then
      echo "PASS tailscaled daemon recovered"
      remote_read_only --read-only
      return 0
    fi
    sleep 3
  done

  echo "ERROR: tailscaled did not recover" >&2
  return 1
}

case "$MODE" in
  --read-only)
    remote_read_only --read-only
    ;;
  --post-reboot)
    remote_read_only --post-reboot
    ;;
  --faults)
    run_faults
    ;;
  --remote-access-fault)
    run_remote_access_fault
    ;;
esac
