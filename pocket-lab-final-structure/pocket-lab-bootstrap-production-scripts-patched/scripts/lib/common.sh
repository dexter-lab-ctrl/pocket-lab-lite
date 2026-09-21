#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Pocket Lab Day-0 common runtime helpers.
# Goals: Android/Termux compatibility, idempotency, rerun safety, and readable logs.

is_termux() { [[ -n "${TERMUX_VERSION:-}" || -d "/data/data/com.termux/files/usr" ]]; }

if is_termux; then
  export HOME="${HOME:-/data/data/com.termux/files/home}"
  export PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
else
  export HOME="${HOME:-$PWD/.pocketlab-home}"
  export PREFIX="${PREFIX:-$HOME/.local}"
fi

export PATH="$PREFIX/bin:$HOME/.local/bin:$PATH"
export POCKET_LAB_BASE_DIR="${POCKET_LAB_BASE_DIR:-$HOME/pocket-lab-lite}"
export POCKET_LAB_IAC_DIR="${POCKET_LAB_IAC_DIR:-$POCKET_LAB_BASE_DIR/pocket_lab_iac}"
export POCKET_LAB_API_DIR="${POCKET_LAB_API_DIR:-$POCKET_LAB_BASE_DIR/api}"
export POCKET_LAB_PWA_DIR="${POCKET_LAB_PWA_DIR:-$POCKET_LAB_BASE_DIR/pwa_dist}"
export POCKET_LAB_POLICIES_DIR="${POCKET_LAB_POLICIES_DIR:-$POCKET_LAB_BASE_DIR/pocket_lab_policies}"
export POCKET_LAB_GITEA_DIR="${POCKET_LAB_GITEA_DIR:-$POCKET_LAB_BASE_DIR/gitea}"
export POCKET_LAB_GITEA_RUNNERS_DIR="${POCKET_LAB_GITEA_RUNNERS_DIR:-$POCKET_LAB_BASE_DIR/gitea-runners}"
export POCKET_LAB_VAULT_DIR="${POCKET_LAB_VAULT_DIR:-$POCKET_LAB_BASE_DIR/vault}"
export POCKET_LAB_OBSERVABILITY_DIR="${POCKET_LAB_OBSERVABILITY_DIR:-$POCKET_LAB_BASE_DIR/observability_configs}"
export POCKET_LAB_GATUS_DIR="${POCKET_LAB_GATUS_DIR:-$POCKET_LAB_OBSERVABILITY_DIR/gatus}"
export POCKET_LAB_CADDYFILE="${POCKET_LAB_CADDYFILE:-$POCKET_LAB_BASE_DIR/caddy/Caddyfile}"
export POCKET_LAB_HARDWARE_DAEMON="${POCKET_LAB_HARDWARE_DAEMON:-$POCKET_LAB_BASE_DIR/hardware_daemon.py}"

STATE_DIR="${STATE_DIR:-$HOME/.pocket_lab}"
LOG_DIR="${LOG_DIR:-$HOME/pocket_lab_logs}"
RUN_DIR="${RUN_DIR:-$HOME/pocket_lab_run}"
LOCK_DIR="${LOCK_DIR:-$STATE_DIR/locks}"
MARKER_DIR="${MARKER_DIR:-$STATE_DIR/markers}"
TMP_ROOT="${TMP_ROOT:-${TMPDIR:-$PREFIX/tmp}/pocket-lab}"
export TERMUX_PREFIX="$PREFIX"

mkdir -p "$STATE_DIR" "$LOG_DIR" "$RUN_DIR" "$LOCK_DIR" "$MARKER_DIR" "$TMP_ROOT" "$PREFIX/bin"

SCRIPT_NAME="${SCRIPT_NAME:-$(basename "${BASH_SOURCE[-1]:-$0}")}"
LOCK_FD=200

NO_NETWORK="${POCKET_LAB_NO_NETWORK:-0}"
ALLOW_NON_TERMUX="${POCKET_LAB_ALLOW_NON_TERMUX:-0}"
export POCKETLAB_PROFILE="${POCKETLAB_PROFILE:-full}"
export POCKETLAB_LITE="${POCKETLAB_LITE:-0}"

normalize_profile() {
  case "${1:-full}" in
    lite|Lite|LITE) printf 'lite' ;;
    full|Full|FULL|enterprise|Enterprise|ENTERPRISE) printf 'full' ;;
    *) printf '%s' "$1" ;;
  esac
}

is_lite_profile() {
  [[ "$(normalize_profile "${POCKETLAB_PROFILE:-full}")" == "lite" || "${POCKETLAB_LITE:-0}" == "1" ]]
}

handle_err() {
  local rc=$? line=${BASH_LINENO[0]:-unknown} cmd=${BASH_COMMAND:-unknown}
  log FATAL "Unexpected error rc=$rc at line $line while running: $cmd" >&2
  exit "$rc"
}
trap handle_err ERR

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { printf '[%s] [%s] [%s] %s\n' "$(timestamp)" "${1:-INFO}" "$SCRIPT_NAME" "${*:2}"; }
die() { log FATAL "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

ensure_root_dirs() {
  mkdir -p "$STATE_DIR" "$LOG_DIR" "$RUN_DIR" "$LOCK_DIR" "$MARKER_DIR" "$TMP_ROOT" "$PREFIX/bin" \
    "$POCKET_LAB_BASE_DIR" "$POCKET_LAB_API_DIR"
  chmod 700 "$STATE_DIR" "$LOG_DIR" "$RUN_DIR" "$LOCK_DIR" "$MARKER_DIR" 2>/dev/null || true
}

require_termux() {
  if ! is_termux && [[ "$ALLOW_NON_TERMUX" != "1" ]]; then
    die "This script targets Android/Termux. Set POCKET_LAB_ALLOW_NON_TERMUX=1 for syntax/test harness mode."
  fi
}

require_cmd() { for c in "$@"; do have "$c" || die "Required command missing: $c"; done; }
require_any_cmd() { for c in "$@"; do have "$c" && return 0; done; die "Required one of these commands: $*"; }

lock_owner_pid() {
  local path="$1" pid=""
  [[ -e "$path" ]] || return 0
  if [[ -f "$path" ]]; then
    pid="$(awk -F= '/^pid=/{print $2; exit}' "$path" 2>/dev/null || true)"
    [[ -n "$pid" ]] || pid="$(head -n 1 "$path" 2>/dev/null | tr -dc '0-9' || true)"
  elif [[ -f "$path/metadata" ]]; then
    pid="$(awk -F= '/^pid=/{print $2; exit}' "$path/metadata" 2>/dev/null || true)"
  fi
  printf '%s' "$pid"
}

pid_is_running() {
  local pid="$1"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

write_lock_metadata() {
  local path="$1" name="$2"
  {
    printf 'pid=%s\n' "$$"
    printf 'script=%s\n' "$name"
    printf 'started_at=%s\n' "$(timestamp)"
    printf 'command=%s\n' "${0:-unknown}"
  } > "$path"
}

release_lock() {
  [[ -n "${ACTIVE_LOCK_DIR:-}" ]] && rm -rf "$ACTIVE_LOCK_DIR" 2>/dev/null || true
  [[ -n "${ACTIVE_LOCK_FILE:-}" ]] && rm -f "$ACTIVE_LOCK_FILE" 2>/dev/null || true
}

acquire_lock() {
  local name="${1:-$SCRIPT_NAME}"
  ensure_root_dirs
  local sanitized="${name//[^A-Za-z0-9_.-]/_}"
  local lockfile="$LOCK_DIR/${sanitized}.lock"
  local pid=""

  if have flock; then
    eval "exec ${LOCK_FD}>\"$lockfile\""
    if ! flock -n "$LOCK_FD"; then
      pid="$(lock_owner_pid "$lockfile")"
      if [[ -n "$pid" ]] && ! pid_is_running "$pid"; then
        log WARN "Removing stale lock for $name held by dead PID $pid: $lockfile"
        rm -f "$lockfile" 2>/dev/null || true
        eval "exec ${LOCK_FD}>\"$lockfile\""
        flock -n "$LOCK_FD" || die "Another $name run is already active: $lockfile"
      else
        die "Another $name run is already active: $lockfile${pid:+ pid=$pid}"
      fi
    fi
    write_lock_metadata "$lockfile" "$name"
    ACTIVE_LOCK_FILE="$lockfile"
    trap release_lock EXIT
  else
    local lockdir="$lockfile.d"
    if ! mkdir "$lockdir" 2>/dev/null; then
      pid="$(lock_owner_pid "$lockdir")"
      if [[ -n "$pid" ]] && ! pid_is_running "$pid"; then
        log WARN "Removing stale lock directory for $name held by dead PID $pid: $lockdir"
        rm -rf "$lockdir" 2>/dev/null || true
        mkdir "$lockdir" 2>/dev/null || die "Another $name run may be active: $lockdir"
      else
        die "Another $name run may be active: $lockdir${pid:+ pid=$pid}"
      fi
    fi
    write_lock_metadata "$lockdir/metadata" "$name"
    ACTIVE_LOCK_DIR="$lockdir"
    trap release_lock EXIT
  fi
}
marker_path() { printf '%s/%s.done' "$MARKER_DIR" "${1//[^A-Za-z0-9_.-]/_}"; }
is_done() { [[ -f "$(marker_path "$1")" ]]; }
mark_done() { mkdir -p "$MARKER_DIR"; printf '%s\n' "$(timestamp)" > "$(marker_path "$1")"; }
mark_clear() { rm -f "$(marker_path "$1")"; }

run_once() {
  local key="$1"; shift
  if is_done "$key"; then
    log INFO "Already completed: $key"
    return 0
  fi
  "$@"
  mark_done "$key"
}

ensure_dir_perm() { local dir="$1" mode="${2:-700}"; mkdir -p "$dir"; chmod "$mode" "$dir" 2>/dev/null || true; }

atomic_write() {
  local dst="$1" mode="${2:-0644}" tmp
  mkdir -p "$(dirname "$dst")"
  tmp="$(mktemp "${dst}.tmp.XXXXXX")"
  cat > "$tmp"
  chmod "$mode" "$tmp" 2>/dev/null || true
  mv -f "$tmp" "$dst"
}

write_secret_file() {
  local file="$1"; shift
  umask 077
  { for kv in "$@"; do printf '%s\n' "$kv"; done; } | atomic_write "$file" 0600
}

backup_file_if_exists() { local src="$1" suffix="${2:-$(date -u +%Y%m%d%H%M%S).bak}"; [[ -f "$src" ]] && cp -p "$src" "${src}.${suffix}" || true; }
ensure_line_in_file() { local line="$1" file="$2"; mkdir -p "$(dirname "$file")"; touch "$file"; grep -Fxq "$line" "$file" || printf '%s\n' "$line" >> "$file"; }

wait_for_tcp() {
  local host="$1" port="$2" timeout="${3:-60}" i
  for i in $(seq 1 "$timeout"); do
    if have nc && nc -z "$host" "$port" >/dev/null 2>&1; then return 0; fi
    if have python3 && python3 - "$host" "$port" >/dev/null 2>&1 <<'PYCHECK'
import socket, sys
s=socket.socket(); s.settimeout(1)
s.connect((sys.argv[1], int(sys.argv[2])))
PYCHECK
    then return 0; fi
    sleep 1
  done
  return 1
}

wait_for_http() {
  local url="$1" timeout="${2:-60}" i
  for i in $(seq 1 "$timeout"); do curl -fsS "$url" >/dev/null 2>&1 && return 0; sleep 1; done
  return 1
}

retry() { local tries="${1:-5}" delay="${2:-2}" n=1; shift 2; until "$@"; do (( n >= tries )) && return 1; sleep "$delay"; n=$((n+1)); done; }

download_file() {
  local url="$1" dest="$2"
  [[ "$NO_NETWORK" == "1" ]] && die "Network disabled; cannot download $url"
  mkdir -p "$(dirname "$dest")"
  local tmp="${dest}.download.$$"
  curl -fL --retry 3 --connect-timeout 20 --max-time 180 "$url" -o "$tmp"
  mv -f "$tmp" "$dest"
}

download_if_missing() { local url="$1" dest="$2"; [[ -s "$dest" ]] && { log INFO "Already present: $dest"; return 0; }; log INFO "Downloading $url"; download_file "$url" "$dest"; }
sha256_verify() { local file="$1" expected="$2"; [[ -n "$expected" ]] || die "Missing expected SHA256 for $file"; printf '%s  %s\n' "$expected" "$file" | sha256sum -c -; }

ensure_pkg_installed() {
  local pkg_name="$1"
  require_termux
  require_cmd pkg dpkg
  if dpkg -s "$pkg_name" >/dev/null 2>&1; then log INFO "Package already installed: $pkg_name"; return 0; fi
  log INFO "Installing Termux package: $pkg_name"
  DEBIAN_FRONTEND=noninteractive pkg install -y "$pkg_name"
}

pm2_has() { have pm2 && pm2 describe "$1" >/dev/null 2>&1; }
pm2_start_or_restart() {
  local name="$1"
  shift

  require_cmd pm2
  log INFO "Starting PM2 process: $name"

  local before_sep=()
  local after_sep=()
  local seen_sep=0
  local arg

  for arg in "$@"; do
    if [[ "$arg" == "--" && "$seen_sep" -eq 0 ]]; then
      seen_sep=1
      continue
    fi

    if [[ "$seen_sep" -eq 1 ]]; then
      after_sep+=("$arg")
    else
      before_sep+=("$arg")
    fi
  done

  # Delete first instead of restart so command/path/env changes are applied reliably.
  pm2 delete "$name" >/dev/null 2>&1 || true

  if [[ "${#after_sep[@]}" -gt 0 ]]; then
    pm2 start "${before_sep[@]}" --name "$name" -- "${after_sep[@]}"
  else
    pm2 start "${before_sep[@]}" --name "$name"
  fi
}

pm2_policy_registry_path() {
  if [[ -n "${POCKETLAB_PM2_POLICY_REGISTRY:-}" ]]; then
    printf '%s\n' "$POCKETLAB_PM2_POLICY_REGISTRY"
    return 0
  fi
  local common_dir final_root
  common_dir="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  final_root="$(CDPATH='' cd -- "$common_dir/../../.." && pwd)"
  printf '%s\n' "$final_root/runtime/supervisors/pocketlab_runtime_registry.py"
}

pm2_policy_fingerprint() {
  local name="$1" registry rc
  registry="$(pm2_policy_registry_path)"
  [[ -f "$registry" ]] || return 0
  python3 "$registry" --policy-fingerprint "$name" 2>/dev/null || {
    rc=$?
    [[ "$rc" -eq 3 ]] && return 0
    return "$rc"
  }
}

pm2_launch_fingerprint() {
  local script="$1" interpreter="$2" cwd="$3" registry
  registry="$(pm2_policy_registry_path)"
  [[ -f "$registry" ]] || return 1
  python3 "$registry" \
    --launch-fingerprint \
    --script "$script" \
    --interpreter "$interpreter" \
    --cwd "$cwd"
}

pm2_write_ecosystem_config() {
  local name="$1" script="$2" interpreter="$3" app_args_json="$4" destination="$5"
  local registry cwd
  registry="$(pm2_policy_registry_path)"
  [[ -f "$registry" ]] || return 1
  cwd="$(pwd -P)"
  python3 "$registry" \
    --ecosystem-js "$name" \
    --script "$script" \
    --interpreter "$interpreter" \
    --cwd "$cwd" \
    --app-args-json "$app_args_json" >"$destination"
}

pm2_process_spec_hash() {
  {
    printf 'argv\\0'
    printf '%s\\0' "$@"
    env | LC_ALL=C sort \
      | grep -E '^(POCKETLAB_|API_PORT=|DASH_PORT=|MALLOC_ARENA_MAX=|OMP_NUM_THREADS=|OPENBLAS_NUM_THREADS=|NUMEXPR_NUM_THREADS=)' \
      | grep -Ev '^POCKETLAB_(RECONCILE_ONLY|RECONCILER_CHILD|RENDER_CADDY_ONLY|BOOTSTRAP_DRY_RUN|PROCESS_SPEC_HASH|PM2_POLICY_REGISTRY|RUNTIME_OBSERVED_.*|PM2_OBSERVED_.*|LITE_APP_OPERATION_ID|PHOTOPRISM_PACKAGE_URL|LITE_SECURE_ORIGIN)=' || true
  } | sha256sum | awk '{print $1}'
}

pm2_record_desired_process_spec_hash() {
  local name="$1" hash="$2" launch_hash="$3"
  local state_dir="${POCKETLAB_STATE_DIR:-${POCKET_LAB_BASE_DIR:-$HOME/pocket-lab-lite}/state}"
  local evidence_path="$state_dir/runtime/desired-process-specs.json"
  python3 - "$evidence_path" "$name" "$hash" "$launch_hash" <<'PY'
import fcntl
import json
import os
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
name, digest, launch_digest = sys.argv[2], sys.argv[3], sys.argv[4]
if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", name):
    raise SystemExit("invalid PM2 process name for desired-spec evidence")
if not re.fullmatch(r"[0-9a-f]{64}", digest):
    raise SystemExit("invalid PM2 desired process-spec fingerprint")
if not re.fullmatch(r"[0-9a-f]{64}", launch_digest):
    raise SystemExit("invalid PM2 desired launch fingerprint")
path.parent.mkdir(parents=True, exist_ok=True)
lock_path = path.with_suffix(path.suffix + ".lock")
with lock_path.open("a", encoding="utf-8") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current.get("schema") != "pocketlab.pm2-desired-process-specs/v1":
            raise SystemExit("unsupported PM2 desired process-spec evidence schema")
        processes = current.get("processes")
        if not isinstance(processes, dict):
            raise SystemExit("invalid PM2 desired process-spec evidence")
        launches = current.get("launches")
        if not isinstance(launches, dict):
            launches = {}
    else:
        processes = {}
        launches = {}
    processes[name] = digest
    launches[name] = launch_digest
    payload = {
        "schema": "pocketlab.pm2-desired-process-specs/v1",
        "schema_version": 1,
        "processes": dict(sorted(processes.items())),
        "launches": dict(sorted(launches.items())),
        "sanitized": True,
    }
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
PY
}

pm2_normalize_service_version() {
  local raw="${1:-}"
  python3 - "$raw" <<'PY'
import re
import sys
value = (sys.argv[1] or "").replace("\r", " ").replace("\n", " ").strip()
value = re.sub(r"\s+", " ", value)
if (
    not value
    or value.lower() in {"n/a", "na", "unknown", "none", "null"}
    or value.startswith("$")
):
    raise SystemExit(1)
print(value)
PY
}

pocketlab_source_version() {
  local source_path="${1:-}"
  local package_json version digest
  package_json="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)/package.json"
  [[ -f "$source_path" ]] || die "Cannot version missing Pocket Lab source: $source_path"
  version="$(python3 - "$package_json" <<'PY'
import json, sys
try:
    data=json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    data={}
print(str(data.get("version") or "0.0.0"))
PY
)"
  digest="$(sha256sum "$source_path" | awk '{print substr($1,1,12)}')"
  pm2_normalize_service_version "${version}+sha.${digest}"
}

pm2_prepare_versioned_exec() {
  local name="$1" version="$2" source_exec="$3"
  local resolved safe_name dir link
  [[ -n "$name" ]] || die "PM2 version projection requires a process name"
  version="$(pm2_normalize_service_version "$version")" || die "PM2 version projection for $name is missing or invalid"
  if [[ "$source_exec" == */* ]]; then
    resolved="$source_exec"
  else
    resolved="$(command -v "$source_exec" 2>/dev/null || true)"
  fi
  [[ -n "$resolved" && -e "$resolved" ]] || die "PM2 version projection cannot resolve executable for $name: $source_exec"

  safe_name="${name//[^A-Za-z0-9_.-]/_}"
  dir="$STATE_DIR/pm2-versioned/$safe_name"
  link="$dir/exec"
  mkdir -p "$dir"
  chmod 700 "$STATE_DIR/pm2-versioned" "$dir" 2>/dev/null || true

  python3 - "$dir/package.json" "$safe_name" "$version" <<'PY'
import json, sys
from pathlib import Path
path=Path(sys.argv[1])
payload={
    "name": "pocketlab-pm2-" + sys.argv[2],
    "private": True,
    "version": sys.argv[3],
}
tmp=path.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
tmp.replace(path)
PY
  ln -sfn "$resolved" "$link"
  printf '%s\n' "$link"
}

pm2_version_snapshot() {
  local name="$1"
  pm2 jlist 2>/dev/null | python3 -c '
import json, sys
name=sys.argv[1]
try:
    items=json.load(sys.stdin)
except Exception:
    items=[]
for item in items if isinstance(items,list) else []:
    if str(item.get("name") or "") != name:
        continue
    env=item.get("pm2_env") if isinstance(item.get("pm2_env"),dict) else {}
    print(str(env.get("version") or ""))
    print(str(env.get("POCKETLAB_SERVICE_VERSION") or ""))
    raise SystemExit(0)
raise SystemExit(1)
' "$name"
}

pm2_ensure_versioned_process() {
  local name="$1" version="$2" source_exec="$3"
  shift 3
  local projected_exec version_snapshot current_version current_declared
  require_cmd pm2 python3 sha256sum
  version="$(pm2_normalize_service_version "$version")" || die "PM2 service $name does not have an exact installed version"
  projected_exec="$(pm2_prepare_versioned_exec "$name" "$version" "$source_exec")"
  local POCKETLAB_SERVICE_VERSION="$version"
  export POCKETLAB_SERVICE_VERSION

  version_snapshot="$(pm2_version_snapshot "$name" 2>/dev/null || true)"
  current_version="$(printf '%s\n' "$version_snapshot" | sed -n '1p')"
  current_declared="$(printf '%s\n' "$version_snapshot" | sed -n '2p')"
  if [[ -n "$current_version" ]] && {
    [[ "$current_version" != "$version" ]] ||
    [[ "$current_version" =~ ^([Nn]/?[Aa]|unknown)$ ]] ||
    [[ "$current_declared" != "$version" ]]
  }; then
    log INFO "Replacing PM2 process with stale version projection: $name observed=${current_version:-missing} declared=${current_declared:-missing} expected=$version"
    pm2 delete "$name" >/dev/null 2>&1 || true
  fi

  pm2_ensure_process "$name" "$projected_exec" "$@"
}

pm2_process_snapshot() {
  local name="$1"
  pm2 jlist 2>/dev/null | python3 -c '
import json, sys
name=sys.argv[1]
try:
    items=json.load(sys.stdin)
except Exception:
    items=[]
for item in items if isinstance(items,list) else []:
    if str(item.get("name") or "") != name:
        continue
    env=item.get("pm2_env") if isinstance(item.get("pm2_env"),dict) else {}
    print(str(env.get("status") or item.get("status") or "unknown").lower())
    print(str(env.get("POCKETLAB_PROCESS_SPEC_HASH") or ""))
    print(str(env.get("pm_exec_path") or ""))
    print(str(env.get("exec_interpreter") or ""))
    raise SystemExit(0)
raise SystemExit(0)
' "$name"
}

pm2_ensure_process() {
  local name="$1"
  shift
  require_cmd pm2 python3 sha256sum

  local before_sep=()
  local after_sep=()
  local seen_sep=0
  local arg
  for arg in "$@"; do
    if [[ "$arg" == "--" && "$seen_sep" -eq 0 ]]; then
      seen_sep=1
      continue
    fi
    if [[ "$seen_sep" -eq 1 ]]; then
      after_sep+=("$arg")
    else
      before_sep+=("$arg")
    fi
  done
  local process_script="${before_sep[0]:-}" process_interpreter="" index=1 arg
  [[ -n "$process_script" ]] || { log ERROR "PM2 process $name has no executable"; return 2; }
  while (( index < ${#before_sep[@]} )); do
    arg="${before_sep[$index]}"
    case "$arg" in
      --interpreter)
        (( index + 1 < ${#before_sep[@]} )) || { log ERROR "PM2 process $name has an incomplete interpreter option"; return 2; }
        arg="${before_sep[$((index + 1))]}"
        if ! command -v "$arg" >/dev/null 2>&1; then
          log ERROR "PM2 interpreter is unavailable for $name: $arg"
          return 2
        fi
        process_interpreter="$(command -v "$arg")"
        index=$((index + 2))
        ;;
      --update-env)
        index=$((index + 1))
        ;;
      *)
        log ERROR "Unsupported PM2 launch option for $name: $arg"
        return 2
        ;;
    esac
  done

  local cwd launch_fingerprint policy_fingerprint spec_hash snapshot status current_hash current_script current_interpreter current_launch_fingerprint
  cwd="$(pwd -P)"
  launch_fingerprint="$(pm2_launch_fingerprint "$process_script" "$process_interpreter" "$cwd")"
  policy_fingerprint="$(pm2_policy_fingerprint "$name")"
  local POCKETLAB_PM2_POLICY_FINGERPRINT="$policy_fingerprint"
  export POCKETLAB_PM2_POLICY_FINGERPRINT

  local effective_spec=("${before_sep[@]}")
  if [[ "${#after_sep[@]}" -gt 0 ]]; then
    effective_spec+=(-- "${after_sep[@]}")
  fi
  spec_hash="$(pm2_process_spec_hash "${effective_spec[@]}")"
  if ! snapshot="$(pm2_process_snapshot "$name" 2>/dev/null)"; then
    snapshot=""
  fi
  status="$(printf '%s\n' "$snapshot" | sed -n '1p')"
  current_hash="$(printf '%s\n' "$snapshot" | sed -n '2p')"
  current_script="$(printf '%s\n' "$snapshot" | sed -n '3p')"
  current_interpreter="$(printf '%s\n' "$snapshot" | sed -n '4p')"
  current_launch_fingerprint=""
  if [[ -n "$current_script" ]]; then
    current_launch_fingerprint="$(pm2_launch_fingerprint "$current_script" "$current_interpreter" "$cwd" 2>/dev/null || true)"
  fi

  if [[ -n "$status" && "$current_hash" == "$spec_hash" && "$current_launch_fingerprint" == "$launch_fingerprint" ]]; then
    if [[ "$status" == "online" ]]; then
      pm2_record_desired_process_spec_hash "$name" "$spec_hash" "$launch_fingerprint"
      log INFO "PM2 process already converged: $name"
      return 0
    fi
    log INFO "Restarting existing converged PM2 process: $name status=$status"
    POCKETLAB_PROCESS_SPEC_HASH="$spec_hash" pm2 restart "$name" --update-env >/dev/null
    pm2_record_desired_process_spec_hash "$name" "$spec_hash" "$launch_fingerprint"
    return 0
  fi

  if [[ -n "$status" ]]; then
    log INFO "Replacing drifted PM2 process definition: $name"
    pm2 delete "$name" >/dev/null 2>&1 || true
  else
    log INFO "Creating missing PM2 process definition: $name"
  fi

  local app_args_json state_dir ecosystem_dir ecosystem_file ecosystem_tmp launch_status=0 old_umask safe_name
  app_args_json="$(python3 - "${after_sep[@]}" <<'PY'
import json
import sys
print(json.dumps(sys.argv[1:], separators=(",", ":")))
PY
)"
  state_dir="${POCKETLAB_STATE_DIR:-${POCKET_LAB_BASE_DIR:-$HOME/pocket-lab-lite}/state}"
  mkdir -p "$state_dir/runtime"
  safe_name="${name//[^A-Za-z0-9_.-]/_}"
  ecosystem_dir="$state_dir/runtime/pm2-ecosystems"
  mkdir -p "$ecosystem_dir"
  old_umask="$(umask)"
  umask 077
  ecosystem_file="$ecosystem_dir/$safe_name.config.cjs"
  ecosystem_tmp="$ecosystem_file.$$.tmp"
  umask "$old_umask"
  if ! pm2_write_ecosystem_config "$name" "$process_script" "$process_interpreter" "$app_args_json" "$ecosystem_tmp"; then
    rm -f -- "$ecosystem_tmp"
    return 1
  fi
  # Keep a stable, process-specific ecosystem path. PM2 7 on Termux can cache
  # rapidly replaced temporary configs and apply a later --only selection to
  # the previous app definition. Atomic replacement preserves a deterministic
  # path while ensuring PM2 reads the current canonical app.
  mv -f -- "$ecosystem_tmp" "$ecosystem_file"
  if POCKETLAB_PROCESS_SPEC_HASH="$spec_hash" pm2 start "$ecosystem_file" --only "$name" >/dev/null; then
    launch_status=0
  else
    launch_status=$?
  fi
  if [[ "$launch_status" -ne 0 ]]; then
    return "$launch_status"
  fi
  # PM2 writes its jlist record asynchronously. The next reconciliation pass
  # validates the recorded executable identity before treating this process as
  # converged, avoiding a startup race while retaining fail-closed drift
  # detection.
  pm2_record_desired_process_spec_hash "$name" "$spec_hash" "$launch_fingerprint"
}

cleanup_pidfile() { local pidfile="$1" pid=""; [[ -f "$pidfile" ]] || return 0; pid="$(cat "$pidfile" 2>/dev/null || true)"; [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true; rm -f "$pidfile"; }

json_get() { jq -r "$1" "${2:--}"; }
safe_cp() { local src="$1" dst="$2"; install -m 0644 "$src" "$dst"; }
render_template() { local tpl="$1" dst="$2"; shift 2; export "$@"; envsubst < "$tpl" > "$dst"; }
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python || true)}"
