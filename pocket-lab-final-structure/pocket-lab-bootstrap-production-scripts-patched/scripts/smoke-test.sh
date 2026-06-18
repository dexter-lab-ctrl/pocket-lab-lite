#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"; export VAULT_ADDR
GITEA_URL="${GITEA_URL:-http://127.0.0.1:3030}"
DASHBOARD_URL="${DASHBOARD_URL:-http://127.0.0.1:8443}"
API_URL="${API_URL:-http://127.0.0.1:8080}"
GATUS_URL="${GATUS_URL:-http://127.0.0.1:8081}"

curl_quiet() {
  curl -fsS -o /dev/null "$1"
}

main(){
  export SCRIPT_NAME="smoke-test.sh"
  ensure_root_dirs
  require_cmd curl
  local failures=0

  check(){
    local name="$1"; shift
    if "$@"; then
      log INFO "PASS: $name"
    else
      log ERROR "FAIL: $name"
      failures=$((failures+1))
    fi
  }

  check "Vault health" curl_quiet "${VAULT_ADDR}/v1/sys/health?standbyok=true"
  if have vault && have jq; then
    check "Vault status JSON" bash -lc "vault status -format=json | jq -e '.initialized == true and .sealed == false' >/dev/null"
  else
    log WARN "Skipping Vault JSON check; vault/jq missing"
  fi

  check "Gitea HTTP" curl_quiet "$GITEA_URL"
  check "Dashboard HTTP" curl_quiet "$DASHBOARD_URL"
  check "FastAPI/NATS event bus status" curl_quiet "$API_URL/api/events/status"
  check "Worker status endpoint" curl_quiet "$API_URL/api/workers/status"
  check "JetStream reliability status" curl_quiet "$API_URL/api/reliability/status"
  check "Event-sourced workflow engine status" curl_quiet "$API_URL/api/workflows/status"
  check "Dead-letter queue endpoint" curl_quiet "$API_URL/api/reliability/dead-letters"
  check "Live status sampler" curl_quiet "$API_URL/api/live-status/status"
  check "NATS-backed fleet agents API" curl_quiet "$API_URL/api/fleet/agents"
  check "Event-native telemetry" curl_quiet "$API_URL/api/telemetry.json"
  check "Event-native health engine" curl_quiet "$API_URL/api/health-engine.json"
  if is_lite_profile; then
    check "Lite status API" curl_quiet "$API_URL/api/lite/status"
  else
    check "Gatus status API" curl_quiet "$GATUS_URL/api/v1/endpoints/statuses"
  fi

  if have mariadb; then
    check "MariaDB socket" bash -lc "mariadb --protocol=socket -uroot -S '${PREFIX}/var/run/mysqld/mysqld.sock' -e 'SELECT 1;' >/dev/null"
  else
    log WARN "Skipping MariaDB check; client missing"
  fi

  if [[ -f "$STATE_DIR/service-secrets.env" ]]; then
    check "Gitea API auth" bash -lc "source '$STATE_DIR/service-secrets.env'; curl -fsS -o /dev/null -u \"pocket_admin:\${GITEA_UI_PASS}\" '$GITEA_URL/api/v1/version'"
  fi

  if have tailscale-cli; then
    check "Tailscale status" bash -lc "tailscale-cli status >/dev/null"
  fi

  (( failures == 0 )) || die "$failures smoke test(s) failed"
  mark_done smoke_tests_passed
  log INFO "All smoke tests passed"
}
main "$@"
