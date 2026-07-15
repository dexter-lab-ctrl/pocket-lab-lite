#!/usr/bin/env bash
# Android/Termux-compatible run lock implementation using atomic mkdir.

long_gate_lock_acquire() {
  local recover_stale="${1:-0}"
  LONG_GATE_LOCK_DIR="$LONG_GATE_RUN_DIR/.lock"
  export LONG_GATE_LOCK_DIR
  if mkdir "$LONG_GATE_LOCK_DIR" 2>/dev/null; then
    long_gate_python lock-metadata \
      --output "$LONG_GATE_LOCK_DIR/owner.json" \
      --run-id "$LONG_GATE_RUN_ID" \
      --pid "$BASHPID"
    LONG_GATE_LOCK_HELD=1
    export LONG_GATE_LOCK_HELD
    return 0
  fi

  if [[ "$recover_stale" != "1" ]]; then
    long_gate_die "$LONG_GATE_EXIT_LOCK_CONFLICT" "Run directory is already locked. Use --resume --recover-stale-lock only after validating the prior owner is gone."
    return $?
  fi

  [[ -f "$LONG_GATE_LOCK_DIR/owner.json" ]] || {
    long_gate_die "$LONG_GATE_EXIT_LOCK_CONFLICT" "Lock directory exists without valid owner metadata; manual review is required."
    return $?
  }

  set +e
  local inspection
  inspection="$(long_gate_python inspect-lock \
    --path "$LONG_GATE_LOCK_DIR/owner.json" \
    --run-id "$LONG_GATE_RUN_ID" \
    --minimum-age "${POCKETLAB_LONG_GATE_STALE_LOCK_MIN_AGE_SECONDS:-60}" 2>/dev/null)"
  local rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    long_gate_die "$LONG_GATE_EXIT_LOCK_CONFLICT" "Existing lock is active, too recent, or inconsistent; stale-lock recovery was refused."
    return $?
  fi

  local archived="$LONG_GATE_RUN_DIR/checkpoints/stale-lock-$(date -u +%Y%m%d-%H%M%S).lock"
  mv "$LONG_GATE_LOCK_DIR" "$archived"
  mkdir "$LONG_GATE_LOCK_DIR"
  long_gate_python lock-metadata \
    --output "$LONG_GATE_LOCK_DIR/owner.json" \
    --run-id "$LONG_GATE_RUN_ID" \
    --pid "$BASHPID"
  LONG_GATE_LOCK_HELD=1
  export LONG_GATE_LOCK_HELD
  long_gate_warn "Recovered stale lock and preserved prior metadata at ${archived#$LONG_GATE_RUN_DIR/}."
}

long_gate_lock_release() {
  if [[ "${LONG_GATE_LOCK_HELD:-0}" == "1" && -d "${LONG_GATE_LOCK_DIR:-}" ]]; then
    rm -rf -- "$LONG_GATE_LOCK_DIR"
    LONG_GATE_LOCK_HELD=0
    export LONG_GATE_LOCK_HELD
  fi
}
