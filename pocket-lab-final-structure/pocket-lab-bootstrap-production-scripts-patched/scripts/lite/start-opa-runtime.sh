#!/usr/bin/env bash
# Start Lite OPA without allowing repository source updates to bypass durable
# P2.2 policy lifecycle authority. Pointer mutations happen only while the
# shared activation lock is held and never write policy governance SQLite.
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_SCRIPT_DIR="$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_SCRIPT_DIR/lib/common.sh"

OPA_POLICY_PREP="$SCRIPT_DIR/prepare-opa-policy.sh"
OPA_STARTUP_RESOLVER="$SCRIPT_DIR/resolve-opa-startup-policy.py"
POCKETLAB_STATE_DIR="${POCKETLAB_STATE_DIR:-${POCKETLAB_BASE_DIR:-$POCKET_LAB_BASE_DIR}/state}"
POCKETLAB_LITE_DB_PATH="${POCKETLAB_LITE_DB_PATH:-$POCKETLAB_STATE_DIR/pocketlab-lite.sqlite3}"
POCKETLAB_OPA_ACTIVE_POLICY_DIR="${POCKETLAB_OPA_ACTIVE_POLICY_DIR:-$POCKETLAB_STATE_DIR/opa/active}"
export POCKETLAB_STATE_DIR POCKETLAB_LITE_DB_PATH POCKETLAB_OPA_ACTIVE_POLICY_DIR

bounded_revision() {
  [[ "${1:-}" =~ ^[A-Za-z0-9._-]{8,80}$ ]]
}

stage_repository_candidate() {
  local required="${1:-0}" output revision
  if ! output="$(POCKETLAB_STATE_DIR="$POCKETLAB_STATE_DIR" \
      POCKETLAB_OPA_ACTIVE_POLICY_DIR="$POCKETLAB_OPA_ACTIVE_POLICY_DIR" \
      "$OPA_POLICY_PREP" stage)"; then
    if [[ "$required" == "1" ]]; then
      die "OPA repository baseline could not be staged"
    fi
    log WARN "OPA repository candidate could not be staged; keeping the durable governed revision"
    return 1
  fi
  revision="${output##*revision=}"
  if ! bounded_revision "$revision"; then
    if [[ "$required" == "1" ]]; then
      die "OPA policy staging did not return a bounded revision"
    fi
    log WARN "OPA repository candidate staging returned an invalid revision; keeping the durable governed revision"
    return 1
  fi
  POCKETLAB_OPA_REPOSITORY_STAGED_REVISION="$revision"
  export POCKETLAB_OPA_REPOSITORY_STAGED_REVISION
  return 0
}

start_opa_process() {
  pm2_start_or_restart pocket-opa "$(command -v opa)" \
    --interpreter bash -- run --server --addr=127.0.0.1:8181 \
    "$POCKETLAB_OPA_ACTIVE_POLICY_DIR"
}

wait_for_exact_revision() {
  local expected="$1" ready=0 attempt observed=""
  for attempt in $(seq 1 20); do
    if curl -fsS --max-time 2 http://127.0.0.1:8181/health >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  [[ "$ready" -eq 1 ]] || {
    pm2 logs pocket-opa --lines 80 --nostream || true
    die "OPA did not become ready on loopback"
  }
  observed="$(curl -fsS --max-time 3 \
    http://127.0.0.1:8181/v1/data/pocketlab/meta/revision \
    | python3 -c 'import json,sys; value=json.load(sys.stdin).get("result"); print(value if isinstance(value,str) else ""); raise SystemExit(0 if isinstance(value,str) else 1)' \
    2>/dev/null || true)"
  [[ "$observed" == "$expected" ]] || die "OPA metadata revision did not match the startup-authorized revision"
}

start_blocked_runtime_for_recovery() {
  local reason="${POCKETLAB_OPA_STARTUP_REASON_CODE:-policy_startup_blocked}"
  log WARN "OPA governed startup pointer mutation blocked reason=$reason; preserving current pointers for recovery"
  if ! start_opa_process; then
    log WARN "OPA could not be restarted from the preserved active pointer; continuing so FastAPI and the core supervisor can expose/reconcile fail-closed recovery state"
    return 0
  fi
  # Diagnostics only. Never bless this revision or change pointers while the
  # durable lifecycle is nonterminal/uncertain/inconsistent.
  if curl -fsS --max-time 2 http://127.0.0.1:8181/health >/dev/null 2>&1; then
    log INFO "OPA preserved runtime is reachable while governed startup remains blocked"
  else
    log WARN "OPA preserved runtime is not ready; continuing for supervisor/API recovery"
  fi
  return 0
}

run_under_activation_lock() {
  local mode="${POCKETLAB_OPA_STARTUP_MODE:-blocked}"
  local target="${POCKETLAB_OPA_STARTUP_REVISION:-}"
  case "$mode" in
    baseline_bootstrap)
      stage_repository_candidate 1
      target="$POCKETLAB_OPA_REPOSITORY_STAGED_REVISION"
      log INFO "OPA startup uses repository baseline because no durable governed policy state exists"
      ;;
    durable)
      bounded_revision "$target" || die "Durable OPA startup revision is invalid"
      # Staging the current source is inert. Failure here must not take down a
      # previously proved durable revision after an update/reboot.
      stage_repository_candidate 0 || true
      if [[ -n "${POCKETLAB_OPA_REPOSITORY_STAGED_REVISION:-}" && "$POCKETLAB_OPA_REPOSITORY_STAGED_REVISION" != "$target" ]]; then
        log INFO "OPA repository candidate is staged but the durable governed revision remains authoritative"
      fi
      ;;
    blocked)
      start_blocked_runtime_for_recovery
      return 0
      ;;
    *)
      die "OPA startup resolver returned an unsupported mode"
      ;;
  esac

  POCKETLAB_STATE_DIR="$POCKETLAB_STATE_DIR" "$OPA_POLICY_PREP" activate "$target"
  start_opa_process
  wait_for_exact_revision "$target"
  # known-good advances/restores only after exact health + metadata proof.
  POCKETLAB_STATE_DIR="$POCKETLAB_STATE_DIR" "$OPA_POLICY_PREP" known-good "$target"
  log INFO "OPA startup revision proved and known-good pointer synchronized"
}

main() {
  require_cmd python3 opa pm2 curl
  [[ -f "$OPA_STARTUP_RESOLVER" ]] || die "OPA startup authority resolver is missing: $OPA_STARTUP_RESOLVER"
  [[ -f "$OPA_POLICY_PREP" ]] || die "OPA policy preparation script is missing: $OPA_POLICY_PREP"

  if [[ "${1:-}" == "--under-activation-lock" ]]; then
    run_under_activation_lock
    return
  fi

  local rc=0
  python3 "$OPA_STARTUP_RESOLVER" --locked-exec -- \
    bash "$0" --under-activation-lock || rc=$?
  if [[ "$rc" -eq 75 ]]; then
    log WARN "OPA activation lock remained busy; leaving policy runtime untouched and continuing so the active supervisor can finish reconciliation"
    return 0
  fi
  [[ "$rc" -eq 0 ]] || return "$rc"
}

main "$@"
