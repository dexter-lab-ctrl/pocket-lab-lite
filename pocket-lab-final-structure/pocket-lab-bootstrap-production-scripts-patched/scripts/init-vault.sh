#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_CONFIG="${VAULT_CONFIG:-$POCKET_LAB_VAULT_DIR/vault.hcl}"
VAULT_DATA_DIR="${VAULT_DATA_DIR:-$POCKET_LAB_VAULT_DIR/data}"
VAULT_STATE_DIR="${VAULT_STATE_DIR:-$STATE_DIR/vault}"
ROOT_ARTIFACTS="${ROOT_ARTIFACTS:-$VAULT_STATE_DIR/root.json}"
VAULT_TOKEN_FILE="${VAULT_TOKEN_FILE:-$VAULT_STATE_DIR/root.token}"
UNSEAL_KEY_FILE="${UNSEAL_KEY_FILE:-$VAULT_STATE_DIR/unseal.key}"
SERVICE_SECRETS_FILE="${SERVICE_SECRETS_FILE:-$STATE_DIR/service-secrets.env}"

write_vault_config() {
  ensure_dir_perm "$(dirname "$VAULT_CONFIG")" 700; ensure_dir_perm "$VAULT_DATA_DIR" 700
  cat <<EOF | atomic_write "$VAULT_CONFIG" 0600
disable_mlock = true
ui = true
api_addr = "${VAULT_ADDR}"
storage "file" { path = "${VAULT_DATA_DIR}" }
listener "tcp" {
  address = "127.0.0.1:8200"
  tls_disable = 1
  unauthenticated_metrics_access = true
}
telemetry { prometheus_retention_time = "24h" disable_hostname = true }
EOF
}
start_vault() {
  if curl -fsS "$VAULT_ADDR/v1/sys/health?standbyok=true&sealedcode=200&uninitcode=200" >/dev/null 2>&1; then log INFO "Vault API already reachable"; return 0; fi
  if pgrep -f "vault server .*${VAULT_CONFIG}" >/dev/null 2>&1; then log INFO "Vault process already running"; return 0; fi
  log INFO "Starting Vault server"
  nohup vault server -config="$VAULT_CONFIG" >"$LOG_DIR/vault.log" 2>&1 & echo $! > "$RUN_DIR/vault.pid"
}
ensure_initialized() {
  if curl -fsS "$VAULT_ADDR/v1/sys/init" | jq -e '.initialized == true' >/dev/null 2>&1; then log INFO "Vault already initialized"; return 0; fi
  [[ -s "$ROOT_ARTIFACTS" ]] && die "Vault reports uninitialized but root artifacts already exist; refusing to overwrite $ROOT_ARTIFACTS"
  log INFO "Initializing Vault"
  vault operator init -key-shares=1 -key-threshold=1 -format=json > "$ROOT_ARTIFACTS"
  chmod 600 "$ROOT_ARTIFACTS"
  jq -r '.unseal_keys_b64[0]' "$ROOT_ARTIFACTS" | atomic_write "$UNSEAL_KEY_FILE" 0600
  jq -r '.root_token' "$ROOT_ARTIFACTS" | atomic_write "$VAULT_TOKEN_FILE" 0600
}
ensure_unsealed() {
  local tmp rc sealed
  tmp="$(mktemp "${TMPDIR:-$PREFIX/tmp}/pocketlab-vault-status.XXXXXX")"
  rc=0
  VAULT_ADDR="$VAULT_ADDR" vault status -format=json >"$tmp" 2>/dev/null || rc=$?
  if [[ "$rc" != "0" && "$rc" != "2" ]]; then
    cat "$tmp" 2>/dev/null || true
    rm -f "$tmp"
    die "Unable to read Vault status, rc=$rc"
  fi
  sealed="$(jq -r '.sealed' "$tmp")"
  rm -f "$tmp"
  [[ "$sealed" == "false" ]] && { log INFO "Vault already unsealed"; return 0; }
  [[ -s "$UNSEAL_KEY_FILE" ]] || die "Missing unseal key: $UNSEAL_KEY_FILE"
  log INFO "Unsealing Vault"
  VAULT_ADDR="$VAULT_ADDR" vault operator unseal "$(cat "$UNSEAL_KEY_FILE")" >/dev/null
}
enable_engines() {
  log INFO "Ensuring Vault secret engines"
  vault secrets list -format=json | jq -e 'has("secret/")' >/dev/null 2>&1 || vault secrets enable -path=secret kv-v2 >/dev/null
  vault secrets list -format=json | jq -e 'has("database/")' >/dev/null 2>&1 || vault secrets enable database >/dev/null
}
bootstrap_service_secret() {
  if [[ -s "$SERVICE_SECRETS_FILE" ]]; then
    log INFO "Service secrets file already exists"
    chmod 600 "$SERVICE_SECRETS_FILE" || true
    return 0
  fi
  log INFO "Generating service secrets once"
  local gsp gup vap
  gsp="$(python3 - <<'PYSECRET'
import secrets
print(secrets.token_hex(16))
PYSECRET
)"
  gup="$(python3 - <<'PYSECRET'
import secrets, string
alphabet = string.ascii_letters + string.digits + '_@#%+=.-'
print(''.join(secrets.choice(alphabet) for _ in range(24)))
PYSECRET
)"
  vap="$(python3 - <<'PYSECRET'
import secrets
print(secrets.token_hex(16))
PYSECRET
)"
  write_secret_file "$SERVICE_SECRETS_FILE" "GITEA_SERVICE_PASS=$gsp" "GITEA_UI_PASS=$gup" "VAULT_ADMIN_PASS=$vap"
}
write_vault_service_secrets() {
  # shellcheck disable=SC1090
  source "$SERVICE_SECRETS_FILE"
  log INFO "Upserting bootstrap secrets into Vault"
  vault kv put secret/gitea username="pocket_admin" password="$GITEA_UI_PASS" service_pass="$GITEA_SERVICE_PASS" >/dev/null
  vault kv put secret/platform vault_admin_pass="$VAULT_ADMIN_PASS" >/dev/null
}
main() {
  SCRIPT_NAME="init-vault.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_termux; require_cmd vault jq curl pgrep python3
  ensure_dir_perm "$VAULT_STATE_DIR" 700; ensure_dir_perm "$VAULT_DATA_DIR" 700
  write_vault_config; start_vault
  wait_for_http "$VAULT_ADDR/v1/sys/health?standbyok=true&sealedcode=200&uninitcode=200" 60 || die "Vault failed to start"
  export VAULT_ADDR; ensure_initialized; ensure_unsealed; VAULT_TOKEN="$(cat "$VAULT_TOKEN_FILE")"; export VAULT_TOKEN; vault login "$VAULT_TOKEN" >/dev/null
  enable_engines; bootstrap_service_secret; write_vault_service_secrets
  mark_done vault_ready
  log INFO "Vault is initialized, unsealed, and safe to rerun"
}
main "$@"
