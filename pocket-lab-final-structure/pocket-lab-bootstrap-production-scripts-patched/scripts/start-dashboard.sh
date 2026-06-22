#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
FASTAPI_SERVER="$SCRIPT_DIR/../../runtime/api_fastapi/pocket_lab_fastapi_server.py"
WORKER_SERVER="$SCRIPT_DIR/../../runtime/workers/pocketlab_worker.py"
AGENT_SERVER="$SCRIPT_DIR/../../runtime/agents/pocketlab_node_agent.py"
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
    { user: "$POCKETLAB_NATS_API_USER", password: "$POCKETLAB_NATS_API_PASSWORD", permissions: { publish: ["\$JS.API.>", "pocketlab.commands.>", "pocketlab.events.>", "pocketlab.audit.>", "pocketlab.dlq.>"], subscribe: ["_INBOX.>", "pocketlab.events.>", "pocketlab.audit.>"] } },
    { user: "$POCKETLAB_NATS_WORKER_USER", password: "$POCKETLAB_NATS_WORKER_PASSWORD", permissions: { publish: ["\$JS.API.>", "pocketlab.events.>", "pocketlab.audit.>", "pocketlab.dlq.>"], subscribe: ["_INBOX.>", "pocketlab.commands.>"] } },
    { user: "$POCKETLAB_NATS_AGENT_USER", password: "$POCKETLAB_NATS_AGENT_PASSWORD", permissions: { publish: ["pocketlab.events.fleet.>", "pocketlab.events.telemetry.>", "pocketlab.events.health.>"], subscribe: ["_INBOX.>", "pocketlab.commands.node.>"] } }
  ]
}
EOF
  chmod 600 "$nats_config"
  export POCKETLAB_NATS_CONFIG="$nats_config"
}

write_caddyfile(){
  local fqdn loki_route
  fqdn="$(get_ts_fqdn || true)"
  loki_route=""
  if ! is_lite_profile; then
    loki_route="$loki_route"
  fi
  log INFO "Writing Caddyfile idempotently"
  if [[ -n "$fqdn" && ! is_lite_profile ]]; then
    cat <<EOF | atomic_write "$CADDYFILE" 0644
$fqdn {
  tls {
    get_certificate tailscale
  }
  encode gzip zstd
  header Strict-Transport-Security "max-age=31536000; includeSubDomains"
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
$loki_route
  handle {
    root * ${PWA_DIR}
    try_files {path} /index.html
    file_server
  }
}
EOF
  else
    cat <<EOF | atomic_write "$CADDYFILE" 0644
:${DASH_PORT} {
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
$loki_route
  handle {
    root * ${PWA_DIR}
    try_files {path} /index.html
    file_server
  }
}
EOF
  fi
  caddy validate --config "$CADDYFILE" >/dev/null
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

start_pm2_daemons(){
  log INFO "Starting/restarting dashboard services with PM2"
  pm2_start_or_restart pocket-telemetry "$HARDWARE_DAEMON" --interpreter python3 --exp-backoff-restart-delay 100
  write_nats_config
  pm2_start_or_restart pocket-nats nats-server -- -c "$POCKETLAB_NATS_CONFIG"
  if [[ "${POCKETLAB_DISABLE_WORKER:-0}" != "1" ]]; then
    POCKETLAB_NATS_REQUIRED=1 POCKETLAB_NATS_REQUIRE_JETSTREAM=1 POCKETLAB_NATS_JETSTREAM=1 POCKETLAB_WORKER_EXECUTION=worker POCKETLAB_NATS_USER="$POCKETLAB_NATS_WORKER_USER" POCKETLAB_NATS_PASSWORD="$POCKETLAB_NATS_WORKER_PASSWORD" POCKETLAB_NATS_NAME=pocketlab-worker POCKETLAB_COMMAND_MAX_DELIVER="${POCKETLAB_COMMAND_MAX_DELIVER:-5}" POCKETLAB_COMMAND_ACK_WAIT_SECONDS="${POCKETLAB_COMMAND_ACK_WAIT_SECONDS:-60}" pm2_start_or_restart pocket-worker "$WORKER_SERVER" --interpreter python3 --update-env
  else
    die "POCKETLAB_DISABLE_WORKER=1 is not allowed in production NATS mode"
  fi
  if [[ -f "$AGENT_SERVER" && "${POCKETLAB_DISABLE_FLEET_AGENT:-0}" != "1" ]]; then
    POCKETLAB_NATS_USER="$POCKETLAB_NATS_AGENT_USER" POCKETLAB_NATS_PASSWORD="$POCKETLAB_NATS_AGENT_PASSWORD" POCKETLAB_NATS_NAME=pocketlab-node-agent pm2_start_or_restart pocket-node-agent "$AGENT_SERVER" --interpreter python3 --update-env
  else
    log WARN "Pocket Lab node agent not started; this control plane will not publish NATS fleet heartbeats"
  fi
  POCKETLAB_NATS_REQUIRED=1 POCKETLAB_NATS_REQUIRE_JETSTREAM=1 POCKETLAB_NATS_JETSTREAM=1 POCKETLAB_WORKER_EXECUTION=worker POCKETLAB_NATS_USER="$POCKETLAB_NATS_API_USER" POCKETLAB_NATS_PASSWORD="$POCKETLAB_NATS_API_PASSWORD" POCKETLAB_AGENT_NATS_USER="$POCKETLAB_NATS_AGENT_USER" POCKETLAB_AGENT_NATS_PASSWORD="$POCKETLAB_NATS_AGENT_PASSWORD" POCKETLAB_NATS_NAME=pocketlab-fastapi POCKETLAB_COMMAND_MAX_DELIVER="${POCKETLAB_COMMAND_MAX_DELIVER:-5}" POCKETLAB_COMMAND_ACK_WAIT_SECONDS="${POCKETLAB_COMMAND_ACK_WAIT_SECONDS:-60}" pm2_start_or_restart pocket-api "$API_SERVER" --interpreter python3 --update-env
  pm2_start_or_restart caddy-proxy caddy -- run --config "$CADDYFILE"
  if is_lite_profile; then
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
main(){
  SCRIPT_NAME="start-dashboard.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_termux; require_cmd python3 caddy curl pm2 jq nats-server
  ensure_assets; start_tailscale_if_missing; write_hardware_daemon; write_caddyfile; write_observability_configs; start_pm2_daemons; verify_lite_remote_nats; mark_done dashboard_ready
  log INFO "Dashboard/control-plane services are ready and safe to rerun"
}
main "$@"
