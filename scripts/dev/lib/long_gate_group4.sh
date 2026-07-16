#!/usr/bin/env bash
# Shared Phase 5 Group 4 CLI validation and dry-run descriptions.

long_gate_group4_defaults() {
  LONG_GATE_WAL_SCENARIO="${POCKETLAB_LONG_GATE_WAL_SCENARIO:-isolated}"
  LONG_GATE_STORAGE_SCENARIO="${POCKETLAB_LONG_GATE_STORAGE_SCENARIO:-deterministic}"
  LONG_GATE_ANDROID_SCENARIO="${POCKETLAB_LONG_GATE_ANDROID_SCENARIO:-background-active}"
  LONG_GATE_WAL_DURATION_SECONDS="${POCKETLAB_LONG_GATE_WAL_DURATION_SECONDS:-300}"
  LONG_GATE_WAL_WRITER_INTERVAL_MS="${POCKETLAB_LONG_GATE_WAL_WRITER_INTERVAL_MS:-100}"
  LONG_GATE_WAL_READER_INTERVAL_MS="${POCKETLAB_LONG_GATE_WAL_READER_INTERVAL_MS:-100}"
  LONG_GATE_WAL_CHECKPOINT_INTERVAL_SECONDS="${POCKETLAB_LONG_GATE_WAL_CHECKPOINT_INTERVAL_SECONDS:-5}"
  LONG_GATE_WAL_HEALTH_INTERVAL_SECONDS="${POCKETLAB_LONG_GATE_WAL_HEALTH_INTERVAL_SECONDS:-30}"
  LONG_GATE_WAL_GROWTH_BUDGET_BYTES="${POCKETLAB_LONG_GATE_WAL_GROWTH_BUDGET_BYTES:-67108864}"
  LONG_GATE_WAL_READER_P95_SECONDS="${POCKETLAB_LONG_GATE_WAL_READER_P95_SECONDS:-1}"
  LONG_GATE_WAL_WRITER_P95_SECONDS="${POCKETLAB_LONG_GATE_WAL_WRITER_P95_SECONDS:-2}"
  LONG_GATE_WAL_CONTENTION_RETRY_BUDGET="${POCKETLAB_LONG_GATE_WAL_CONTENTION_RETRY_BUDGET:-10}"
  LONG_GATE_WAL_FINAL_TRUNCATE=0
  LONG_GATE_MIN_FREE_SPACE_BYTES="${POCKETLAB_MIN_FREE_SPACE_BYTES:-134217728}"
  LONG_GATE_MIN_FREE_SPACE_PERCENT="${POCKETLAB_MIN_FREE_SPACE_PERCENT:-3}"
  LONG_GATE_EMERGENCY_RESERVE_BYTES="${POCKETLAB_EMERGENCY_RESERVE_BYTES:-16777216}"
  LONG_GATE_MAX_ALLOCATION_BYTES="${POCKETLAB_LOW_STORAGE_TEST_MAX_BYTES:-0}"
  LONG_GATE_ABSOLUTE_ALLOCATION_CAP_BYTES="${POCKETLAB_LOW_STORAGE_ABSOLUTE_CAP_BYTES:-268435456}"
  LONG_GATE_ANDROID_OPERATOR_TIMEOUT_SECONDS="${POCKETLAB_LONG_GATE_ANDROID_OPERATOR_TIMEOUT_SECONDS:-600}"
  LONG_GATE_FRONTEND_REPORT_TIMEOUT_SECONDS="${POCKETLAB_LONG_GATE_FRONTEND_REPORT_TIMEOUT_SECONDS:-120}"
  LONG_GATE_ANDROID_RESUME_CYCLES="${POCKETLAB_LONG_GATE_ANDROID_RESUME_CYCLES:-3}"
  LONG_GATE_ANDROID_AUTO_CONFIRM=0
}

long_gate_export_group4_configuration() {
  export LONG_GATE_WAL_SCENARIO LONG_GATE_STORAGE_SCENARIO LONG_GATE_ANDROID_SCENARIO LONG_GATE_WAL_DURATION_SECONDS
  export LONG_GATE_WAL_WRITER_INTERVAL_MS LONG_GATE_WAL_READER_INTERVAL_MS LONG_GATE_WAL_CHECKPOINT_INTERVAL_SECONDS LONG_GATE_WAL_HEALTH_INTERVAL_SECONDS
  export LONG_GATE_WAL_GROWTH_BUDGET_BYTES LONG_GATE_WAL_READER_P95_SECONDS LONG_GATE_WAL_WRITER_P95_SECONDS LONG_GATE_WAL_CONTENTION_RETRY_BUDGET LONG_GATE_WAL_FINAL_TRUNCATE
  export LONG_GATE_MIN_FREE_SPACE_BYTES LONG_GATE_MIN_FREE_SPACE_PERCENT LONG_GATE_EMERGENCY_RESERVE_BYTES LONG_GATE_MAX_ALLOCATION_BYTES LONG_GATE_ABSOLUTE_ALLOCATION_CAP_BYTES
  export LONG_GATE_ANDROID_OPERATOR_TIMEOUT_SECONDS LONG_GATE_FRONTEND_REPORT_TIMEOUT_SECONDS LONG_GATE_ANDROID_RESUME_CYCLES LONG_GATE_ANDROID_AUTO_CONFIRM
}

long_gate_resolve_shared_options() {
  if [[ -n "$GENERIC_DURATION_SECONDS" ]]; then
    long_gate_is_positive_integer "$GENERIC_DURATION_SECONDS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--duration-seconds must be positive."
    if [[ "$SELECT_ALL" == '1' ]]; then
      LONG_GATE_IDLE_DURATION_SECONDS="$GENERIC_DURATION_SECONDS"; LONG_GATE_WAL_DURATION_SECONDS="$GENERIC_DURATION_SECONDS"
    elif [[ "${#SELECTED_GATES[@]}" -eq 1 && "${SELECTED_GATES[0]}" == 'idle' ]]; then
      LONG_GATE_IDLE_DURATION_SECONDS="$GENERIC_DURATION_SECONDS"
    elif [[ "${#SELECTED_GATES[@]}" -eq 1 && "${SELECTED_GATES[0]}" == 'wal-pressure' ]]; then
      LONG_GATE_WAL_DURATION_SECONDS="$GENERIC_DURATION_SECONDS"
    else
      long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--duration-seconds applies only to idle, wal-pressure, or --all."
    fi
  fi
  if [[ -n "$GENERIC_SCENARIO" ]]; then
    [[ "${#SELECTED_GATES[@]}" -eq 1 ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--scenario requires exactly one selected gate."
    case "${SELECTED_GATES[0]}" in
      nats-restart|worker-restart) LONG_GATE_RECOVERY_SCENARIO="$GENERIC_SCENARIO" ;;
      wal-pressure) LONG_GATE_WAL_SCENARIO="$GENERIC_SCENARIO" ;;
      low-storage) LONG_GATE_STORAGE_SCENARIO="$GENERIC_SCENARIO" ;;
      android-resume) LONG_GATE_ANDROID_SCENARIO="$GENERIC_SCENARIO" ;;
      *) long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--scenario is not supported for ${SELECTED_GATES[0]}." ;;
    esac
  fi
}

long_gate_validate_group4_configuration() {
  [[ "$LONG_GATE_WAL_SCENARIO" =~ ^(isolated|live|both)$ ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "WAL scenario must be isolated, live, or both."
  [[ "$LONG_GATE_STORAGE_SCENARIO" =~ ^(deterministic|live|both)$ ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Low-storage scenario must be deterministic, live, or both."
  [[ "$LONG_GATE_ANDROID_SCENARIO" =~ ^(background-active|process-eviction|network-transition|repeated-resume|all)$ ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Android scenario is invalid."
  long_gate_is_positive_integer "$LONG_GATE_WAL_DURATION_SECONDS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--duration-seconds must be positive."
  long_gate_is_positive_integer "$LONG_GATE_WAL_WRITER_INTERVAL_MS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--writer-interval-ms must be positive."
  long_gate_is_positive_integer "$LONG_GATE_WAL_READER_INTERVAL_MS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--reader-interval-ms must be positive."
  (( LONG_GATE_WAL_WRITER_INTERVAL_MS >= 10 && LONG_GATE_WAL_READER_INTERVAL_MS >= 10 )) || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "WAL reader/writer intervals must be at least 10 ms."
  long_gate_is_positive_number "$LONG_GATE_WAL_CHECKPOINT_INTERVAL_SECONDS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--checkpoint-interval-seconds must be positive."
  long_gate_is_positive_number "$LONG_GATE_WAL_HEALTH_INTERVAL_SECONDS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--health-interval-seconds must be positive."
  long_gate_is_nonnegative_integer "$LONG_GATE_WAL_GROWTH_BUDGET_BYTES" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--wal-growth-budget-bytes must be non-negative."
  long_gate_is_nonnegative_integer "$LONG_GATE_WAL_CONTENTION_RETRY_BUDGET" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--contention-retry-budget must be non-negative."
  long_gate_is_positive_number "$LONG_GATE_WAL_READER_P95_SECONDS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--reader-p95-budget-seconds must be positive."
  long_gate_is_positive_number "$LONG_GATE_WAL_WRITER_P95_SECONDS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--writer-p95-budget-seconds must be positive."
  long_gate_is_positive_integer "$LONG_GATE_MIN_FREE_SPACE_BYTES" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--min-free-space-bytes must be positive."
  long_gate_is_positive_number "$LONG_GATE_MIN_FREE_SPACE_PERCENT" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--min-free-space-percent must be positive."
  long_gate_is_positive_integer "$LONG_GATE_EMERGENCY_RESERVE_BYTES" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--emergency-reserve-bytes must be positive."
  long_gate_is_nonnegative_integer "$LONG_GATE_MAX_ALLOCATION_BYTES" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--max-allocation-bytes must be non-negative."
  long_gate_is_positive_integer "$LONG_GATE_ABSOLUTE_ALLOCATION_CAP_BYTES" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--absolute-allocation-cap-bytes must be positive."
  long_gate_is_positive_integer "$LONG_GATE_ANDROID_OPERATOR_TIMEOUT_SECONDS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--operator-timeout-seconds must be positive."
  long_gate_is_positive_integer "$LONG_GATE_FRONTEND_REPORT_TIMEOUT_SECONDS" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--frontend-report-timeout-seconds must be positive."
  long_gate_is_positive_integer "$LONG_GATE_ANDROID_RESUME_CYCLES" || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--resume-cycles must be positive."
  (( LONG_GATE_ANDROID_RESUME_CYCLES <= 20 )) || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--resume-cycles cannot exceed 20."
}

long_gate_group4_dry_run() {
  case "$1" in
    wal-pressure)
      printf 'planned_actions=isolated repository pressure and/or bounded live observation; scenario=%s; passive checkpoints only\n' "$LONG_GATE_WAL_SCENARIO"
      ;;
    low-storage)
      printf 'planned_actions=isolated ENOSPC failpoints and/or capped run-owned allocation; scenario=%s; allocation_cap_bytes=%s\n' "$LONG_GATE_STORAGE_SCENARIO" "$LONG_GATE_MAX_ALLOCATION_BYTES"
      ;;
    android-resume)
      printf 'planned_actions=operator-assisted frontend/backend lifecycle reconciliation; scenario=%s; no backend service stop\n' "$LONG_GATE_ANDROID_SCENARIO"
      ;;
  esac
}
