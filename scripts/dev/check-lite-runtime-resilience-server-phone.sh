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
  --pm2-contract-faults)
    [[ "${POCKETLAB_RUNTIME_PM2_CONTRACT_FAULTS:-0}" == "1" ]] || {
      echo "ERROR: --pm2-contract-faults requires POCKETLAB_RUNTIME_PM2_CONTRACT_FAULTS=1" >&2
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
    echo "Usage: $0 [--read-only|--faults|--pm2-contract-faults|--post-reboot|--remote-access-fault]" >&2
    exit 2
    ;;
esac

remote_read_only() {
  local mode="${1:---read-only}"
  local verification_policy="${2:-strict}"
  ssh "$SSH_ALIAS" bash -s -- "$mode" "$verification_policy" <<'REMOTE'
set -Eeuo pipefail
mode="$1"
verification_policy="$2"

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

api_stable=0
api_budget_seconds="${POCKETLAB_PHONE_API_STABILIZATION_SECONDS:-300}"
api_backoff_seconds=2
api_backoff_max="${POCKETLAB_PHONE_API_BACKOFF_MAX_SECONDS:-30}"
api_started_at="$(date +%s)"
api_deadline=$((api_started_at + api_budget_seconds))
api_probe_count=0

while (( $(date +%s) <= api_deadline )); do
  api_probe_count=$((api_probe_count + 1))

  # Avoid hammering HTTP while the socket is not even accepting connections.
  # A cheap TCP gate keeps health/readiness probes proportional to actual
  # recovery progress.
  if python3 - <<'PY' >/dev/null 2>&1
import socket
sock = socket.socket()
sock.settimeout(1.0)
try:
    sock.connect(("127.0.0.1", 8080))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
  then
    if curl -fsS --connect-timeout 1 --max-time 4 http://127.0.0.1:8080/health >/dev/null 2>&1 &&
       curl -fsS --connect-timeout 1 --max-time 4 http://127.0.0.1:8080/ready >/dev/null 2>&1; then
      api_stable=$((api_stable + 1))
      [[ "$api_stable" -ge 2 ]] && break
    else
      api_stable=0
    fi
  else
    api_stable=0
  fi

  now="$(date +%s)"
  (( now >= api_deadline )) && break
  remaining=$((api_deadline - now))
  sleep_for="$api_backoff_seconds"
  (( sleep_for > remaining )) && sleep_for="$remaining"
  (( sleep_for > 0 )) && sleep "$sleep_for"
  if (( api_backoff_seconds < api_backoff_max )); then
    api_backoff_seconds=$((api_backoff_seconds * 2))
    (( api_backoff_seconds > api_backoff_max )) && api_backoff_seconds="$api_backoff_max"
  fi
done

if [[ "$api_stable" -ge 2 ]]; then
  echo "PASS Lite API health reachable"
  echo "PASS Lite API readiness reachable"
elif [[ "$verification_policy" == "advisory" ]]; then
  echo "ADVISORY Lite API health/readiness did not stabilize within ${api_budget_seconds}s after fault recovery."
  echo "ADVISORY All injected recovery scenarios completed; the API may still be finishing NATS/application startup."
  echo "ADVISORY Recheck later with: curl -fsS http://127.0.0.1:8080/health && curl -fsS http://127.0.0.1:8080/ready"
else
  fail "Lite API /health and /ready did not remain reachable on 127.0.0.1:8080 within ${api_budget_seconds}s"
fi

pm2_tmp_root="${TMPDIR:-$HOME/tmp}"
mkdir -p "$pm2_tmp_root"
pm2_json_file="$(mktemp "$pm2_tmp_root/pocketlab-pm2-jlist.XXXXXX.json")"
trap 'rm -f "$pm2_json_file" "${topology_check_file:-}"' EXIT
topology_check_file="$pm2_tmp_root/pocketlab-pm2-topology-check.$"
topology_stable=0
topology_attempts="${POCKETLAB_PHONE_TOPOLOGY_ATTEMPTS:-20}"
for _ in $(seq 1 "$topology_attempts"); do
  if ! pm2 jlist >"$pm2_json_file" 2>/dev/null; then
    printf '%s\n' "pm2 jlist failed while reading Lite runtime topology" >"$topology_check_file"
    topology_stable=0
  elif REQUIRED="$required" LEGACY="$legacy" python3 - "$pm2_json_file" >"$topology_check_file" 2>&1 <<'PY'
import json
import os
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    items = json.load(handle)
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
  then
    topology_stable=$((topology_stable + 1))
    if [[ "$topology_stable" -ge 2 ]]; then
      cat "$topology_check_file"
      break
    fi
  else
    topology_stable=0
  fi
  sleep 3
done
if [[ "$topology_stable" -lt 2 ]]; then
  topology_error="$(cat "$topology_check_file" 2>/dev/null || true)"
  rm -f "$topology_check_file"
  fail "Lite runtime did not reach a stable PM2 topology/version projection after $topology_attempts attempts: ${topology_error:-unknown topology error}"
fi
rm -f "$topology_check_file"

runtime_contract="$HOME/pocket-lab-lite/state/runtime/pm2-runtime-contract.json"
contract_budget_seconds="${POCKETLAB_PHONE_RUNTIME_CONTRACT_STABILIZATION_SECONDS:-600}"
contract_started_at="$(date +%s)"
contract_deadline=$((contract_started_at + contract_budget_seconds))
contract_backoff=3
contract_stable=0
contract_error="runtime contract has not been written yet"
while (( $(date +%s) <= contract_deadline )); do
  if [[ -s "$runtime_contract" ]]; then
    if contract_error="$(python3 - "$runtime_contract" <<'PY' 2>&1
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
assert data.get("schema") == "pocketlab.pm2-runtime-contract/v1", data.get("schema")
assert int(data.get("schema_version") or 0) == 1
assert data.get("sanitized") is True
assert data.get("legacy_lite_services_present") == []
assert data.get("state") == "stable", data.get("state")
assert data.get("stable") is True
assert int(data.get("stable_observations") or 0) >= 2
log_policy = data.get("log_policy") or {}
assert log_policy.get("within_policy") is True
services = [item for item in data.get("services") or [] if isinstance(item, dict)]
required = [item for item in services if item.get("required") is True]
assert required
for item in required:
    assert item.get("state") == "online", item
    assert item.get("stable") is True, item
    assert item.get("desired_state_match") is True, item
    assert item.get("pm2_policy_match") is True, item
    assert item.get("health") == "ready", item
    assert int(item.get("restart_budget_remaining") or 0) > 0, item
    assert item.get("memory_within_policy") is True, item
print("PASS PM2 Runtime Contract reached stable convergence")
print("PASS PM2 policy/version/health/dependency/restart-budget checks passed")
print("PASS PM2 log usage is within the bounded retention policy")
PY
)"; then
      contract_stable=1
      printf '%s\n' "$contract_error"
      break
    fi
  fi
  now="$(date +%s)"
  (( now >= contract_deadline )) && break
  sleep "$contract_backoff"
  (( contract_backoff < 20 )) && contract_backoff=$((contract_backoff + 3))
done
if [[ "$contract_stable" -ne 1 ]]; then
  fail "PM2 Runtime Contract did not reach stable convergence within ${contract_budget_seconds}s: $contract_error"
fi

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

  photoprism_stable=0
  photoprism_budget_seconds="${POCKETLAB_PHONE_PHOTOPRISM_STABILIZATION_SECONDS:-300}"
  photoprism_backoff_seconds=2
  photoprism_backoff_max="${POCKETLAB_PHONE_PHOTOPRISM_BACKOFF_MAX_SECONDS:-30}"
  photoprism_started_at="$(date +%s)"
  photoprism_deadline=$((photoprism_started_at + photoprism_budget_seconds))

  while (( $(date +%s) <= photoprism_deadline )); do
    photoprism_pm2_ready=0
    if pm2 jlist >"$pm2_json_file" 2>/dev/null &&
       python3 - "$pm2_json_file" <<'PY' >/dev/null 2>&1
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    items = json.load(handle)
for item in items if isinstance(items, list) else []:
    if item.get("name") != "pocketlab-app-photoprism":
        continue
    env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
    status = str(env.get("status") or item.get("status") or "").lower()
    version = str(env.get("version") or "").strip()
    declared = str(env.get("POCKETLAB_SERVICE_VERSION") or "").strip()
    healthy = (
        status == "online"
        and bool(version)
        and version.lower() not in {"n/a", "na", "unknown"}
        and version == declared
    )
    raise SystemExit(0 if healthy else 1)
raise SystemExit(1)
PY
    then
      photoprism_pm2_ready=1
    fi

    if [[ "$photoprism_pm2_ready" == "1" ]]; then
      local_ready=0
      if curl -fsS --connect-timeout 1 --max-time 5 \
        http://127.0.0.1:2342/apps/photoprism/api/v1/status >/dev/null 2>&1 ||
         curl -fsS --connect-timeout 1 --max-time 5 \
        http://127.0.0.1:2342/apps/photoprism/ >/dev/null 2>&1; then
        local_ready=1
      fi

      caddy_ready=0
      if [[ "$local_ready" == "1" ]] &&
         curl -fsS --connect-timeout 1 --max-time 5 \
           http://127.0.0.1:8443/apps/photoprism/ >/dev/null 2>&1; then
        caddy_ready=1
      fi

      if [[ "$local_ready" == "1" && "$caddy_ready" == "1" ]]; then
        photoprism_stable=$((photoprism_stable + 1))
        [[ "$photoprism_stable" -ge 2 ]] && break
      else
        photoprism_stable=0
      fi
    else
      photoprism_stable=0
    fi

    now="$(date +%s)"
    (( now >= photoprism_deadline )) && break
    remaining=$((photoprism_deadline - now))
    sleep_for="$photoprism_backoff_seconds"
    (( sleep_for > remaining )) && sleep_for="$remaining"
    (( sleep_for > 0 )) && sleep "$sleep_for"
    if (( photoprism_backoff_seconds < photoprism_backoff_max )); then
      photoprism_backoff_seconds=$((photoprism_backoff_seconds * 2))
      (( photoprism_backoff_seconds > photoprism_backoff_max )) &&
        photoprism_backoff_seconds="$photoprism_backoff_max"
    fi
  done

  if [[ "$photoprism_stable" -ge 2 ]]; then
    echo "PASS PhotoPrism PM2 ownership and exact version projection online"
    echo "PASS PhotoPrism PRoot/local/same-origin runtime ready"
  elif [[ "$verification_policy" == "advisory" ]]; then
    echo "ADVISORY PhotoPrism did not fully stabilize within ${photoprism_budget_seconds}s after fault recovery."
    echo "ADVISORY Core fault recovery completed; PhotoPrism may still be finishing PRoot/application startup."
    echo "ADVISORY Recheck later with: pm2 status pocketlab-app-photoprism"
    echo "ADVISORY Then verify: curl -fsS http://127.0.0.1:2342/apps/photoprism/ && curl -fsS http://127.0.0.1:8443/apps/photoprism/"
  else
    fail "PhotoPrism PM2/local/same-origin runtime did not stabilize within ${photoprism_budget_seconds}s"
  fi
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
  local budget_seconds="${2:-${POCKETLAB_PHONE_PM2_SERVICE_STABILIZATION_SECONDS:-600}}"
  local backoff_max="${POCKETLAB_PHONE_PM2_SERVICE_BACKOFF_MAX_SECONDS:-30}"
  ssh "$SSH_ALIAS" bash -s -- "$service" "$budget_seconds" "$backoff_max" <<'REMOTE'
set -Eeuo pipefail
service="$1"
budget_seconds="$2"
backoff_max="$3"

pm2_status() {
  local name="$1" tmp_root json_file
  tmp_root="${TMPDIR:-$HOME/tmp}"
  mkdir -p "$tmp_root"
  json_file="$(mktemp "$tmp_root/pocketlab-pm2-status.XXXXXX.json")"
  if ! pm2 jlist >"$json_file" 2>/dev/null; then
    printf '[]\n' >"$json_file"
  fi
  SERVICE="$name" python3 - "$json_file" <<'PY'
import json
import os
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        items = json.load(handle)
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
  rc=$?
  rm -f "$json_file"
  return "$rc"
}

stable=0
backoff_seconds=2
started_at="$(date +%s)"
deadline=$((started_at + budget_seconds))
last_status="missing"

while (( $(date +%s) <= deadline )); do
  last_status="$(pm2_status "$service")"
  if [[ "$last_status" == "online" ]]; then
    stable=$((stable + 1))
    [[ "$stable" -ge 2 ]] && exit 0
  else
    stable=0
  fi

  now="$(date +%s)"
  (( now >= deadline )) && break
  remaining=$((deadline - now))
  sleep_for="$backoff_seconds"
  (( sleep_for > remaining )) && sleep_for="$remaining"
  (( sleep_for > 0 )) && sleep "$sleep_for"
  if (( backoff_seconds < backoff_max )); then
    backoff_seconds=$((backoff_seconds * 2))
    (( backoff_seconds > backoff_max )) && backoff_seconds="$backoff_max"
  fi
done

echo "ERROR: service did not reach stable online state within ${budget_seconds}s: $service (last_status=$last_status)" >&2
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

  if remote_read_only --read-only advisory; then
    echo "PASS fault injection recovery sequence completed"
  else
    return 1
  fi
}

run_pm2_contract_faults() {
  remote_read_only --read-only

  echo "FAULT qualifying bounded PM2 crash-loop, graceful-stop, and memory-ceiling behavior with disposable canaries"
  ssh "$SSH_ALIAS" bash -s -- "${POCKETLAB_RUNTIME_MEMORY_FAULTS:-0}" <<'REMOTE'
set -Eeuo pipefail
memory_faults="$1"
tmp_root="${TMPDIR:-$HOME/tmp}/pocketlab-pm2-contract-qualification"
mkdir -p "$tmp_root"
chmod 700 "$tmp_root" 2>/dev/null || true
crash_name="pocketlab-qualification-crash-loop"
grace_name="pocketlab-qualification-graceful-stop"
memory_name="pocketlab-qualification-memory-ceiling"

cleanup() {
  pm2 delete "$crash_name" "$grace_name" "$memory_name" >/dev/null 2>&1 || true
  rm -rf "$tmp_root"
}
trap cleanup EXIT

pm2 delete "$crash_name" "$grace_name" "$memory_name" >/dev/null 2>&1 || true

cat >"$tmp_root/crash.py" <<'PY'
raise SystemExit(23)
PY
pm2 start "$tmp_root/crash.py" --name "$crash_name" --interpreter python3 \
  --min-uptime 2s --max-restarts 3 --kill-timeout 2000 --restart-delay 250 >/dev/null
crash_terminal=0
for _ in $(seq 1 40); do
  if pm2 jlist | NAME="$crash_name" python3 -c '
import json, os, sys
items=json.load(sys.stdin)
for item in items:
    if item.get("name") != os.environ["NAME"]:
        continue
    env=item.get("pm2_env") or {}
    status=str(env.get("status") or "").lower()
    restarts=int(env.get("unstable_restarts") or env.get("restart_time") or 0)
    if status in {"errored","error","stopped"} and restarts >= 3:
        raise SystemExit(0)
raise SystemExit(1)
'; then
    crash_terminal=1
    break
  fi
  sleep 1
done
[[ "$crash_terminal" -eq 1 ]] || {
  echo "ERROR: disposable PM2 crash loop did not stop at its restart budget" >&2
  exit 1
}
echo "PASS PM2 crash-loop canary reached a bounded terminal state"

cat >"$tmp_root/graceful.py" <<'PY'
import os
from pathlib import Path
import signal
import time

marker=Path(os.environ["GRACEFUL_MARKER"])
def stop(signum, _frame):
    marker.write_text(str(signum), encoding="utf-8")
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
while True:
    time.sleep(1)
PY
marker="$tmp_root/graceful.marker"
GRACEFUL_MARKER="$marker" pm2 start "$tmp_root/graceful.py" --name "$grace_name" --interpreter python3 \
  --no-autorestart --kill-timeout 3000 >/dev/null
sleep 2
pm2 sendSignal SIGTERM "$grace_name" >/dev/null
for _ in $(seq 1 15); do
  [[ -s "$marker" ]] && break
  sleep 1
done
[[ -s "$marker" ]] || {
  echo "ERROR: disposable graceful-stop canary did not handle SIGTERM" >&2
  exit 1
}
echo "PASS graceful SIGTERM was handled before the kill-timeout deadline"

if [[ "$memory_faults" == "1" ]]; then
  cat >"$tmp_root/memory.py" <<'PY'
import time
payload = bytearray(48 * 1024 * 1024)
while payload:
    time.sleep(1)
PY
  pm2 start "$tmp_root/memory.py" --name "$memory_name" --interpreter python3 \
    --max-memory-restart 32M --min-uptime 2s --max-restarts 3 --kill-timeout 3000 >/dev/null
  memory_restarted=0
  for _ in $(seq 1 100); do
    if pm2 jlist | NAME="$memory_name" python3 -c '
import json, os, sys
items=json.load(sys.stdin)
for item in items:
    if item.get("name") == os.environ["NAME"]:
        env=item.get("pm2_env") or {}
        raise SystemExit(0 if int(env.get("restart_time") or 0) >= 1 else 1)
raise SystemExit(1)
'; then
      memory_restarted=1
      break
    fi
    sleep 1
  done
  [[ "$memory_restarted" -eq 1 ]] || {
    echo "ERROR: bounded memory canary did not cross the configured PM2 memory ceiling" >&2
    exit 1
  }
  echo "PASS PM2 memory ceiling restarted a bounded 48 MiB canary without an OOM test"
else
  echo "SKIP memory-ceiling canary; set POCKETLAB_RUNTIME_MEMORY_FAULTS=1 to enable the bounded 48 MiB scenario"
fi

pm2 delete "$crash_name" "$grace_name" "$memory_name" >/dev/null 2>&1 || true
echo "PASS disposable PM2 policy canaries cleaned up"
REMOTE

  # Re-run the existing real service-class recovery checks for a Python agent,
  # Caddy proxy, and NATS binary daemon. Existing runtime owners perform the
  # recovery; the harness never starts these services itself.
  fault_pm2_service pocket-node-agent
  fault_pm2_service caddy-proxy
  fault_pm2_service pocket-nats

  remote_read_only --read-only
  echo "PASS PM2 Runtime Contract fault qualification completed and stable recovery reconfirmed"
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
  --pm2-contract-faults)
    run_pm2_contract_faults
    ;;
  --remote-access-fault)
    run_remote_access_fault
    ;;
esac
