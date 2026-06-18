#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
MYSQL_DATADIR="${MYSQL_DATADIR:-$PREFIX/var/lib/mysql}"
MYSQL_RUN_DIR="${MYSQL_RUN_DIR:-$PREFIX/var/run/mysqld}"
MYSQL_SOCKET="${MYSQL_SOCKET:-$MYSQL_RUN_DIR/mysqld.sock}"
MYSQL_PIDFILE="${MYSQL_PIDFILE:-$RUN_DIR/mariadb.pid}"
MYSQLD_BIN="${MYSQLD_BIN:-$(command -v mariadbd || command -v mysqld || true)}"
SERVICE_SECRETS_FILE="${SERVICE_SECRETS_FILE:-$STATE_DIR/service-secrets.env}"

sql_escape() { printf "%s" "$1" | sed "s/'/''/g"; }
ensure_mysql_dirs() { ensure_dir_perm "$MYSQL_DATADIR" 700; ensure_dir_perm "$MYSQL_RUN_DIR" 755; }
start_mariadb() {
  if [[ -S "$MYSQL_SOCKET" ]] && mariadb --protocol=socket -uroot -S "$MYSQL_SOCKET" -e 'SELECT 1;' >/dev/null 2>&1; then log INFO "MariaDB already running"; return 0; fi
  log INFO "Starting MariaDB"
  nohup "$MYSQLD_BIN" --datadir="$MYSQL_DATADIR" --socket="$MYSQL_SOCKET" --pid-file="$MYSQL_PIDFILE" --skip-networking=0 --bind-address=127.0.0.1 --port=3306 >"$LOG_DIR/mariadb.log" 2>&1 & echo $! > "$MYSQL_PIDFILE"
}
db_exec() { mariadb --protocol=socket -uroot -S "$MYSQL_SOCKET" "$@"; }
ensure_datadir_initialized() {
  [[ -d "$MYSQL_DATADIR/mysql" ]] && { log INFO "MariaDB datadir already initialized"; return 0; }
  log INFO "Initializing MariaDB datadir"
  if have mariadb-install-db; then mariadb-install-db --datadir="$MYSQL_DATADIR" --auth-root-authentication-method=normal || mariadb-install-db --datadir="$MYSQL_DATADIR"; elif have mysql_install_db; then mysql_install_db --datadir="$MYSQL_DATADIR"; else die "No MariaDB initialization tool available"; fi
}
ensure_service_secrets() { [[ -f "$SERVICE_SECRETS_FILE" ]] || die "Missing $SERVICE_SECRETS_FILE; run init-vault.sh first"; # shellcheck disable=SC1090
  source "$SERVICE_SECRETS_FILE"; [[ -n "${GITEA_SERVICE_PASS:-}" && -n "${VAULT_ADMIN_PASS:-}" ]] || die "Required service secrets missing"; }
configure_schema_and_users() {
  local gp vp; gp="$(sql_escape "$GITEA_SERVICE_PASS")"; vp="$(sql_escape "$VAULT_ADMIN_PASS")"
  log INFO "Ensuring MariaDB schemas/users"
  db_exec -e "CREATE DATABASE IF NOT EXISTS gitea CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  db_exec -e "CREATE USER IF NOT EXISTS 'gitea'@'127.0.0.1' IDENTIFIED BY '${gp}'; ALTER USER 'gitea'@'127.0.0.1' IDENTIFIED BY '${gp}'; GRANT ALL PRIVILEGES ON gitea.* TO 'gitea'@'127.0.0.1';"
  db_exec -e "CREATE USER IF NOT EXISTS 'vault_admin'@'127.0.0.1' IDENTIFIED BY '${vp}'; ALTER USER 'vault_admin'@'127.0.0.1' IDENTIFIED BY '${vp}'; GRANT ALL PRIVILEGES ON *.* TO 'vault_admin'@'127.0.0.1' WITH GRANT OPTION; FLUSH PRIVILEGES;"
}
resolve_vault_token_file() {
  local candidate
  for candidate in \
    "${VAULT_TOKEN_FILE:-}" \
    "$STATE_DIR/vault/root.token" \
    "$POCKET_LAB_BASE_DIR/state/vault/root.token" \
    "$POCKET_LAB_VAULT_DIR/root.token"; do
    [[ -n "$candidate" && -s "$candidate" ]] && { printf '%s
' "$candidate"; return 0; }
  done
  find "$HOME" -path '*/vault/root.token' -type f -print 2>/dev/null | head -n 1
}

register_vault_database_engine() {
  command -v vault >/dev/null 2>&1 || return 0
  export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

  local token_file="${VAULT_TOKEN_FILE:-}"
  if [[ -z "${VAULT_TOKEN:-}" ]]; then
    token_file="$(resolve_vault_token_file || true)"
    if [[ -n "$token_file" && -s "$token_file" ]]; then
      export VAULT_TOKEN="$(cat "$token_file")"
    fi
  fi

  if [[ -z "${VAULT_TOKEN:-}" ]]; then
    log WARN "Vault token unavailable; skipping DB engine registration"
    return 0
  fi

  if ! vault status >/dev/null 2>&1; then
    log WARN "Vault unavailable; skipping DB engine registration"
    return 0
  fi

  vault login "$VAULT_TOKEN" >/dev/null 2>&1 || true
  log INFO "Ensuring Vault MariaDB database engine config"
  vault secrets list -format=json | jq -e 'has("database/")' >/dev/null 2>&1 || vault secrets enable database >/dev/null
  vault write database/config/mariadb plugin_name="mysql-database-plugin" allowed_roles="mariadb-role" connection_url="{{username}}:{{password}}@tcp(127.0.0.1:3306)/" username="vault_admin" password="$VAULT_ADMIN_PASS" >/dev/null
  vault write database/roles/mariadb-role db_name="mariadb" creation_statements="CREATE USER '{{name}}'@'127.0.0.1' IDENTIFIED BY '{{password}}'; GRANT ALL PRIVILEGES ON *.* TO '{{name}}'@'127.0.0.1';" revocation_statements="DROP USER '{{name}}'@'127.0.0.1';" default_ttl="1h" max_ttl="24h" >/dev/null
}
main() {
  SCRIPT_NAME="init-mariadb.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_termux; require_cmd mariadb curl jq
  [[ -n "$MYSQLD_BIN" ]] || die "Unable to locate mariadbd/mysqld"
  ensure_mysql_dirs; ensure_datadir_initialized; start_mariadb
  wait_for_tcp 127.0.0.1 3306 60 || [[ -S "$MYSQL_SOCKET" ]] || die "MariaDB failed to start"
  ensure_service_secrets; configure_schema_and_users; register_vault_database_engine
  mark_done mariadb_ready
  log INFO "MariaDB is ready and safe to rerun"
}
main "$@"
