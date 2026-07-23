#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

parse_start_dashboard_args(){
  export POCKETLAB_RENDER_CADDY_ONLY="${POCKETLAB_RENDER_CADDY_ONLY:-0}"
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
      --caddy-only)
        export POCKETLAB_RENDER_CADDY_ONLY=1
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
  export POCKETLAB_LITE_DB_PATH="${POCKETLAB_LITE_DB_PATH:-$POCKETLAB_STATE_DIR/pocketlab-lite.sqlite3}"
  export POCKETLAB_LITE_SECURITY_STORE_MODE="${POCKETLAB_LITE_SECURITY_STORE_MODE:-dual}"
  export POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS="${POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS:-1}"
  export POCKETLAB_LITE_DB_PROGRESS_READ_TIMEOUT_MS="${POCKETLAB_LITE_DB_PROGRESS_READ_TIMEOUT_MS:-250}"
  export POCKETLAB_NATS_DURABLE_STALE_SECONDS="${POCKETLAB_NATS_DURABLE_STALE_SECONDS:-15}"
  export POCKETLAB_WORKER_RECOVERY_SECONDS="${POCKETLAB_WORKER_RECOVERY_SECONDS:-10}"
  export POCKETLAB_LITE_SECURITY_ACCEPTED_STALE_SECONDS="${POCKETLAB_LITE_SECURITY_ACCEPTED_STALE_SECONDS:-120}"
  export POCKETLAB_LITE_SECURITY_PUBLISHED_STALE_SECONDS="${POCKETLAB_LITE_SECURITY_PUBLISHED_STALE_SECONDS:-120}"
  export POCKETLAB_LITE_SECURITY_RECEIVED_STALE_SECONDS="${POCKETLAB_LITE_SECURITY_RECEIVED_STALE_SECONDS:-180}"
  export POCKETLAB_WORKER_ACCEPTED_RECOVERY_GRACE_SECONDS="${POCKETLAB_WORKER_ACCEPTED_RECOVERY_GRACE_SECONDS:-15}"
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
  local status_file tmp_base
  tmp_base="${TMPDIR:-$HOME/tmp}"
  mkdir -p "$tmp_base"
  status_file="$(mktemp "$tmp_base/tailscale-status.XXXXXX.json")"

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

pocketlab_lite_cert_needs_refresh() {
  local cert_path="$1"

  if [[ ! -s "$cert_path" ]]; then
    return 0
  fi

  if command -v openssl >/dev/null 2>&1; then
    if ! openssl x509 -checkend 1209600 -noout -in "$cert_path" >/dev/null 2>&1; then
      return 0
    fi
  fi

  return 1
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

  if pocketlab_lite_cert_needs_refresh "$cert_path" || [[ ! -s "$key_path" ]]; then
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


write_caddy_app_routes() {
  local portal_origin="${1:-}"
  local routes_file="${POCKETLAB_LITE_APP_ROUTES:-${POCKETLAB_STATE_DIR:-$STATE_DIR}/app_routes.json}"

  [[ -s "$routes_file" ]] || return 0
  command -v python3 >/dev/null 2>&1 || return 0

  python3 - "$routes_file" "$portal_origin" <<'PYCADDYROUTES'
import json
import re
import sys
from pathlib import Path
try:
    data = json.loads(Path(sys.argv[1]).read_text())
except Exception:
    raise SystemExit(0)
portal_origin = str(sys.argv[2] if len(sys.argv) > 2 else "")
portal_embed_ready = bool(re.fullmatch(r"https://[A-Za-z0-9.-]+\.ts\.net", portal_origin))
for route in data.get("routes", []):
    if not isinstance(route, dict) or not route.get("enabled"):
        continue
    app_id = str(route.get("app_id") or "")
    path = str(route.get("path") or "")
    upstream = str(route.get("upstream") or "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", app_id):
        continue
    if not path.startswith("/apps/") or not path.endswith("/"):
        continue
    if ".." in path or "//" in path:
        continue
    if not re.fullmatch(r"(127\.0\.0\.1|localhost):[0-9]{2,5}", upstream):
        continue
    print(f"  handle {path}* {{")
    if app_id == "photoprism" and portal_embed_ready:
        print("    header -X-Frame-Options")
        print(f"    header Content-Security-Policy \"frame-ancestors 'self' {portal_origin}\"")
        print(f"    reverse_proxy {upstream} {{")
        print("      header_down -X-Frame-Options")
        print("      header_down -Content-Security-Policy")
        print("    }")
    else:
        print(f"    reverse_proxy {upstream}")
    print("  }")
    print("")
PYCADDYROUTES
}

validate_caddyfile() {
  if command -v caddy >/dev/null 2>&1; then
    caddy validate --config "$CADDYFILE" >/dev/null
  fi
}

write_caddy_site() {
  local site_label="$1"
  local tls_block="${2:-}"

  printf '%s {\n' "$site_label"

  if [[ -n "$tls_block" ]]; then
    printf '%b\n' "$tls_block"
    printf '  header Strict-Transport-Security "max-age=31536000; includeSubDomains"\n'
  fi

  cat <<EOF
  encode gzip zstd
  header X-Content-Type-Options "nosniff"
  @pocketlab_non_app_routes {
    not path /apps/*
  }
  header @pocketlab_non_app_routes X-Frame-Options "DENY"
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
  handle /api/lite/security/events {
    reverse_proxy 127.0.0.1:${API_PORT} {
      flush_interval -1
    }
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
  @pocketlab_versioned_assets {
    path /assets/*
  }
  header @pocketlab_versioned_assets Cache-Control "public, max-age=31536000, immutable"

  @pocketlab_runtime_assets {
    path /icon.svg /manifest.webmanifest /registerSW.js /sw.js /workbox-*.js
  }
  header @pocketlab_runtime_assets Cache-Control "no-cache"

  handle /gitea/* {
    reverse_proxy 127.0.0.1:3030
  }

  handle /assets/* {
    root * ${PWA_DIR}
    file_server
  }
  handle /icon.svg {
    root * ${PWA_DIR}
    file_server
  }
  handle /manifest.webmanifest {
    root * ${PWA_DIR}
    file_server
  }
  handle /registerSW.js {
    root * ${PWA_DIR}
    file_server
  }
  handle /sw.js {
    root * ${PWA_DIR}
    file_server
  }
  handle /workbox-*.js {
    root * ${PWA_DIR}
    file_server
  }

EOF

  if [[ -n "$tls_block" && "$site_label" == *.ts.net ]]; then
    write_caddy_app_routes "https://${site_label}"
  else
    write_caddy_app_routes
  fi

  cat <<EOF
  handle {
    root * ${PWA_DIR}
    try_files {path} /index.html
    file_server
  }
}
EOF
}

write_caddyfile(){
  local fqdn tailscale_fqdn cert_dir tls_block
  log INFO "Writing Caddyfile idempotently"

  if is_lite_profile; then
    tailscale_fqdn=""
    tls_block=""

    if tailscale_fqdn="$(pocketlab_lite_detect_tailscale_fqdn)"; then
      if pocketlab_lite_prepare_tailscale_cert "$tailscale_fqdn"; then
        cert_dir="$HOME/.pocket_lab/tailscale-certs"
        tls_block="  tls ${cert_dir}/${tailscale_fqdn}.crt ${cert_dir}/${tailscale_fqdn}.key"
        log INFO "Tailscale HTTPS enabled for ${tailscale_fqdn}"
      else
        log WARN "Tailscale HTTPS cert could not be prepared; keeping local :${DASH_PORT} listener only"
        tailscale_fqdn=""
      fi
    else
      log WARN "Tailscale FQDN not detected; keeping local :${DASH_PORT} listener only"
      tailscale_fqdn=""
    fi

    {
      write_caddy_site ":${DASH_PORT}"
      if [[ -n "$tailscale_fqdn" && -n "$tls_block" ]]; then
        write_caddy_site "$tailscale_fqdn" "$tls_block"
      fi
    } | atomic_write "$CADDYFILE" 0644
    return
  fi

  fqdn="$(get_ts_fqdn || true)"
  if [[ -n "$fqdn" ]]; then
    {
      write_caddy_site "$fqdn" "  tls {
    get_certificate tailscale
  }"
    } | atomic_write "$CADDYFILE" 0644
  else
    {
      write_caddy_site ":${DASH_PORT}"
    } | atomic_write "$CADDYFILE" 0644
  fi
}


write_hardware_daemon(){
  log INFO "Writing Android-compatible telemetry daemon"
  cat > "$HARDWARE_DAEMON" <<'PYD'
#!/usr/bin/env python3
import json, time, os
API_DIR=os.environ.get('POCKET_LAB_API_DIR', os.path.expanduser('~/pocket-lab-lite/api'))
TELEMETRY_FILE=os.path.join(API_DIR,'telemetry.json')
def thermal():
    for z in range(30):
        p=f'/sys/class/thermal/thermal_zone{z}/temp'
        try:
            if os.path.exists(p):
                v=int(open(p).read().strip()); return v/1000.0 if v>1000 else float(v)
        except Exception: pass
    return 42.0
def storage():
    try:
        st=os.statvfs(os.path.expanduser('~')); return (st.f_bavail*st.f_frsize)//(1024*1024)
    except Exception: return 256000
def memory():
    try:
        vals={}
        for line in open('/proc/meminfo'):
            k=line.split(':',1)[0]; vals[k]=int(line.split()[1])
        total=vals.get('MemTotal',0); avail=vals.get('MemAvailable',vals.get('MemFree',0)); return max(0,(total-avail)//1024)
    except Exception: return 2048
def cpu():
    try:
        parts=list(map(int,open('/proc/stat').readline().split()[1:])); return sum(parts), parts[3]
    except Exception: return 0,0
os.makedirs(API_DIR, exist_ok=True); pt,pi=cpu()
while True:
    time.sleep(2); ct,ci=cpu(); usage=12.0
    if ct>pt: usage=round(100.0*(1.0-((ci-pi)/(ct-pt))),1)
    pt,pi=ct,ci
    data={'cpu_temp_c':round(thermal(),1),'free_space_mb':storage(),'cpu_usage_percent':usage,'memory_usage_mb':memory(),'error':False}
    tmp=TELEMETRY_FILE+'.tmp'; open(tmp,'w').write(json.dumps(data)); os.replace(tmp,TELEMETRY_FILE); time.sleep(8)
PYD
  chmod +x "$HARDWARE_DAEMON"
}
write_observability_configs(){
  if is_lite_profile; then
    log INFO "Lite profile: skipping observability config generation"
    return 0
  fi
  log INFO "Writing observability configs idempotently"
  cat <<EOF | atomic_write "$OBS_DIR/loki-config.yaml" 0644
auth_enabled: false
server:
  http_listen_port: 3100
  http_listen_address: 127.0.0.1
  grpc_listen_address: 127.0.0.1
common:
  instance_addr: 127.0.0.1
  path_prefix: $OBS_DIR/loki_data
  storage:
    filesystem:
      chunks_directory: $OBS_DIR/loki_data/chunks
      rules_directory: $OBS_DIR/loki_data/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore: { store: inmemory }
schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index: { prefix: index_, period: 24h }
frontend:
  instance_interface_names: [lo]
EOF
  cat <<EOF | atomic_write "$OBS_DIR/promtail-config.yaml" 0644
server: { http_listen_port: 9080, grpc_listen_port: 0 }
positions: { filename: $OBS_DIR/positions.yaml }
clients:
  - url: http://127.0.0.1:3100/loki/api/v1/push
scrape_configs:
- job_name: system_logs
  static_configs:
  - targets: [localhost]
    labels: { job: pm2_logs, __path__: /data/data/com.termux/files/home/.pm2/logs/*.log }
EOF
  cat <<EOF | atomic_write "$OBS_DIR/prometheus.yml" 0644
global: { scrape_interval: 15s, evaluation_interval: 15s }
scrape_configs:
  - job_name: prometheus
    static_configs: [{ targets: ["127.0.0.1:9090"] }]
  - job_name: vault
    metrics_path: /v1/sys/metrics
    params: { format: [prometheus] }
    static_configs: [{ targets: ["127.0.0.1:8200"] }]
EOF
  cat <<EOF | atomic_write "$OBS_DIR/gatus-config.yaml" 0644
web: { port: ${GATUS_PORT} }
ui:
  title: Pocket Lab Health Engine
  description: Dependency-aware health dashboard for Pocket Lab.
endpoints:
  - { name: pocket-lab-api, group: core, url: http://127.0.0.1:${API_PORT}/health, interval: 30s, conditions: ["[STATUS] == 200", "[BODY].status == ok"] }
  - { name: pocket-lab-ready, group: core, url: http://127.0.0.1:${API_PORT}/ready, interval: 30s, conditions: ["[STATUS] == 200"] }
  - { name: gitea, group: platform, url: http://127.0.0.1:3030/api/healthz, interval: 30s, conditions: ["[STATUS] == 200"] }
  - { name: vault, group: platform, url: http://127.0.0.1:8200/v1/sys/health?standbyok=true, interval: 30s, conditions: ["[STATUS] == any(200, 429)"] }
  - { name: loki, group: observability, url: http://127.0.0.1:3100/ready, interval: 30s, conditions: ["[STATUS] == 200"] }
  - { name: prometheus, group: observability, url: http://127.0.0.1:9090/-/ready, interval: 30s, conditions: ["[STATUS] == 200"] }
  - { name: grafana, group: observability, url: http://127.0.0.1:3050/api/health, interval: 30s, conditions: ["[STATUS] == 200"] }
EOF
  cat <<EOF | atomic_write "$OBS_DIR/custom.ini" 0644
[server]
http_port = 3050
http_addr = 0.0.0.0
[paths]
data = data
logs = data/log
plugins = data/plugins
provisioning = conf/provisioning
EOF
  if proot_ubuntu_ready; then proot-distro login ubuntu -- bash -c "mkdir -p /opt/grafana/data/log /opt/grafana/data/plugins /opt/grafana/conf/provisioning && chmod -R 755 /opt/grafana/data /opt/grafana/conf" || true; fi
}
proot_ubuntu_ready() {
  have proot-distro || return 1
  proot-distro login ubuntu -- true >/dev/null 2>&1
}

wait_for_nats_ready(){
  local url="http://127.0.0.1:8222/healthz"
  local i
  for i in $(seq 1 30); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log INFO "NATS monitor is ready at $url"
      return 0
    fi
    sleep 1
  done
  pm2 logs pocket-nats --lines 80 --nostream || true
  die "NATS did not become ready at $url"
}

start_pm2_daemons(){
  log INFO "Starting/restarting dashboard services with PM2"
  pm2_start_or_restart pocket-telemetry "$HARDWARE_DAEMON" --interpreter python3 --exp-backoff-restart-delay 100
  write_nats_config
  pm2_start_or_restart pocket-nats nats-server -- -c "$POCKETLAB_NATS_CONFIG"
  wait_for_nats_ready
  if [[ "${POCKETLAB_DISABLE_WORKER:-0}" != "1" ]]; then
    POCKETLAB_NATS_REQUIRED=1 POCKETLAB_NATS_REQUIRE_JETSTREAM=1 POCKETLAB_NATS_JETSTREAM=1 POCKETLAB_WORKER_EXECUTION=worker POCKETLAB_NATS_EVENT_FANOUT=0 POCKETLAB_NATS_USER="$POCKETLAB_NATS_WORKER_USER" POCKETLAB_NATS_PASSWORD="$POCKETLAB_NATS_WORKER_PASSWORD" POCKETLAB_NATS_NAME=pocketlab-worker POCKETLAB_COMMAND_MAX_DELIVER="${POCKETLAB_COMMAND_MAX_DELIVER:-5}" POCKETLAB_COMMAND_ACK_WAIT_SECONDS="${POCKETLAB_COMMAND_ACK_WAIT_SECONDS:-60}" pm2_start_or_restart pocket-worker "$WORKER_SERVER" --interpreter python3 --update-env
  else
    die "POCKETLAB_DISABLE_WORKER=1 is not allowed in production NATS mode"
  fi
  if [[ -f "$AGENT_SERVER" && "${POCKETLAB_DISABLE_FLEET_AGENT:-0}" != "1" ]]; then
    POCKETLAB_NODE_ID="${POCKETLAB_SERVER_NODE_ID:-pocket-lab-lite-server}" POCKETLAB_NODE_NAME="${POCKETLAB_DEVICE_NAME:-Pocket Lab Lite Server}" POCKETLAB_NODE_ROLE=server_host POCKETLAB_IS_CONTROL_PLANE=1 POCKETLAB_NATS_USER="$POCKETLAB_NATS_AGENT_USER" POCKETLAB_NATS_PASSWORD="$POCKETLAB_NATS_AGENT_PASSWORD" POCKETLAB_NATS_NAME=pocketlab-node-agent pm2_start_or_restart pocket-node-agent "$AGENT_SERVER" --interpreter python3 --update-env
  else
    log WARN "Pocket Lab node agent not started; this control plane will not publish NATS fleet heartbeats"
  fi
  POCKETLAB_NATS_REQUIRED=1 POCKETLAB_NATS_REQUIRE_JETSTREAM=1 POCKETLAB_NATS_JETSTREAM=1 POCKETLAB_WORKER_EXECUTION=worker POCKETLAB_NATS_USER="$POCKETLAB_NATS_API_USER" POCKETLAB_NATS_PASSWORD="$POCKETLAB_NATS_API_PASSWORD" POCKETLAB_AGENT_NATS_USER="$POCKETLAB_NATS_AGENT_USER" POCKETLAB_AGENT_NATS_PASSWORD="$POCKETLAB_NATS_AGENT_PASSWORD" POCKETLAB_NATS_NAME=pocketlab-fastapi POCKETLAB_COMMAND_MAX_DELIVER="${POCKETLAB_COMMAND_MAX_DELIVER:-5}" POCKETLAB_COMMAND_ACK_WAIT_SECONDS="${POCKETLAB_COMMAND_ACK_WAIT_SECONDS:-60}" pm2_start_or_restart pocket-api "$API_SERVER" --interpreter python3 --update-env
  validate_caddyfile
  pm2_start_or_restart caddy-proxy "$(command -v caddy)" -- run --config "$CADDYFILE"
  if is_lite_profile; then
    POCKETLAB_CORE_SUPERVISOR_INTERVAL_SECONDS="${POCKETLAB_CORE_SUPERVISOR_INTERVAL_SECONDS:-45}" POCKETLAB_CORE_SUPERVISOR_COOLDOWN_SECONDS="${POCKETLAB_CORE_SUPERVISOR_COOLDOWN_SECONDS:-120}" pm2_start_or_restart pocketlab-core-supervisor "$CORE_SUPERVISOR_SERVER" --interpreter python3 --update-env
    log INFO "Lite profile: started Pocket Lab Lite core supervisor"
    log INFO "Lite profile: skipping Gatus, Loki, Promtail, Prometheus, and Grafana PM2 services"
  else
    if have gatus; then
      pm2_start_or_restart pocket-gatus bash -- -c "GATUS_CONFIG_PATH=$OBS_DIR/gatus-config.yaml gatus"
    else
      log WARN "gatus missing; health UI will use API fallback"
    fi
    if proot_ubuntu_ready; then
      pm2_start_or_restart loki-kms bash -- -c "proot-distro login ubuntu -- /usr/local/bin/loki -config.file=$OBS_DIR/loki-config.yaml" || true
      pm2_start_or_restart promtail-agent bash -- -c "proot-distro login ubuntu -- /usr/local/bin/promtail -config.file=$OBS_DIR/promtail-config.yaml" || true
      pm2_start_or_restart prometheus-db bash -- -c "proot-distro login ubuntu -- /usr/local/bin/prometheus --config.file=$OBS_DIR/prometheus.yml --storage.tsdb.path=$OBS_DIR/prom_data --web.listen-address=127.0.0.1:9090" || true
      pm2_start_or_restart grafana-ui bash -- -c "proot-distro login ubuntu -- bash -c 'cd /opt/grafana && ./bin/grafana-server --homepath=/opt/grafana --config=$OBS_DIR/custom.ini'" || true
    else
      log WARN "PRoot Ubuntu unavailable; skipping Loki/Promtail/Prometheus/Grafana PM2 processes"
    fi
  fi
  pm2 save >/dev/null || true
}
start_caddy_only(){
  SCRIPT_NAME="start-dashboard.sh"
  acquire_lock "$SCRIPT_NAME"
  ensure_root_dirs
  require_termux
  require_cmd python3 caddy pm2
  start_tailscale_if_missing
  write_caddyfile
  validate_caddyfile
  pm2_start_or_restart caddy-proxy "$(command -v caddy)" -- run --config "$CADDYFILE"
  pm2 save >/dev/null || true
  log INFO "Caddy proxy configuration is updated and safe to rerun"
}

main(){
  if [[ "${POCKETLAB_RENDER_CADDY_ONLY:-0}" == "1" ]]; then
    start_caddy_only
    return
  fi
  SCRIPT_NAME="start-dashboard.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_termux; require_cmd python3 caddy curl pm2 jq nats-server
  ensure_assets; start_tailscale_if_missing; write_hardware_daemon; write_caddyfile; write_observability_configs; start_pm2_daemons; verify_lite_remote_nats; mark_done dashboard_ready
  log INFO "Dashboard/control-plane services are ready and safe to rerun"
}
main "$@"
