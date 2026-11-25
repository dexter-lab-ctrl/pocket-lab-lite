#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
DASHBOARD_URL="${DASHBOARD_URL:-http://127.0.0.1:8443}"
API_URL="${API_URL:-http://127.0.0.1:8080}"

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

  check "Dashboard HTTP" curl_quiet "$DASHBOARD_URL"
  check "Lite API liveness" curl_quiet "$API_URL/health"
  check "Lite API readiness" curl_quiet "$API_URL/ready"
  check "FastAPI/NATS event bus status" curl_quiet "$API_URL/api/events/status"
  check "Worker status endpoint" curl_quiet "$API_URL/api/workers/status"
  check "JetStream reliability status" curl_quiet "$API_URL/api/reliability/status"
  check "Event-sourced workflow engine status" curl_quiet "$API_URL/api/workflows/status"
  check "Dead-letter queue endpoint" curl_quiet "$API_URL/api/reliability/dead-letters"
  check "Live status sampler" curl_quiet "$API_URL/api/live-status/status"
  check "NATS-backed fleet agents API" curl_quiet "$API_URL/api/fleet/agents"
  check "Event-native telemetry" curl_quiet "$API_URL/api/telemetry.json"
  check "Event-native health engine" curl_quiet "$API_URL/api/health-engine.json"
  check "Lite status API" curl_quiet "$API_URL/api/lite/status"

  if have tailscale-cli; then
    check "Tailscale status" bash -lc "tailscale-cli status >/dev/null"
  fi

  (( failures == 0 )) || die "$failures smoke test(s) failed"
  mark_done smoke_tests_passed
  log INFO "All smoke tests passed"
}
main "$@"
