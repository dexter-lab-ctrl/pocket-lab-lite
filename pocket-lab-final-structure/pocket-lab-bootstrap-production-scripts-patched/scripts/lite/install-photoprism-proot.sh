#!/usr/bin/env bash
# PhotoPrism lifecycle for Pocket Lab Lite.
#
# Modes:
#   install    - first installation; may install PRoot/dependencies/download app.
#   reconcile  - runtime-only convergence; NEVER installs/downloads/updates.
#   repair     - bounded runtime/config/route repair; NEVER updates software.
#   update     - explicit software update path.
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../lib/common.sh"
SCRIPT_NAME="install-photoprism-proot.sh"

MODE="${1:-install}"
case "$MODE" in
  install|reconcile|repair|update) ;;
  *) die "Unsupported PhotoPrism lifecycle mode: $MODE" ;;
esac

APP_ID="${POCKETLAB_LITE_APP_ID:-photoprism}"
OPERATION_ID="${POCKETLAB_LITE_APP_OPERATION_ID:-app-photoprism-$MODE}"
STATE_BASE="${POCKETLAB_STATE_DIR:-${POCKETLAB_BASE_DIR:-$HOME/pocket-lab-lite}/state}"
APP_ROOT="${POCKETLAB_PHOTOPRISM_ROOT:-$HOME/.pocket_lab/lite/apps/photoprism}"
CONFIG_DIR="$APP_ROOT/config"
STORAGE_DIR="$APP_ROOT/storage"
ORIGINALS_DIR="$APP_ROOT/originals"
IMPORT_DIR="$APP_ROOT/import"
LOG_DIR_APP="$APP_ROOT/logs"
ENV_FILE="$CONFIG_DIR/photoprism.env"
INSTALL_MANIFEST="$CONFIG_DIR/install-manifest.json"
ROUTES_FILE="${POCKETLAB_LITE_APP_ROUTES:-$STATE_BASE/app_routes.json}"
ROUTE_PATH="${POCKETLAB_LITE_APP_ROUTE:-/apps/photoprism/}"
UPSTREAM="${POCKETLAB_LITE_APP_UPSTREAM:-127.0.0.1:2342}"
PROCESS_NAME="${POCKETLAB_PHOTOPRISM_PROCESS:-pocketlab-app-photoprism}"
EVIDENCE_DIR="$STATE_BASE/catalog/evidence/$OPERATION_ID"
SUMMARY_FILE="$EVIDENCE_DIR/summary.json"
SECURE_ORIGIN="${POCKETLAB_LITE_SECURE_ORIGIN:-${POCKETLAB_SECURE_ORIGIN:-}}"
PACKAGE_URL="${POCKETLAB_PHOTOPRISM_PACKAGE_URL:-}"

sanitize_message(){
  python3 - "$1" <<'PY'
import re, sys
text=sys.argv[1] if len(sys.argv)>1 else ""
print(re.sub(r"(?i)(password|token|secret|api[_-]?key|private[_ -]?key)\s*[:=]\s*\S+", r"\1=[hidden]", text)[:240])
PY
}

write_summary(){
  local status="$1" summary="$2" version="${3:-detected-or-unknown}" local_health="${4:-unknown}" route_health="${5:-unknown}"
  mkdir -p "$EVIDENCE_DIR"
  chmod 700 "$STATE_BASE" "$EVIDENCE_DIR" 2>/dev/null || true
  python3 - "$SUMMARY_FILE" "$status" "$(sanitize_message "$summary")" "$OPERATION_ID" "$version" "$local_health" "$route_health" "$MODE" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
path,status,summary,op,version,local_health,route_health,mode=sys.argv[1:]
payload={
  "status":status,
  "summary":summary,
  "operation_id":op,
  "app_id":"photoprism",
  "lifecycle_mode":mode,
  "version":version or "detected-or-unknown",
  "local_health":local_health,
  "route_health":route_health,
  "updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
  "runtime":{"route":"/apps/photoprism/","upstream":"127.0.0.1:2342","process":"pocketlab-app-photoprism"},
  "evidence_refs":[f"catalog/evidence/{op}/summary.json"],
  "safe_notes":[
    "PhotoPrism runs on the Server Host through PRoot Ubuntu.",
    "Runtime reconciliation never installs, downloads, or updates PhotoPrism.",
    "Admin credentials remain server-side and are not returned through the Lite API."
  ],
  "sanitized":True,
}
Path(path).parent.mkdir(parents=True, exist_ok=True)
Path(path).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n", encoding="utf-8")
PY
}

fail_safe(){
  write_summary "failed" "$1" "detected-or-unknown" "unhealthy" "unhealthy"
  log ERROR "$(sanitize_message "$1")"
  exit 1
}

arch_package_url(){
  [[ -n "$PACKAGE_URL" ]] && { printf '%s\n' "$PACKAGE_URL"; return 0; }
  case "$(uname -m)" in
    aarch64|arm64) echo "https://dl.photoprism.app/pkg/linux/arm64.tar.gz" ;;
    x86_64|amd64) echo "https://dl.photoprism.app/pkg/linux/amd64.tar.gz" ;;
    *) return 1 ;;
  esac
}

ubuntu_ready(){
  have proot-distro || return 1
  proot-distro login ubuntu -- true >/dev/null 2>&1
}

ensure_ubuntu_for_install(){
  require_cmd proot-distro
  if ubuntu_ready; then return 0; fi
  log INFO "Installing PRoot Ubuntu for explicit PhotoPrism installation"
  proot-distro install ubuntu >/dev/null || fail_safe "Could not install PRoot Ubuntu for PhotoPrism."
  ubuntu_ready || fail_safe "PRoot Ubuntu is not ready for PhotoPrism."
}

require_existing_ubuntu(){
  ubuntu_ready || fail_safe "PRoot Ubuntu is unavailable. Runtime recovery will not reinstall it automatically."
}

binary_ready(){
  ubuntu_ready || return 1
  proot-distro login ubuntu -- bash -lc 'test -x /usr/local/bin/photoprism && /usr/local/bin/photoprism --version >/dev/null 2>&1'
}

install_dependencies(){
  log INFO "Installing PhotoPrism dependencies for explicit $MODE"
  proot-distro login ubuntu -- bash -lc '
    set -Eeuo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y >/dev/null
    apt-get install -y ca-certificates curl tar sqlite3 tzdata ffmpeg libimage-exiftool-perl >/dev/null
    apt-get install -y libvips42t64 >/dev/null 2>&1 || apt-get install -y libvips42 >/dev/null
    mkdir -p /opt/photoprism /usr/local/bin
  ' || fail_safe "Could not prepare PhotoPrism runtime dependencies."
}

install_or_update_package(){
  local url="$1"
  log INFO "Downloading PhotoPrism package for explicit $MODE"
  proot-distro login ubuntu -- env POCKETLAB_PACKAGE_URL="$url" bash -lc '
    set -Eeuo pipefail
    archive=/tmp/pocketlab-photoprism.tar.gz
    next="/opt/photoprism.next.$$"
    previous=/opt/photoprism.previous
    curl -fsSL "$POCKETLAB_PACKAGE_URL" -o "$archive"
    digest="$(sha256sum "$archive" | awk "{print \$1}")"
    rm -rf "$next"
    mkdir -p "$next"
    tar -xzf "$archive" -C "$next" --strip-components=1
    test -x "$next/bin/photoprism"
    "$next/bin/photoprism" --version >/tmp/photoprism-version.next.txt 2>/dev/null
    rm -rf "$previous"
    if test -d /opt/photoprism && test -n "$(ls -A /opt/photoprism 2>/dev/null || true)"; then
      mv /opt/photoprism "$previous"
    else
      rm -rf /opt/photoprism
    fi
    mv "$next" /opt/photoprism
    ln -sfn /opt/photoprism/bin/photoprism /usr/local/bin/photoprism
    mv /tmp/photoprism-version.next.txt /tmp/photoprism-version.txt
    printf "%s\n" "$digest" >/tmp/photoprism-package.sha256
    rm -f "$archive"
  ' || fail_safe "Could not install the PhotoPrism package."
}

photoprism_version(){
  proot-distro login ubuntu -- bash -lc '/usr/local/bin/photoprism --version 2>/dev/null | head -1' 2>/dev/null | tr -d '\r' | sed 's/[[:space:]]\+$//' | head -1
}

package_digest(){
  proot-distro login ubuntu -- bash -lc 'cat /tmp/photoprism-package.sha256 2>/dev/null | head -1' 2>/dev/null | tr -cd '0-9a-fA-F' | head -c64
}

photoprism_pm2_version(){
  local raw build
  raw="$(photoprism_version)"
  build="$(printf '%s\n' "$raw" | sed -nE 's/^.*[Bb]uild[[:space:]]+([^[:space:]]+).*$/\1/p' | head -1)"
  if [[ -n "$build" ]]; then
    pm2_normalize_service_version "$build"
  else
    pm2_normalize_service_version "$raw"
  fi
}

write_install_manifest(){
  local version="$1" digest="${2:-}"
  mkdir -p "$CONFIG_DIR"
  python3 - "$INSTALL_MANIFEST" "$version" "$digest" "$(uname -m)" "$MODE" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
path,version,digest,arch,mode=sys.argv[1:]
existing={}
try:
    existing=json.loads(Path(path).read_text())
except Exception:
    pass
payload={
  "schema_version":1,
  "app_id":"photoprism",
  "version":version or "detected-or-unknown",
  "package_sha256":digest if len(digest)==64 else existing.get("package_sha256"),
  "architecture":arch,
  "last_software_action":mode,
  "installed_at":existing.get("installed_at") or datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
  "updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
  "sanitized":True,
}
tmp=Path(path+".tmp")
tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n", encoding="utf-8")
tmp.replace(Path(path))
PY
  chmod 600 "$INSTALL_MANIFEST" 2>/dev/null || true
}

create_env_file_for_install(){
  mkdir -p "$CONFIG_DIR" "$STORAGE_DIR" "$ORIGINALS_DIR" "$IMPORT_DIR" "$LOG_DIR_APP"
  chmod 700 "$APP_ROOT" "$CONFIG_DIR" "$STORAGE_DIR" 2>/dev/null || true
  if [[ -s "$ENV_FILE" ]] && grep -q '^PHOTOPRISM_ADMIN_PASSWORD=' "$ENV_FILE"; then return 0; fi
  local admin_password
  admin_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  umask 077
  cat > "$ENV_FILE" <<ENV
PHOTOPRISM_ADMIN_USER=admin
PHOTOPRISM_ADMIN_PASSWORD=$admin_password
PHOTOPRISM_AUTH_MODE=password
PHOTOPRISM_DATABASE_DRIVER=sqlite
PHOTOPRISM_HTTP_HOST=0.0.0.0
PHOTOPRISM_HTTP_PORT=2342
PHOTOPRISM_CONFIG_PATH=$CONFIG_DIR
PHOTOPRISM_STORAGE_PATH=$STORAGE_DIR
PHOTOPRISM_ORIGINALS_PATH=$ORIGINALS_DIR
PHOTOPRISM_IMPORT_PATH=$IMPORT_DIR
PHOTOPRISM_LOG_LEVEL=info
PHOTOPRISM_SITE_URL=${SECURE_ORIGIN:+$SECURE_ORIGIN$ROUTE_PATH}
ENV
  chmod 600 "$ENV_FILE"
}

require_existing_env(){
  [[ -s "$ENV_FILE" ]] || fail_safe "PhotoPrism configuration is missing. Runtime recovery will not generate new credentials."
  grep -q '^PHOTOPRISM_ADMIN_PASSWORD=' "$ENV_FILE" || fail_safe "PhotoPrism configuration is incomplete. Runtime recovery will not replace credentials."
  chmod 600 "$ENV_FILE" 2>/dev/null || true
}

write_route_registry(){
  mkdir -p "$(dirname "$ROUTES_FILE")"
  python3 - "$ROUTES_FILE" "$APP_ID" "$ROUTE_PATH" "$UPSTREAM" <<'PY'
import json,re,sys
from datetime import datetime, timezone
from pathlib import Path
path=Path(sys.argv[1]); app_id, route_path, upstream=sys.argv[2:5]
if app_id!="photoprism" or route_path!="/apps/photoprism/" or not re.fullmatch(r"(127\.0\.0\.1|localhost):[0-9]{2,5}", upstream):
    raise SystemExit(1)
try:
    data=json.loads(path.read_text()) if path.exists() else {}
except Exception:
    data={}
routes=[r for r in data.get("routes",[]) if isinstance(r,dict) and r.get("app_id")!=app_id]
routes.append({"app_id":app_id,"path":route_path,"upstream":upstream,"enabled":True,"health":"unknown","updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")})
data.update({"routes":routes,"updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")})
tmp=path.with_suffix(".tmp")
tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
tmp.replace(path)
PY
}

mark_route_health(){
  [[ -s "$ROUTES_FILE" ]] || return 0
  python3 - "$ROUTES_FILE" "$1" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
path=Path(sys.argv[1]); health=sys.argv[2]; data=json.loads(path.read_text())
for r in data.get("routes",[]):
    if isinstance(r,dict) and r.get("app_id")=="photoprism":
        r["health"]=health
        r["updated_at"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
data["updated_at"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
tmp=path.with_suffix(".tmp")
tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
tmp.replace(path)
PY
}

local_health_ready(){
  curl -fsS --connect-timeout 1 --max-time 3 "http://127.0.0.1:2342/apps/photoprism/api/v1/status" >/dev/null 2>&1 ||
    curl -fsS --connect-timeout 1 --max-time 3 "http://127.0.0.1:2342/apps/photoprism/" >/dev/null 2>&1
}

pm2_app_status(){
  pm2 jlist 2>/dev/null | python3 -c '
import json,sys
name=sys.argv[1]
try: items=json.load(sys.stdin)
except Exception: items=[]
for item in items if isinstance(items,list) else []:
    if item.get("name") == name:
        env=item.get("pm2_env") if isinstance(item.get("pm2_env"),dict) else {}
        print(str(env.get("status") or item.get("status") or "unknown").lower())
        raise SystemExit(0)
print("missing")
' "$PROCESS_NAME"
}

ensure_pm2_ownership(){
  local status env_revision command
  status="$(pm2_app_status)"
  if local_health_ready && [[ "$status" == "missing" ]]; then
    fail_safe "PhotoPrism is responding outside Pocket Lab PM2 ownership. Automatic adoption is blocked."
  fi
  local version
  env_revision="$(sha256sum "$ENV_FILE" | awk '{print $1}')"
  version="$(photoprism_pm2_version)" || fail_safe "PhotoPrism did not report an installed version."
  command="exec proot-distro login ubuntu -- bash -lc 'set -a; source \"$ENV_FILE\"; set +a; exec photoprism start'"
  POCKETLAB_PHOTOPRISM_ENV_REVISION="$env_revision" pm2_ensure_versioned_process "$PROCESS_NAME" "$version" bash -- -lc "$command"
}

refresh_caddy(){
  local helper="$SCRIPT_DIR/restart-caddy-proxy.sh"
  if [[ -x "$helper" ]]; then
    "$helper" || log WARN "Caddy route refresh did not complete; local PhotoPrism health remains authoritative"
  fi
}

wait_for_health(){
  local attempt
  for attempt in $(seq 1 90); do
    local_health_ready && return 0
    sleep 2
  done
  return 1
}

route_health(){
  if curl -fsS --connect-timeout 1 --max-time 3 "http://127.0.0.1:8443/apps/photoprism/api/v1/status" >/dev/null 2>&1 ||
     curl -fsS --connect-timeout 1 --max-time 3 "http://127.0.0.1:8443/apps/photoprism/" >/dev/null 2>&1; then
    echo healthy
  else
    echo unknown
  fi
}

reconcile_runtime(){
  require_existing_ubuntu
  require_existing_env
  binary_ready || fail_safe "PhotoPrism runtime binary is missing. Reconcile will not download or reinstall software."
  write_route_registry
  ensure_pm2_ownership
  refresh_caddy
  # Caddy refresh is a separate PM2 mutation. PM2 7 on Termux can briefly
  # remap a sibling definition while that queued operation drains, so prove
  # PhotoPrism ownership again before publishing runtime evidence or saving
  # the PM2 snapshot.
  ensure_pm2_ownership
  wait_for_health || fail_safe "PhotoPrism did not become healthy after runtime reconciliation."
  local version route
  version="$(photoprism_version)"
  route="$(route_health)"
  mark_route_health "$route"
  write_summary "succeeded" "PhotoPrism runtime is reconciled." "${version:-detected-or-unknown}" "healthy" "$route"
  pm2 save >/dev/null 2>&1 || true
}

install_runtime(){
  local url version digest=""
  ensure_ubuntu_for_install
  install_dependencies
  if ! binary_ready; then
    url="$(arch_package_url)" || fail_safe "PhotoPrism package is not available for this architecture."
    install_or_update_package "$url"
    digest="$(package_digest)"
  fi
  create_env_file_for_install
  version="$(photoprism_version)"
  write_install_manifest "$version" "$digest"
  reconcile_runtime
}

update_runtime(){
  local url version digest
  require_existing_ubuntu
  require_existing_env
  install_dependencies
  url="$(arch_package_url)" || fail_safe "PhotoPrism package is not available for this architecture."
  install_or_update_package "$url"
  version="$(photoprism_version)"
  digest="$(package_digest)"
  write_install_manifest "$version" "$digest"
  reconcile_runtime
}

main(){
  [[ "$APP_ID" == "photoprism" ]] || fail_safe "Unsupported Lite app requested."
  require_termux
  require_cmd python3 curl pm2 sha256sum

  case "$MODE" in
    install) install_runtime ;;
    update) update_runtime ;;
    reconcile|repair) reconcile_runtime ;;
  esac
}

main "$@"
