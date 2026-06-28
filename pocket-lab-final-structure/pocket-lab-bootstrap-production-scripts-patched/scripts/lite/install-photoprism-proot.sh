#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../lib/common.sh"
SCRIPT_NAME="install-photoprism-proot.sh"

APP_ID="${POCKETLAB_LITE_APP_ID:-photoprism}"
OPERATION_ID="${POCKETLAB_LITE_APP_OPERATION_ID:-app-photoprism-manual}"
STATE_BASE="${POCKETLAB_STATE_DIR:-${POCKETLAB_BASE_DIR:-$HOME/pocket-lab-lite}/state}"
APP_ROOT="${POCKETLAB_PHOTOPRISM_ROOT:-$HOME/.pocket_lab/lite/apps/photoprism}"
CONFIG_DIR="$APP_ROOT/config"; STORAGE_DIR="$APP_ROOT/storage"; ORIGINALS_DIR="$APP_ROOT/originals"; IMPORT_DIR="$APP_ROOT/import"; LOG_DIR_APP="$APP_ROOT/logs"
ENV_FILE="$CONFIG_DIR/photoprism.env"
ROUTES_FILE="${POCKETLAB_LITE_APP_ROUTES:-$STATE_BASE/app_routes.json}"
ROUTE_PATH="${POCKETLAB_LITE_APP_ROUTE:-/apps/photoprism/}"; UPSTREAM="${POCKETLAB_LITE_APP_UPSTREAM:-127.0.0.1:2342}"
PROCESS_NAME="${POCKETLAB_PHOTOPRISM_PROCESS:-pocketlab-app-photoprism}"
EVIDENCE_DIR="$STATE_BASE/catalog/evidence/$OPERATION_ID"; SUMMARY_FILE="$EVIDENCE_DIR/summary.json"
SECURE_ORIGIN="${POCKETLAB_LITE_SECURE_ORIGIN:-${POCKETLAB_SECURE_ORIGIN:-}}"
PACKAGE_URL="${POCKETLAB_PHOTOPRISM_PACKAGE_URL:-}"

sanitize_message(){ python3 - "$1" <<'PY'
import re, sys
text=sys.argv[1] if len(sys.argv)>1 else ""
print(re.sub(r"(?i)(password|token|secret|api[_-]?key|private[_ -]?key)\s*[:=]\s*\S+", r"\1=[hidden]", text)[:240])
PY
}
write_summary(){
  local status="$1" summary="$2" version="${3:-detected-or-unknown}" local_health="${4:-unknown}" route_health="${5:-unknown}"
  mkdir -p "$EVIDENCE_DIR"; chmod 700 "$STATE_BASE" "$EVIDENCE_DIR" 2>/dev/null || true
  python3 - "$SUMMARY_FILE" "$status" "$(sanitize_message "$summary")" "$OPERATION_ID" "$version" "$local_health" "$route_health" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
path,status,summary,op,version,local_health,route_health=sys.argv[1:]
payload={"status":status,"summary":summary,"operation_id":op,"app_id":"photoprism","version":version or "detected-or-unknown","local_health":local_health,"route_health":route_health,"updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"runtime":{"route":"/apps/photoprism/","upstream":"127.0.0.1:2342","process":"pocketlab-app-photoprism"},"evidence_refs":[f"catalog/evidence/{op}/summary.json"],"safe_notes":["PhotoPrism runs on the Server Host through PRoot Ubuntu.","Admin credentials stay on the server host and are not returned through the Lite API.","Caddy route state contains only a local upstream and no secrets."]}
Path(path).parent.mkdir(parents=True, exist_ok=True); Path(path).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
PY
}
fail_safe(){ write_summary "failed" "$1" "detected-or-unknown" "unhealthy" "unhealthy"; log ERROR "$(sanitize_message "$1")"; exit 1; }

write_route_registry(){
  mkdir -p "$(dirname "$ROUTES_FILE")"
  python3 - "$ROUTES_FILE" "$APP_ID" "$ROUTE_PATH" "$UPSTREAM" <<'PY'
import json,re,sys
from datetime import datetime, timezone
from pathlib import Path
path=Path(sys.argv[1]); app_id, route_path, upstream=sys.argv[2:5]
if app_id!="photoprism" or route_path!="/apps/photoprism/" or not re.fullmatch(r"(127\.0\.0\.1|localhost):[0-9]{2,5}", upstream): raise SystemExit(1)
try: data=json.loads(path.read_text()) if path.exists() else {}
except Exception: data={}
routes=[r for r in data.get("routes",[]) if isinstance(r,dict) and r.get("app_id")!=app_id]
routes.append({"app_id":app_id,"path":route_path,"upstream":upstream,"enabled":True,"health":"unknown","updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")})
data.update({"routes":routes,"updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}); path.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
PY
}
mark_route_health(){ [[ -s "$ROUTES_FILE" ]] || return 0; python3 - "$ROUTES_FILE" "$1" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
path=Path(sys.argv[1]); health=sys.argv[2]; data=json.loads(path.read_text())
for r in data.get("routes",[]):
    if isinstance(r,dict) and r.get("app_id")=="photoprism": r["health"]=health; r["updated_at"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
data["updated_at"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z"); path.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
PY
}

arch_package_url(){
  [[ -n "$PACKAGE_URL" ]] && { printf '%s\n' "$PACKAGE_URL"; return 0; }
  case "$(uname -m)" in aarch64|arm64) echo "https://dl.photoprism.app/pkg/linux/arm64.tar.gz";; x86_64|amd64) echo "https://dl.photoprism.app/pkg/linux/amd64.tar.gz";; *) return 1;; esac
}
ensure_ubuntu_ready(){ require_cmd proot-distro; if ! proot-distro login ubuntu -- true >/dev/null 2>&1; then log INFO "Preparing PRoot Ubuntu for PhotoPrism"; proot-distro install ubuntu >/dev/null || fail_safe "Could not install PRoot Ubuntu for PhotoPrism."; fi; proot-distro login ubuntu -- true >/dev/null 2>&1 || fail_safe "PRoot Ubuntu is not ready for PhotoPrism."; }
install_photoprism_inside_ubuntu(){
  local url="$1"; log INFO "Installing PhotoPrism runtime dependencies in PRoot Ubuntu"
  proot-distro login ubuntu -- bash -lc 'set -Eeuo pipefail; export DEBIAN_FRONTEND=noninteractive; apt-get update -y >/dev/null; apt-get install -y ca-certificates curl tar sqlite3 tzdata ffmpeg libimage-exiftool-perl >/dev/null; apt-get install -y libvips42t64 >/dev/null 2>&1 || apt-get install -y libvips42 >/dev/null; mkdir -p /opt/photoprism /usr/local/bin' || fail_safe "Could not install PhotoPrism runtime dependencies."
  log INFO "Installing PhotoPrism package for this architecture"
  proot-distro login ubuntu -- bash -lc "set -Eeuo pipefail; curl -fsSL '$url' -o /tmp/photoprism.tar.gz; rm -rf /opt/photoprism/*; tar -xzf /tmp/photoprism.tar.gz -C /opt/photoprism --strip-components=1; ln -sf /opt/photoprism/bin/photoprism /usr/local/bin/photoprism; /usr/local/bin/photoprism --version >/tmp/photoprism-version.txt 2>/dev/null || true" || fail_safe "Could not install the PhotoPrism package."
}
photoprism_version(){ proot-distro login ubuntu -- bash -lc 'cat /tmp/photoprism-version.txt 2>/dev/null | head -1' 2>/dev/null | tr -d '\r' | sed 's/[[:space:]]\+$//' | head -1; }
ensure_env_file(){
  mkdir -p "$CONFIG_DIR" "$STORAGE_DIR" "$ORIGINALS_DIR" "$IMPORT_DIR" "$LOG_DIR_APP"; chmod 700 "$APP_ROOT" "$CONFIG_DIR" "$STORAGE_DIR" 2>/dev/null || true
  [[ -s "$ENV_FILE" && $(grep -c '^PHOTOPRISM_ADMIN_PASSWORD=' "$ENV_FILE" || true) -gt 0 ]] && return 0
  local admin_password; admin_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"; umask 077
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
  chmod 600 "$ENV_FILE" 2>/dev/null || true
}
start_photoprism_pm2(){ require_cmd pm2; local command="exec proot-distro login ubuntu -- bash -lc 'set -a; source \"$ENV_FILE\"; set +a; exec photoprism start'"; pm2 delete "$PROCESS_NAME" >/dev/null 2>&1 || true; pm2 start bash --name "$PROCESS_NAME" -- -lc "$command" >/dev/null || fail_safe "Could not start the PhotoPrism PM2 process."; pm2 save >/dev/null 2>&1 || true; }
refresh_caddy_if_possible(){
  local helper="$SCRIPT_DIR/restart-caddy-proxy.sh"
  if [[ -x "$helper" ]]; then
    "$helper" || log WARN "Caddy route refresh did not complete; PhotoPrism local health will still be checked"
    return 0
  fi

  require_cmd pm2
  require_cmd caddy
  caddy validate --config "$HOME/pocket-lab-lite/caddy/Caddyfile" >/dev/null 2>&1 || {
    log WARN "Caddyfile validation failed; PhotoPrism local health will still be checked"
    return 0
  }
  pm2 delete caddy-proxy >/dev/null 2>&1 || true
  pm2 start "$(command -v caddy)" --name caddy-proxy -- run --config "$HOME/pocket-lab-lite/caddy/Caddyfile" >/dev/null 2>&1 || {
    log WARN "Caddy route refresh did not complete; PhotoPrism local health will still be checked"
    return 0
  }
  sleep 3
}
wait_for_local_health(){
  for _ in $(seq 1 90); do
    curl -fsS "http://127.0.0.1:2342/apps/photoprism/api/v1/status" >/dev/null 2>&1 && return 0
    curl -fsS "http://127.0.0.1:2342/apps/photoprism/" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}
check_route_health(){
  if curl -fsS "http://127.0.0.1:8443/apps/photoprism/api/v1/status" >/dev/null 2>&1; then
    echo healthy
    return 0
  fi
  if curl -fsS "http://127.0.0.1:8443/apps/photoprism/" >/dev/null 2>&1; then
    echo healthy
    return 0
  fi
  [[ -z "$SECURE_ORIGIN" ]] && { echo unknown; return 0; }
  curl -fsS "$SECURE_ORIGIN$ROUTE_PATH" >/dev/null 2>&1 && echo healthy || echo unknown
}

main(){
  [[ "$APP_ID" == "photoprism" ]] || fail_safe "Unsupported Lite app requested."
  require_termux
  require_cmd python3 curl tar

  local url version route_health
  url="$(arch_package_url)" || fail_safe "PhotoPrism package is not available for this architecture."

  if curl -fsS "http://127.0.0.1:2342/apps/photoprism/api/v1/status" >/dev/null 2>&1; then
    ensure_env_file
    write_route_registry
    refresh_caddy_if_possible
    wait_for_local_health || fail_safe "PhotoPrism did not pass local health checks after startup."
    version="$(photoprism_version)"
    route_health="$(check_route_health)"
    mark_route_health "$route_health"
    write_summary "succeeded" "PhotoPrism is ready." "${version:-detected-or-unknown}" "healthy" "$route_health"
    log INFO "PhotoPrism is already running. Credentials remain stored only on the server host."
    return 0
  fi

  ensure_ubuntu_ready
  install_photoprism_inside_ubuntu "$url"
  ensure_env_file
  write_route_registry
  start_photoprism_pm2
  refresh_caddy_if_possible
  wait_for_local_health || fail_safe "PhotoPrism did not pass local health checks after startup."

  version="$(photoprism_version)"
  route_health="$(check_route_health)"
  mark_route_health "$route_health"
  write_summary "succeeded" "PhotoPrism is ready." "${version:-detected-or-unknown}" "healthy" "$route_health"
  log INFO "PhotoPrism is ready. Credentials remain stored only on the server host."
}
main "$@"
