#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

GITEA_HOME="${GITEA_HOME:-$POCKET_LAB_GITEA_DIR}"
GITEA_CONF_DIR="$GITEA_HOME/conf"
GITEA_RUNTIME_CONF="$GITEA_CONF_DIR/app.runtime.ini"
GITEA_BASE_CONF="$GITEA_CONF_DIR/app.ini"
GITEA_HTTP_PORT="${GITEA_HTTP_PORT:-3030}"
GITEA_ADMIN_USER="${GITEA_ADMIN_USER:-pocket_admin}"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
SERVICE_SECRETS_FILE="${SERVICE_SECRETS_FILE:-$STATE_DIR/service-secrets.env}"
ACT_RUNNER_HOME="${ACT_RUNNER_HOME:-$POCKET_LAB_GITEA_RUNNERS_DIR}"
ACT_RUNNER_CONFIG="$ACT_RUNNER_HOME/config.yaml"
GITEA_RUNNER_NAME="${GITEA_RUNNER_NAME:-pocket-lab-android}"
GITEA_RUNNER_LABELS="${GITEA_RUNNER_LABELS:-ubuntu-latest:host,linux-arm64:host}"
MYSQL_SOCKET="${MYSQL_SOCKET:-$PREFIX/var/run/mysqld/mysqld.sock}"

secret64() {
  python3 - <<'PYSECRET'
import secrets, string
alphabet = string.ascii_letters + string.digits
print(''.join(secrets.choice(alphabet) for _ in range(64)))
PYSECRET
}

ensure_config() {
  mkdir -p "$GITEA_CONF_DIR" "$GITEA_HOME/data" "$GITEA_HOME/log"
  if [[ ! -f "$GITEA_BASE_CONF" ]]; then
    log INFO "Creating base Gitea config"
    local secret
    secret="$(secret64)"
    cat <<EOF_CONF | atomic_write "$GITEA_BASE_CONF" 0600
APP_NAME = Pocket Lab GitOps Repository
RUN_MODE = prod
[security]
INSTALL_LOCK = true
SECRET_KEY = ${secret}
[server]
HTTP_PORT = ${GITEA_HTTP_PORT}
DISABLE_SSH = true
OFFLINE_MODE = true
ROOT_URL = http://127.0.0.1:${GITEA_HTTP_PORT}/
[database]
DB_TYPE = mysql
HOST = 127.0.0.1:3306
NAME = gitea
USER = gitea
PASSWD =
SSL_MODE = disable
EOF_CONF
  else
    log INFO "Base Gitea config already exists"
  fi
}

get_secret() {
  local field="$1" env_name="$2" val=""
  if have vault && VAULT_ADDR="$VAULT_ADDR" vault status >/dev/null 2>&1; then
    export VAULT_ADDR
    val="$(vault kv get -field="$field" secret/gitea 2>/dev/null || true)"
  fi
  if [[ -z "$val" && -f "$SERVICE_SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$SERVICE_SECRETS_FILE"
    val="${!env_name:-}"
  fi
  printf '%s' "$val"
}

build_runtime_config() {
  local pass="$1"
  cp -f "$GITEA_BASE_CONF" "$GITEA_RUNTIME_CONF"
  python3 - "$GITEA_RUNTIME_CONF" "$pass" <<'PYCFG'
from pathlib import Path
import sys

path = Path(sys.argv[1])
password = sys.argv[2]
lines = path.read_text().splitlines()
out = []
section = None
in_database = False
saw_database = False
set_pass = False

for line in lines:
    stripped = line.strip()
    if stripped.startswith('[') and stripped.endswith(']'):
        if in_database and not set_pass:
            out.append(f'PASSWD = {password}')
            set_pass = True
        section = stripped[1:-1].strip().lower()
        in_database = section == 'database'
        if in_database:
            saw_database = True
        out.append(line)
        continue
    if in_database and stripped.startswith('PASSWD'):
        out.append(f'PASSWD = {password}')
        set_pass = True
    else:
        out.append(line)

if in_database and not set_pass:
    out.append(f'PASSWD = {password}')
if not saw_database:
    out.extend(['[database]', 'DB_TYPE = mysql', 'HOST = 127.0.0.1:3306', 'NAME = gitea', 'USER = gitea', f'PASSWD = {password}', 'SSL_MODE = disable'])

path.write_text('\n'.join(out) + '\n')
PYCFG
  chmod 600 "$GITEA_RUNTIME_CONF"
}

start_gitea_pm2() {
  pm2_start_or_restart gitea bash -- -lc "until mariadb --protocol=socket -uroot -S '$MYSQL_SOCKET' -e 'SELECT 1;' >/dev/null 2>&1; do echo 'waiting for mariadb before starting gitea'; sleep 5; done; exec gitea web -c '$GITEA_RUNTIME_CONF'"
}

bootstrap_admin_user() {
  local ui_pass="$1"
  log INFO "Ensuring Gitea admin user"
  gitea admin user create --username "$GITEA_ADMIN_USER" --password "$ui_pass" --email admin@pocketlab.local --admin -c "$GITEA_RUNTIME_CONF" >/dev/null 2>&1 || true
}

bootstrap_repos() {
  local ui_pass="$1"
  local base="http://127.0.0.1:${GITEA_HTTP_PORT}"
  local auth="${GITEA_ADMIN_USER}:${ui_pass}"
  local repo status
  for repo in iac-catalog pocket_lab_iac; do
    status="$(curl -s -o /dev/null -w '%{http_code}' -u "$auth" -H 'Content-Type: application/json' -d "{\"name\":\"$repo\",\"private\":true}" "$base/api/v1/user/repos" || true)"
    if [[ "$status" == "201" || "$status" == "409" ]]; then
      log INFO "Repository ready: $repo"
    else
      log WARN "Could not ensure repo $repo; HTTP $status"
    fi
  done
}

configure_act_runner() {
  mkdir -p "$ACT_RUNNER_HOME"
  cd "$ACT_RUNNER_HOME"
  if [[ ! -s "$ACT_RUNNER_CONFIG" ]]; then
    act_runner generate-config > "$ACT_RUNNER_CONFIG"
  else
    log INFO "act_runner config already exists"
  fi
  python3 - "$ACT_RUNNER_CONFIG" <<'PYCFG'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text()
old = '''  labels:
    - "ubuntu-latest:docker://gitea/runner-images:ubuntu-latest"
    - "ubuntu-22.04:docker://gitea/runner-images:ubuntu-22.04"
    - "ubuntu-20.04:docker://gitea/runner-images:ubuntu-20.04"'''
new = '''  labels:
    - "ubuntu-latest:host"
    - "linux-arm64:host"'''
if old in text:
    text = text.replace(old, new)
text = text.replace('network: ""', 'network: "host"')
p.write_text(text)
PYCFG
  chmod 600 "$ACT_RUNNER_CONFIG" "$ACT_RUNNER_HOME/.runner" 2>/dev/null || true

  if [[ -s "$ACT_RUNNER_HOME/.runner" ]]; then
    log INFO "act_runner already registered"
    return 0
  fi

  log INFO "Registering act_runner"
  local runner_token
  runner_token="$(gitea --config "$GITEA_RUNTIME_CONF" actions generate-runner-token)"
  act_runner register \
    --no-interactive \
    --instance "http://127.0.0.1:${GITEA_HTTP_PORT}" \
    --token "$runner_token" \
    --name "$GITEA_RUNNER_NAME" \
    --labels "$GITEA_RUNNER_LABELS" \
    --config "$ACT_RUNNER_CONFIG"
}

start_act_runner_pm2() {
  pm2_start_or_restart gitea-runner bash -- -lc "cd '$ACT_RUNNER_HOME'; until curl -fsS 'http://127.0.0.1:${GITEA_HTTP_PORT}/api/healthz' >/dev/null 2>&1; do echo 'waiting for gitea before starting act_runner'; sleep 5; done; exec act_runner daemon -c '$ACT_RUNNER_CONFIG'"
}

main() {
  SCRIPT_NAME="start-gitea.sh"
  acquire_lock "$SCRIPT_NAME"
  ensure_root_dirs
  require_termux
  require_cmd gitea curl jq pm2 python3 act_runner mariadb
  ensure_config
  local service_pass ui_pass
  service_pass="$(get_secret service_pass GITEA_SERVICE_PASS)"
  ui_pass="$(get_secret password GITEA_UI_PASS)"
  [[ -n "$service_pass" ]] || die "Unable to determine Gitea DB service password"
  [[ -n "$ui_pass" ]] || die "Unable to determine Gitea UI password"
  build_runtime_config "$service_pass"
  start_gitea_pm2
  wait_for_http "http://127.0.0.1:${GITEA_HTTP_PORT}/api/healthz" 120 || die "Gitea failed to start"
  bootstrap_admin_user "$ui_pass"
  bootstrap_repos "$ui_pass"
  configure_act_runner
  start_act_runner_pm2
  pm2 save >/dev/null || true
  mark_done gitea_ready
  log INFO "Gitea and act_runner are ready and safe to rerun"
}
main "$@"
