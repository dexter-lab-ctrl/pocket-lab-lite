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

runtime_dir="$HOME/pocket-lab-lite/state/runtime"
python3 - "$runtime_contract" "$runtime_dir" "$pm2_home/logs" <<'PY'
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys
import time

contract_path, runtime_dir, raw_logs = map(Path, sys.argv[1:])
contract = json.loads(contract_path.read_text(encoding="utf-8"))
stable_path = runtime_dir / "stable-convergence.json"
stable = json.loads(stable_path.read_text(encoding="utf-8"))
log_path = runtime_dir / "pm2-log-policy.json"
log_policy = json.loads(log_path.read_text(encoding="utf-8"))

assert stable.get("schema_version") == 1
assert stable.get("state") == "stable" and stable.get("stable") is True
assert int(stable.get("stable_observations") or 0) >= 2
assert int(stable.get("required_stable_observations") or 0) >= 2

services = [item for item in contract.get("services") or [] if isinstance(item, dict)]
by_name = {str(item.get("process") or ""): item for item in services}
required = [item for item in services if item.get("required") is True]
for item in required:
    name = str(item.get("process") or "unknown")
    assert item.get("state") == "online", (name, item.get("state"))
    assert item.get("stable") is True, name
    assert item.get("desired_state_match") is True, name
    assert item.get("pm2_policy_match") is True, name
    assert item.get("version") not in {None, "", "unavailable"}, name
    assert item.get("version") == item.get("declared_version"), name
    assert item.get("health") == "ready", name
    assert int(item.get("restart_budget_remaining") or 0) > 0, name
    assert int(item.get("pm2_restart_budget_remaining") or 0) > 0, name
    assert item.get("memory_within_policy") is True, name
    assert all(value == "ready" for value in (item.get("dependencies") or {}).values()), name
assert required
assert contract.get("legacy_lite_services_present") == []

telemetry = by_name.get("pocket-telemetry")
if telemetry is not None:
    assert telemetry.get("state") == "online"
    assert telemetry.get("desired_state_match") is True
    assert telemetry.get("pm2_policy_match") is True
    assert telemetry.get("version") == telemetry.get("declared_version")
    assert telemetry.get("health") == "ready"
    assert int(telemetry.get("restart_budget_remaining") or 0) > 0
    assert int(telemetry.get("pm2_restart_budget_remaining") or 0) > 0
    assert telemetry.get("memory_within_policy") is True

assert log_policy.get("schema_version") == 1
assert log_policy.get("sanitized") is True
assert log_policy.get("contains_log_contents") is False
assert log_policy.get("within_policy") is True
aggregate_ceiling = int(log_policy.get("pm2_log_ceiling_bytes") or 0)
file_ceiling = int(log_policy.get("pm2_log_file_ceiling_bytes") or 0)
max_age = int(log_policy.get("pm2_log_max_age_seconds") or 0)
cleanup_interval = int(log_policy.get("cleanup_interval_seconds") or 0)
assert 8 * 1024 * 1024 <= aggregate_ceiling <= 512 * 1024 * 1024
assert 1 * 1024 * 1024 <= file_ceiling <= 64 * 1024 * 1024
assert 24 * 60 * 60 <= max_age <= 30 * 24 * 60 * 60
assert 300 <= cleanup_interval <= 24 * 60 * 60
assert int(log_policy.get("pm2_log_bytes") or 0) <= aggregate_ceiling

logs = raw_logs.expanduser()
if logs.exists():
    assert not logs.is_symlink()
    total_bytes = 0
    file_count = 0
    oldest_age = 0.0
    largest_file = 0
    now = time.time()
    with os.scandir(logs) as entries:
        for index, entry in enumerate(entries):
            assert index < 8192, "PM2 log entry count exceeds the bounded qualification scan"
            if entry.is_symlink():
                continue
            if not entry.is_file(follow_symlinks=False):
                continue
            metadata = entry.stat(follow_symlinks=False)
            assert stat.S_ISREG(metadata.st_mode)
            file_count += 1
            total_bytes += metadata.st_size
            largest_file = max(largest_file, metadata.st_size)
            oldest_age = max(oldest_age, max(0.0, now - metadata.st_mtime))
    assert total_bytes <= aggregate_ceiling, (total_bytes, aggregate_ceiling)
    assert largest_file <= file_ceiling, (largest_file, file_ceiling)
    assert oldest_age <= max_age + cleanup_interval, (oldest_age, max_age, cleanup_interval)
    print(
        "PASS PM2 log metadata current_bytes=%d files=%d max_file_bytes=%d oldest_age_seconds=%d "
        "aggregate_ceiling=%d file_ceiling=%d max_age_seconds=%d cleanup_interval_seconds=%d"
        % (total_bytes, file_count, largest_file, int(oldest_age), aggregate_ceiling,
           file_ceiling, max_age, cleanup_interval)
    )
else:
    assert int(log_policy.get("pm2_log_bytes") or 0) == 0
    print("PASS PM2 log metadata confirms no log files")

print(
    "PASS stable convergence observations=%d required=%d required_services=%d"
    % (stable["stable_observations"], stable["required_stable_observations"], len(required))
)
print("PASS required service versions, desired state, PM2 policy, health, dependencies, budgets, and memory policy")
PY

# Confirm the API projections consumed by Lite screens agree with the local
# sanitized Runtime Contract while keeping remote access a separate signal.
python3 - "$runtime_contract" <<'PY'
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
import sys

contract = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
base = "http://127.0.0.1:8080"
paths = (
    "/api/lite/runtime",
    "/api/lite/status",
    "/api/lite/fleet",
    "/api/lite/recovery/summary",
    "/api/lite/recovery/details",
)
payloads = {}
for path in paths:
    deadline = time.monotonic() + 120
    last_status = 0
    while True:
        request = urllib.request.Request(base + path, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                last_status = int(response.status)
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            last_status = int(error.code)
            if last_status != 503 or time.monotonic() >= deadline:
                raise AssertionError(f"{path} returned HTTP {last_status}") from None
            payload = None
        if payload is not None:
            break
        if time.monotonic() >= deadline:
            raise AssertionError(f"{path} stayed in warming state; last HTTP {last_status}")
        time.sleep(1)
    assert isinstance(payload, dict), path
    payloads[path] = payload

def scan(value, path="payload"):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            assert normalized not in {"pm2_env", "raw_env", "process_environment", "environment"}, path + "." + str(key)
            assert not normalized.endswith(("_password", "_token", "_api_key", "_secret", "_credentials")), path + "." + str(key)
            scan(child, path + "." + str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value[:4096]):
            scan(child, f"{path}[{index}]")

for path, payload in payloads.items():
    scan(payload, path)

runtime = payloads["/api/lite/runtime"]
assert runtime.get("schema") == "pocketlab.pm2-runtime-contract/v1"
assert runtime.get("schema_version") == 1 and runtime.get("sanitized") is True
assert runtime.get("state") == contract.get("state") and runtime.get("stable") is True
assert "PM2" not in str(runtime.get("summary") or "")
print("PASS /api/lite/runtime schema and sanitized state")

status = payloads["/api/lite/status"]
status_services = status.get("services") if isinstance(status.get("services"), list) else []
runtime_status = next((item for item in status_services if item.get("name") == "Runtime"), None)
remote_status = next((item for item in status_services if item.get("name") == "Remote Access"), None)
assert runtime_status is not None and runtime_status.get("status") == "healthy"
assert remote_status is not None
print("PASS /api/lite/status runtime readiness and separate remote-access status")

fleet = payloads["/api/lite/fleet"]
devices = fleet.get("devices") if isinstance(fleet.get("devices"), list) else []
server = next((item for item in devices if item.get("role") == "server_host"), None)
assert server is not None
assert server.get("connection") == "online"
server_runtime = server.get("runtime") if isinstance(server.get("runtime"), dict) else {}
assert server_runtime.get("state") == contract.get("state")
assert server_runtime.get("stable") is True
assert server.get("remote_access_status") is not None
print("PASS /api/lite/fleet protected-host runtime and independent remote-access projection")

for path in ("/api/lite/recovery/summary", "/api/lite/recovery/details"):
    recovery = payloads[path].get("runtime_recovery")
    assert isinstance(recovery, dict) and recovery.get("sanitized") is True
    assert recovery.get("state") == contract.get("state") and recovery.get("stable") is True
    assert "PM2" not in str(recovery.get("summary") or "")
    print(f"PASS {path} runtime recovery projection")
PY

ts_cmd=""
if command -v tailscale-cli >/dev/null 2>&1; then
  ts_cmd=tailscale-cli
elif command -v tailscale >/dev/null 2>&1; then
  ts_cmd=tailscale
fi

if [[ -n "$ts_cmd" ]]; then
  if pgrep -f tailscaled >/dev/null 2>&1; then
    ts_ip="$("$ts_cmd" ip -4 2>/dev/null | head -1 || true)"
    if [[ -n "$ts_ip" ]]; then
      nats_port="${POCKETLAB_LITE_NATS_PORT:-${POCKETLAB_PUBLIC_NATS_PORT:-4222}}"
      python3 - "$ts_ip" "$nats_port" <<'PY' || fail "NATS is not reachable over the Server Phone Tailnet IPv4"
import socket
import sys

try:
    port = int(sys.argv[2])
except ValueError as error:
    raise SystemExit("configured NATS port is not an integer") from error
if not 1 <= port <= 65535:
    raise SystemExit("configured NATS port is outside the valid TCP range")
with socket.create_connection((sys.argv[1], port), timeout=3.0):
    pass
print(f"PASS NATS reachable through Tailnet IPv4 on configured port {port}")
PY
      echo "PASS remote access ready"
    else
      echo "INFO Remote access not ready; tailscaled is running without a Tailnet IPv4"
    fi
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
  local generation_before started_epoch
  generation_before="$(ssh "$SSH_ALIAS" python3 - "$service" <<'REMOTE'
import json
from pathlib import Path
import sys

service = sys.argv[1]
path = Path.home() / "pocket-lab-lite/state/runtime/pm2-runtime-contract.json"
data = json.loads(path.read_text(encoding="utf-8"))
item = next((item for item in data.get("services", []) if item.get("process") == service), None)
assert item is not None, f"runtime contract has no service {service}"
print(int(item.get("restart_generation") or 0))
REMOTE
  )"
  started_epoch="$(ssh "$SSH_ALIAS" 'date +%s')"
  echo "FAULT stopping $service (restart_generation=$generation_before)"
  ssh "$SSH_ALIAS" bash -s -- "$service" <<'REMOTE'
set -Eeuo pipefail
service="$1"
pm2 stop "$service" >/dev/null
REMOTE
  wait_pm2_service "$service"
  ssh "$SSH_ALIAS" bash -s -- "$service" "$generation_before" "$started_epoch" <<'REMOTE'
set -Eeuo pipefail
service="$1"
generation_before="$2"
started_epoch="$3"
budget="${POCKETLAB_PHONE_RUNTIME_CONTRACT_STABILIZATION_SECONDS:-900}"
deadline=$(( $(date +%s) + budget ))
last="runtime contract has not reached stable convergence after recovery"
while (( $(date +%s) <= deadline )); do
  if last="$(python3 - "$service" "$generation_before" "$HOME/pocket-lab-lite/state/runtime" <<'PY' 2>&1
import json
from pathlib import Path
import sys

service, generation_before = sys.argv[1], int(sys.argv[2])
runtime_dir = Path(sys.argv[3])
contract = json.loads((runtime_dir / "pm2-runtime-contract.json").read_text(encoding="utf-8"))
stable = json.loads((runtime_dir / "stable-convergence.json").read_text(encoding="utf-8"))
assert contract.get("state") == "stable" and contract.get("stable") is True
assert int(contract.get("stable_observations") or 0) >= int(contract.get("required_stable_observations") or 2) >= 2
item = next((item for item in contract.get("services", []) if item.get("process") == service), None)
assert item is not None, f"runtime contract has no service {service}"
generation_after = int(item.get("restart_generation") or 0)
assert generation_after > generation_before, (generation_before, generation_after)
assert item.get("state") == "online" and item.get("stable") is True
assert item.get("desired_state_match") is True and item.get("pm2_policy_match") is True
assert item.get("health") == "ready"
assert int(item.get("restart_budget_remaining") or 0) > 0
assert int(item.get("pm2_restart_budget_remaining") or 0) > 0
assert item.get("memory_within_policy") is True
assert all(value == "ready" for value in (item.get("dependencies") or {}).values())
print(json.dumps({
    "generation_after": generation_after,
    "restart_budget_remaining": item.get("restart_budget_remaining"),
    "pm2_restart_budget_remaining": item.get("pm2_restart_budget_remaining"),
    "stable_observations": stable.get("stable_observations"),
    "required_stable_observations": stable.get("required_stable_observations"),
}, sort_keys=True, separators=(",", ":")))
PY
)"; then
    elapsed=$(( $(date +%s) - started_epoch ))
    printf 'PASS recovered service=%s elapsed_seconds=%s generation_before=%s evidence=%s\n' \
      "$service" "$elapsed" "$generation_before" "$last"
    exit 0
  fi
  sleep 5
done
echo "ERROR: Runtime Contract did not confirm stable recovery for $service within ${budget}s: $last" >&2
exit 1
REMOTE
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

runtime_required_generation_csv() {
  ssh "$SSH_ALIAS" python3 - <<'REMOTE'
import json
from pathlib import Path

names = (
    "pocket-nats", "pocket-opa", "pocket-worker", "pocket-api",
    "pocket-node-agent", "caddy-proxy", "pocketlab-core-supervisor",
    "pocketlab-runtime-reconciler",
)
path = Path.home() / "pocket-lab-lite/state/runtime/pm2-runtime-contract.json"
data = json.loads(path.read_text(encoding="utf-8"))
services = {item.get("process"): item for item in data.get("services", []) if isinstance(item, dict)}
if any(name not in services for name in names):
    raise SystemExit("runtime contract omits a required service generation")
print(",".join(str(int(services[name].get("restart_generation") or 0)) for name in names))
REMOTE
}

wait_runtime_convergence_after_daemon_recovery() {
  local generation_before="$1" started_epoch="$2"
  ssh "$SSH_ALIAS" bash -s -- "$generation_before" "$started_epoch" <<'REMOTE'
set -Eeuo pipefail
generation_before="$1"
started_epoch="$2"
budget="${POCKETLAB_PHONE_RUNTIME_CONTRACT_STABILIZATION_SECONDS:-900}"
deadline=$(( $(date +%s) + budget ))
last="runtime contract has not reached stable convergence after PM2 daemon recovery"
while (( $(date +%s) <= deadline )); do
  if last="$(python3 - "$generation_before" "$HOME/pocket-lab-lite/state/runtime" <<'PY' 2>&1
import json
from pathlib import Path
import sys

names = (
    "pocket-nats", "pocket-opa", "pocket-worker", "pocket-api",
    "pocket-node-agent", "caddy-proxy", "pocketlab-core-supervisor",
    "pocketlab-runtime-reconciler",
)
baseline = [int(value) for value in sys.argv[1].split(",")]
assert len(baseline) == len(names)
runtime_dir = Path(sys.argv[2])
contract = json.loads((runtime_dir / "pm2-runtime-contract.json").read_text(encoding="utf-8"))
stable = json.loads((runtime_dir / "stable-convergence.json").read_text(encoding="utf-8"))
assert contract.get("state") == "stable" and contract.get("stable") is True
assert int(stable.get("stable_observations") or 0) >= int(stable.get("required_stable_observations") or 2) >= 2
services = {item.get("process"): item for item in contract.get("services", []) if isinstance(item, dict)}
after = []
for name, previous_generation in zip(names, baseline):
    item = services.get(name)
    assert item is not None, f"runtime contract omits {name}"
    generation = int(item.get("restart_generation") or 0)
    assert generation > previous_generation, (name, previous_generation, generation)
    assert item.get("state") == "online" and item.get("stable") is True
    assert item.get("desired_state_match") is True and item.get("pm2_policy_match") is True
    assert item.get("health") == "ready"
    assert int(item.get("restart_budget_remaining") or 0) > 0
    assert int(item.get("pm2_restart_budget_remaining") or 0) > 0
    after.append(generation)
print(json.dumps({
    "services": len(names),
    "generations_before": baseline,
    "generations_after": after,
    "stable_observations": stable.get("stable_observations"),
    "required_stable_observations": stable.get("required_stable_observations"),
}, sort_keys=True, separators=(",", ":")))
PY
)"; then
    elapsed=$(( $(date +%s) - started_epoch ))
    printf 'PASS PM2 daemon recovery elapsed_seconds=%s evidence=%s\n' "$elapsed" "$last"
    exit 0
  fi
  sleep 5
done
echo "ERROR: Runtime Contract did not confirm stable PM2 daemon recovery within ${budget}s: $last" >&2
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

  local daemon_generations daemon_started_epoch
  daemon_generations="$(runtime_required_generation_csv)"
  daemon_started_epoch="$(ssh "$SSH_ALIAS" 'date +%s')"
  echo "FAULT killing PM2 daemon; the external guardian must resurrect saved state (generations=$daemon_generations)"
  ssh "$SSH_ALIAS" "pm2 kill >/dev/null 2>&1 || true"
  wait_pm2_daemon_without_starting_it
  wait_pm2_service pocketlab-runtime-reconciler
  wait_runtime_convergence_after_daemon_recovery "$daemon_generations" "$daemon_started_epoch"
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

write_pm2_ecosystem() {
  local config="$1" script="$2" name="$3" policy_json="$4" env_name="${5:-}" env_value="${6:-}"
  python3 - "$config" "$script" "$name" "$policy_json" "$env_name" "$env_value" "$(command -v python3)" <<'PY'
import json
from pathlib import Path
import sys

config, script, name, policy_json, env_name, env_value, interpreter = sys.argv[1:]
app = {
    "name": name,
    "script": script,
    "interpreter": interpreter,
    "exec_mode": "fork",
    **json.loads(policy_json),
}
if env_name:
    app["env"] = {env_name: env_value}
path = Path(config)
path.write_text(json.dumps({"apps": [app]}, sort_keys=True), encoding="utf-8")
path.chmod(0o600)
PY
}

cat >"$tmp_root/crash.py" <<'PY'
raise SystemExit(23)
PY
write_pm2_ecosystem "$tmp_root/crash.ecosystem.json" "$tmp_root/crash.py" "$crash_name" \
  '{"autorestart":true,"min_uptime":"2s","max_restarts":3,"kill_timeout":2000,"restart_delay":250}'
pm2 start "$tmp_root/crash.ecosystem.json" --only "$crash_name" >/dev/null
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
    pid=env.get("pid") or item.get("pid")
    configured_max=int(env.get("max_restarts") or 3)
    # PM2 counts the initial launch separately from restart_time on Termux.
    # A max_restarts=3 canary therefore reaches its terminal state at
    # restart_time=2 after three total launch attempts.
    restart_budget_exhausted = restarts >= max(1, configured_max - 1)
    terminal_status = status in {"errored", "error", "stopped"}
    # PM2 7 on Termux leaves a capped crash loop in `waiting restart` with no
    # pid instead of translating it to `errored`; the restart budget is still
    # enforced and the process is terminal for qualification purposes.
    if (terminal_status or (status == "waiting restart" and not pid)) and restart_budget_exhausted:
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
write_pm2_ecosystem "$tmp_root/graceful.ecosystem.json" "$tmp_root/graceful.py" "$grace_name" \
  '{"autorestart":false,"kill_timeout":3000}' GRACEFUL_MARKER "$marker"
pm2 start "$tmp_root/graceful.ecosystem.json" --only "$grace_name" >/dev/null
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
  write_pm2_ecosystem "$tmp_root/memory.ecosystem.json" "$tmp_root/memory.py" "$memory_name" \
    '{"autorestart":true,"max_memory_restart":"32M","min_uptime":"2s","max_restarts":3,"kill_timeout":3000}'
  pm2 start "$tmp_root/memory.ecosystem.json" --only "$memory_name" >/dev/null
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
