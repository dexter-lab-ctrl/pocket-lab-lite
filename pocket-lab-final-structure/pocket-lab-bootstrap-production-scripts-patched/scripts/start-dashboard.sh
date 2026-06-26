#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

parse_start_dashboard_args(){
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --profile)
        [[ "${2:-}" != "" ]] || die "--profile requires a value"
        export POCKETLAB_PROFILE="$(normalize_profile "$2")"
        if [[ "$POCKETLAB_PROFILE" == "lite" ]]; then export POCKETLAB_LITE=1; fi
        shift 2
        ;;
      --profile=*)
        export POCKETLAB_PROFILE="$(normalize_profile "${1#--profile=}")"
        if [[ "$POCKETLAB_PROFILE" == "lite" ]]; then export POCKETLAB_LITE=1; fi
        shift
        ;;
      --lite)
        export POCKETLAB_PROFILE="lite"
        export POCKETLAB_LITE=1
        shift
        ;;
      *)
        shift
        ;;
    esac
  done
}
parse_start_dashboard_args "$@"
prepare_lite_state_path(){
  is_lite_profile || return 0
  export POCKETLAB_BASE_DIR="${POCKETLAB_BASE_DIR:-$POCKET_LAB_BASE_DIR}"
  export POCKETLAB_STATE_DIR="${POCKETLAB_STATE_DIR:-$POCKETLAB_BASE_DIR/state}"
  mkdir -p "$POCKETLAB_STATE_DIR"
  log INFO "Lite state directory: $POCKETLAB_STATE_DIR"
}
prepare_lite_state_path
log INFO "Profile: $(normalize_profile "${POCKETLAB_PROFILE:-full}")"
FASTAPI_SERVER="$SCRIPT_DIR/../../runtime/api_fastapi/pocket_lab_fastapi_server.py"
WORKER_SERVER="$SCRIPT_DIR/../../runtime/workers/pocketlab_worker.py"
AGENT_SERVER="$SCRIPT_DIR/../../runtime/agents/pocketlab_node_agent.py"
CORE_SUPERVISOR_SERVER="$SCRIPT_DIR/../../runtime/supervisors/pocketlab_core_supervisor.py"
API_SERVER="${API_SERVER:-$FASTAPI_SERVER}"
PWA_DIR="${PWA_DIR:-$POCKET_LAB_PWA_DIR}"; CADDYFILE="${CADDYFILE:-$POCKET_LAB_CADDYFILE}"; HARDWARE_DAEMON="${HARDWARE_DAEMON:-$POCKET_LAB_HARDWARE_DAEMON}"; OBS_DIR="${OBS_DIR:-$POCKET_LAB_OBSERVABILITY_DIR}"
DASH_PORT="${DASH_PORT:-8443}"; API_PORT="${API_PORT:-8080}"; GATUS_PORT="${GATUS_PORT:-8081}"
get_ts_fqdn(){ if have tailscale; then tailscale status --json 2>/dev/null | jq -r '.Self.DNSName // empty' | sed 's/\.$//' | grep -E '.ts.net$' || true; fi; }

tailscale_command(){
  if have tailscale-cli; then echo tailscale-cli; return 0; fi
  if have tailscale; then echo tailscale; return 0; fi
  return 1
}
tailscaled_is_running(){
  if have pgrep && pgrep -f tailscaled >/dev/null 2>&1; then return 0; fi
  ps -A 2>/dev/null | grep -v grep | grep -q tailscaled
}
start_tailscale_if_missing(){
  is_lite_profile || return 0
  if tailscaled_is_running; then
    log INFO "Lite remote access: tailscaled is already running"
  elif have tailscaled-start; then
    log INFO "Lite remote access: tailscaled is not running; starting with tailscaled-start"
    tailscaled-start >/dev/null 2>&1 || log WARN "Lite remote access: tailscaled-start did not complete successfully"
    sleep 2
  elif have tailscaled; then
    log INFO "Lite remote access: tailscaled is not running; starting tailscaled directly"
    nohup tailscaled --tun=userspace-networking --socks5-server=127.0.0.1:0 > "$LOG_DIR/tailscaled.log" 2>&1 &
    sleep 2
  else
    log WARN "Lite remote access: tailscaled is not installed; remote devices may stay offline"
    return 0
  fi

  local ts_cmd ts_ip
  ts_cmd="$(tailscale_command || true)"
  if [[ -n "$ts_cmd" ]]; then
    ts_ip="$($ts_cmd ip -4 2>/dev/null | head -1 || true)"
    if [[ -n "$ts_ip" ]]; then
      log INFO "Lite remote access: Tailscale IP detected: $ts_ip"
      export POCKETLAB_TAILNET_IP="$ts_ip"
    else
      log WARN "Lite remote access: Tailscale is running but no IPv4 address is available yet"
    fi
  fi
}
verify_lite_remote_nats(){
  is_lite_profile || return 0
  local ts_cmd ts_ip port
  ts_cmd="$(tailscale_command || true)"
  [[ -n "$ts_cmd" ]] || return 0
  ts_ip="$($ts_cmd ip -4 2>/dev/null | head -1 || true)"
  [[ -n "$ts_ip" ]] || return 0
  port="${POCKETLAB_LITE_NATS_PORT:-${POCKETLAB_PUBLIC_NATS_PORT:-4222}}"
  python3 - "$ts_ip" "$port" <<'PYCHECK' || log WARN "Lite remote access: NATS is not reachable on the Tailscale IP yet"
import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
with socket.create_connection((host, port), timeout=2):
    pass
print(f"Lite remote access: NATS reachable on {host}:{port}")
PYCHECK
}

ensure_assets(){
  [[ -f "$API_SERVER" ]] || die "Missing dashboard API server: $API_SERVER"
  [[ -f "$WORKER_SERVER" ]] || die "Missing worker process required for production NATS execution: $WORKER_SERVER"
  [[ -f "$AGENT_SERVER" ]] || log WARN "Missing NATS-backed fleet agent; multi-device live fleet status will be unavailable: $AGENT_SERVER"
  if is_lite_profile; then
    [[ -f "$CORE_SUPERVISOR_SERVER" ]] || die "Missing Lite core supervisor: $CORE_SUPERVISOR_SERVER"
  fi
  have nats-server || die "nats-server is required; production FastAPI/NATS mode does not allow memory fallback"
  python3 - <<'PYCHECK' || die "FastAPI runtime missing; run install-binaries.sh to install fastapi, uvicorn, pydantic, and nats-py"
import importlib.util, sys
required = ("fastapi", "uvicorn", "pydantic", "nats")
sys.exit(0 if all(importlib.util.find_spec(m) for m in required) else 1)
PYCHECK
  if is_lite_profile; then
    mkdir -p "$PWA_DIR" "$POCKET_LAB_API_DIR" "$(dirname "$CADDYFILE")"
  else
    mkdir -p "$PWA_DIR" "$OBS_DIR/loki_data" "$OBS_DIR/gatus" "$POCKET_LAB_API_DIR" "$(dirname "$CADDYFILE")"
  fi
  if [[ ! -f "$PWA_DIR/index.html" ]]; then log INFO "UI assets missing; attempting self-recovery"; bash "$SCRIPT_DIR/install-pwa-ui.sh" || die "Failed to install UI assets"; fi
}
random_secret(){
  if have openssl; then openssl rand -hex 24; else python3 - <<'PYSECRET'
import secrets
print(secrets.token_hex(24))
PYSECRET
  fi
}
ensure_nats_credentials(){
  mkdir -p "$STATE_DIR/nats"
  local cred_file="$STATE_DIR/nats/pocketlab-nats.env"
  if [[ ! -f "$cred_file" ]]; then
    umask 077
    cat > "$cred_file" <<EOF
POCKETLAB_NATS_API_USER=pocketlab_api
POCKETLAB_NATS_API_PASSWORD=$(random_secret)
POCKETLAB_NATS_WORKER_USER=pocketlab_worker
POCKETLAB_NATS_WORKER_PASSWORD=$(random_secret)
POCKETLAB_NATS_AGENT_USER=pocketlab_agent
POCKETLAB_NATS_AGENT_PASSWORD=$(random_secret)
EOF
  fi
  # shellcheck disable=SC1090
  source "$cred_file"
  export POCKETLAB_NATS_API_USER POCKETLAB_NATS_API_PASSWORD POCKETLAB_NATS_WORKER_USER POCKETLAB_NATS_WORKER_PASSWORD POCKETLAB_NATS_AGENT_USER POCKETLAB_NATS_AGENT_PASSWORD
}
write_nats_config(){
  ensure_nats_credentials
  mkdir -p "$STATE_DIR/nats/store"
  local nats_config="$STATE_DIR/nats/nats-server.conf"
  log INFO "Writing production NATS/JetStream config with auth, localhost monitoring, and durable storage"
  cat > "$nats_config" <<EOF
server_name: pocketlab-nats
listen: 0.0.0.0:4222
http: 127.0.0.1:8222
jetstream {
  store_dir: "$STATE_DIR/nats/store"
  max_mem_store: 64MB
  max_file_store: 1GB
}
authorization {
  users: [
    { user: "$POCKETLAB_NATS_API_USER", password: "$POCKETLAB_NATS_API_PASSWORD", permissions: { publish: ["\$JS.API.>", "\$JS.ACK.>", "\$js.ack.>", "pocketlab.commands.>", "pocketlab.events.>", "pocketlab.audit.>", "pocketlab.dlq.>"], subscribe: ["_INBOX.>", "pocketlab.events.>", "pocketlab.audit.>"] } },
    { user: "$POCKETLAB_NATS_WORKER_USER", password: "$POCKETLAB_NATS_WORKER_PASSWORD", permissions: { publish: ["\$JS.API.>", "\$JS.ACK.>", "\$js.ack.>", "pocketlab.events.>", "pocketlab.audit.>", "pocketlab.dlq.>"], subscribe: ["_INBOX.>", "pocketlab.commands.>", "pocketlab.events.>", "pocketlab.audit.>"] } },
    { user: "$POCKETLAB_NATS_AGENT_USER", password: "$POCKETLAB_NATS_AGENT_PASSWORD", permissions: { publish: ["pocketlab.events.fleet.>", "pocketlab.events.telemetry.>", "pocketlab.events.health.>"], subscribe: ["_INBOX.>", "pocketlab.commands.node.>"] } }
  ]
}
EOF
  chmod 600 "$nats_config"
  export POCKETLAB_NATS_CONFIG="$nats_config"
}


pocketlab_lite_detect_tailscale_fqdn() {
  local status_file
  status_file="$(mktemp)"

  if command -v tailscale-cli >/dev/null 2>&1; then
    if ! tailscale-cli status --json > "$status_file" 2>/dev/null; then
      rm -f "$status_file"
      return 1
    fi
  elif command -v tailscale >/dev/null 2>&1; then
    if ! tailscale status --json > "$status_file" 2>/dev/null; then
      rm -f "$status_file"
      return 1
    fi
  else
    rm -f "$status_file"
    return 1
  fi

  python3 - "$status_file" <<'PYTAILSCALE'
import json
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text())
except Exception:
    raise SystemExit(1)

fqdn = ((data.get("Self") or {}).get("DNSName") or "").strip().rstrip(".")
if not fqdn.endswith(".ts.net"):
    raise SystemExit(1)

print(fqdn)
PYTAILSCALE

  local rc=$?
  rm -f "$status_file"
  return "$rc"
}

pocketlab_lite_prepare_tailscale_cert() {
  local fqdn="$1"
  local cert_dir="$HOME/.pocket_lab/tailscale-certs"
  local cert_path="$cert_dir/${fqdn}.crt"
  local key_path="$cert_dir/${fqdn}.key"

  if [[ -z "$fqdn" ]]; then
    return 1
  fi

  if ! command -v tailscale-cli >/dev/null 2>&1; then
    return 1
  fi

  mkdir -p "$cert_dir"
  chmod 700 "$cert_dir"

  if [[ ! -s "$cert_path" || ! -s "$key_path" ]]; then
    (
      cd "$HOME"
      rm -f "$HOME/${fqdn}.crt" "$HOME/${fqdn}.key"
      tailscale-cli cert "$fqdn" >/dev/null
      mv -f "$HOME/${fqdn}.crt" "$cert_path"
      mv -f "$HOME/${fqdn}.key" "$key_path"
      chmod 644 "$cert_path"
      chmod 600 "$key_path"
    ) || return 1
  fi

  [[ -s "$cert_path" && -s "$key_path" ]]
}

write_caddy_site() {
  local site_label="$1"
  local tls_line="${2:-}"

  printf '%s {\n' "$site_label"

  if [[ -n "$tls_line" ]]; then
    printf '  %s\n' "$tls_line"
  fi

  cat <<EOF
  encode gzip zstd
  header X-Content-Type-Options "nosniff"
  header X-Frame-Options "DENY"
  header Referrer-Policy "no-referrer"

  handle /health {
    reverse_proxy 127.0.0.1:${API_PORT}
  }
  handle /ready {
    reverse_proxy 127.0.0.1:${API_PORT}
  }
  handle /healthz {
    reverse_proxy 127.0.0.1:${API_PORT}
  }
  handle /api/* {
    reverse_proxy 127.0.0.1:${API_PORT}
  }
  handle /openapi.json {
    reverse_proxy 127.0.0.1:${API_PORT}
  }
  handle /docs* {
    reverse_proxy 127.0.0.1:${API_PORT}
  }
  handle /redoc* {
    reverse_proxy 127.0.0.1:${API_PORT}
  }
  handle /ws/* {
    reverse_proxy 127.0.0.1:${API_PORT}
  }
  handle /gitea/* {
    reverse_proxy 127.0.0.1:3030
  }

  handle {
    root * ${PWA_DIR}
    try_files {path} /index.html
    file_server
  }
}
EOF
}

write_caddyfile(){
  local tailscale_fqdn cert_dir
  log INFO "Writing Caddyfile idempotently"

  {
    write_caddy_site ":${DASH_PORT}"

    if is_lite_profile; then
      if tailscale_fqdn="$(pocketlab_lite_detect_tailscale_fqdn)"; then
        if pocketlab_lite_prepare_tailscale_cert "$tailscale_fqdn"; then
          cert_dir="$HOME/.pocket_lab/tailscale-certs"
          write_caddy_site "$tailscale_fqdn" "tls ${cert_dir}/${tailscale_fqdn}.crt ${cert_dir}/${tailscale_fqdn}.key"
          log INFO "Tailscale HTTPS enabled for ${tailscale_fqdn}"
        else
          log WARN "Tailscale HTTPS cert could not be prepared; keeping local :${DASH_PORT} listener only"
        fi
      else
        log WARN "Tailscale FQDN not detected; keeping local :${DASH_PORT} listener only"
      fi
    else
      local fqdn
      fqdn="$(get_ts_fqdn || true)"
      if [[ -n "$fqdn" ]]; then
        write_caddy_site "$fqdn" "tls {
    get_certificate tailscale
  }"
      fi
    fi
  } | atomic_write "$CADDYFILE" 0644
}


main(){
  SCRIPT_NAME="start-dashboard.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_termux; require_cmd python3 caddy curl pm2 jq nats-server
  ensure_assets; start_tailscale_if_missing; write_hardware_daemon; write_caddyfile; write_observability_configs; start_pm2_daemons; verify_lite_remote_nats; mark_done dashboard_ready
  log INFO "Dashboard/control-plane services are ready and safe to rerun"
}
main "$@"
