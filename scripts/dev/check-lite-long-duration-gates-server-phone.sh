#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
LONG_GATE_REPO_ROOT="$REPO_ROOT"
LONG_GATE_JSON_TOOL="$REPO_ROOT/scripts/dev/lib/long_gate_json.py"
LONG_GATE_GROUP2_TOOL="$REPO_ROOT/scripts/dev/lib/long_gate_group2.py"
LONG_GATE_GROUP3_TOOL="$REPO_ROOT/scripts/dev/lib/long_gate_group3.py"
LONG_GATE_GROUP4_TOOL="$REPO_ROOT/scripts/dev/lib/long_gate_group4.py"
LONG_GATE_PYTHON="${POCKETLAB_LONG_GATE_PYTHON:-python3}"
export LONG_GATE_REPO_ROOT LONG_GATE_JSON_TOOL LONG_GATE_GROUP2_TOOL LONG_GATE_GROUP3_TOOL LONG_GATE_GROUP4_TOOL LONG_GATE_PYTHON

source "$REPO_ROOT/scripts/dev/lib/long_gate_common.sh"
source "$REPO_ROOT/scripts/dev/lib/long_gate_checkpoint.sh"
source "$REPO_ROOT/scripts/dev/lib/long_gate_report.sh"
source "$REPO_ROOT/scripts/dev/lib/long_gate_http.sh"
source "$REPO_ROOT/scripts/dev/lib/long_gate_sqlite.sh"
source "$REPO_ROOT/scripts/dev/lib/long_gate_runtime.sh"
source "$REPO_ROOT/scripts/dev/lib/long_gate_process.sh"
source "$REPO_ROOT/scripts/dev/lib/long_gate_group4.sh"

readonly REGISTRY_DELIMITER='|'
GATE_REGISTRY=(
  "idle|scripts/dev/long-gates/idle-stability.sh|low|1|1|Idle 24-hour stability|duration=86400;sample=60;heavy=3600|http,sqlite,pm2|0|0"
  "repeated-scans|scripts/dev/long-gates/repeated-quick-scans.sh|medium|1|1|Repeated Quick Safety Check endurance|count=10;cooldown=5|http,sqlite,nats,worker|0|0"
  "progress-soak|scripts/dev/long-gates/active-progress-soak.sh|medium|1|1|Active Security Progress soak|scan_count=1;sample_ms=500|direct_http,proxy_http,etag,sqlite|0|0"
  "submission-recovery|scripts/dev/long-gates/submission-timeout-recovery.sh|high|1|1|Submission timeout recovery|client_timeout=2;response_delay_ms=5000|http,sqlite,nats,worker,gate_fault|1|1"
  "nats-restart|scripts/dev/long-gates/nats-restart.sh|high|1|1|Controlled NATS restart recovery|scenario=both|pm2,nats,worker,sqlite|1|1"
  "worker-restart|scripts/dev/long-gates/worker-restart.sh|high|1|1|Controlled worker restart recovery|scenario=both|pm2,nats,worker,sqlite|1|1"
  "wal-pressure|scripts/dev/long-gates/wal-checkpoint-pressure.sh|high|1|1|SQLite WAL checkpoint pressure|scenario=isolated;duration=300|sqlite,progress|0|0"
  "low-storage|scripts/dev/long-gates/low-storage.sh|high|1|1|Deterministic and bounded low-storage behavior|scenario=deterministic|storage,sqlite,gate_fault|0|0"
  "android-resume|scripts/dev/long-gates/android-background-resume.sh|medium|1|1|Android background and resume behavior|scenario=background-active|android,frontend,operator|0|1"
  "security-s8|scripts/dev/long-gates/security-s8-recovery.sh|high|1|1|Security S8 retention, WAL, backup, restore, rollback, and cross-platform qualification|platform=auto|http,sqlite,nats,worker,recovery|1|1"
  "framework-self-test|scripts/dev/long-gates/framework-self-test.sh|low|1|1|Non-disruptive Group 1 framework validation|||0|0"
)
usage() {
  cat <<'EOF'
Pocket Lab Lite Phase 5 long-duration gate framework

Usage: bash scripts/dev/check-lite-long-duration-gates-server-phone.sh [options]
Selection: --gate <name> | --all | --framework-self-test | --baseline-only | --list-gates
Control: --resume --run-id <id> --report-dir <path> --dry-run --recover-stale-lock
Risk opt-ins: --allow-disruptive --allow-storage-pressure
S8 qualification also requires environment opt-ins:
  POCKETLAB_S8_GATE_ALLOW_RETENTION_APPLY=1
  POCKETLAB_S8_GATE_ALLOW_RESTORE=1
  POCKETLAB_S8_GATE_ALLOW_FAILED_RESTORE=1
  POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS=1 (API/worker startup environment for Gate 6)

Groups 2/3 retain their existing duration, scan, Progress, and recovery options.
  --scenario <name>                     Scenario for one selected gate.
  --wal-scenario isolated|live|both     WAL stage selection.
  --storage-scenario deterministic|live|both
  --android-scenario background-active|process-eviction|network-transition|repeated-resume|all
  --writer-interval-ms <n> --reader-interval-ms <n>
  --checkpoint-interval-seconds <n> --health-interval-seconds <n>
  --wal-growth-budget-bytes <n> --reader-p95-budget-seconds <n> --writer-p95-budget-seconds <n>
  --contention-retry-budget <n> --final-truncate-checkpoint
  --min-free-space-bytes <n> --min-free-space-percent <n>
  --emergency-reserve-bytes <n> --max-allocation-bytes <n> --absolute-allocation-cap-bytes <n>
  --operator-timeout-seconds <n> --frontend-report-timeout-seconds <n> --resume-cycles <n>

EOF
}

registry_field() {
  local requested="$1" field="$2" row name script risk implemented resume_support description defaults capabilities disruptive confirmation
  for row in "${GATE_REGISTRY[@]}"; do
    IFS="$REGISTRY_DELIMITER" read -r name script risk implemented resume_support description defaults capabilities disruptive confirmation <<< "$row"
    if [[ "$name" == "$requested" ]]; then
      case "$field" in
        script) printf '%s\n' "$script" ;;
        risk) printf '%s\n' "$risk" ;;
        implemented) printf '%s\n' "$implemented" ;;
        resume) printf '%s\n' "$resume_support" ;;
        description) printf '%s\n' "$description" ;;
        defaults) printf '%s\n' "$defaults" ;;
        capabilities) printf '%s\n' "$capabilities" ;;
        disruptive) printf '%s\n' "$disruptive" ;;
        confirmation) printf '%s\n' "$confirmation" ;;
        *) return 2 ;;
      esac
      return 0
    fi
  done
  return 1
}

registry_contains() {
  registry_field "$1" implemented >/dev/null 2>&1
}

list_gates() {
  local row name script risk implemented resume_support description defaults capabilities disruptive confirmation status
  printf '%-24s %-14s %-8s %-8s %-11s %s\n' 'GATE' 'STATUS' 'RISK' 'RESUME' 'DISRUPTIVE' 'DESCRIPTION'
  for row in "${GATE_REGISTRY[@]}"; do
    IFS="$REGISTRY_DELIMITER" read -r name script risk implemented resume_support description defaults capabilities disruptive confirmation <<< "$row"
    status='unavailable'
    [[ "$implemented" == "1" && -f "$REPO_ROOT/$script" ]] && status='implemented'
    printf '%-24s %-14s %-8s %-8s %-11s %s\n' "$name" "$status" "$risk" "$resume_support" "$([[ "$disruptive" == '1' ]] && printf yes || printf no)" "$description"
  done
}

implemented_real_gate_names() {
  local row name script risk implemented resume_support description defaults capabilities disruptive confirmation
  for row in "${GATE_REGISTRY[@]}"; do
    IFS="$REGISTRY_DELIMITER" read -r name script risk implemented resume_support description defaults capabilities disruptive confirmation <<< "$row"
    if [[ "$name" != "framework-self-test" && "$implemented" == "1" && -f "$REPO_ROOT/$script" && "$name" != "android-resume" && ( "$disruptive" != "1" || "$ALLOW_DISRUPTIVE" == "1" ) ]]; then
      printf '%s\n' "$name"
    fi
  done
}

join_by_comma() {
  local output='' item
  for item in "$@"; do
    [[ -n "$output" ]] && output+=','
    output+="$item"
  done
  printf '%s\n' "$output"
}

result_status() {
  local gate_id="$1"
  local path="$LONG_GATE_RUN_DIR/gates/$gate_id/result.json"
  [[ -f "$path" ]] || { printf 'missing\n'; return 0; }
  "$LONG_GATE_PYTHON" - "$path" <<'PY'
import json, sys
try:
    payload = json.load(open(sys.argv[1], encoding='utf-8'))
except (OSError, json.JSONDecodeError):
    print('corrupt')
else:
    print(payload.get('status') or 'missing')
PY
}

REPORT_ROOT="$(long_gate_default_report_root)"
RUN_ID=''
RESUME=0
RECOVER_STALE_LOCK=0
DRY_RUN=0
LIST_ONLY=0
SELECT_ALL=0
BASELINE_ONLY=0
FRAMEWORK_SELF_TEST=0
ALLOW_DISRUPTIVE=0
ALLOW_STORAGE_PRESSURE=0
GENERIC_SCENARIO=''
GENERIC_DURATION_SECONDS=''
SELECTED_GATES=()

LONG_GATE_RESUME=0
LONG_GATE_PROXY_BASE_URL="${POCKETLAB_LONG_GATE_PROXY_BASE_URL:-${POCKETLAB_LONG_GATE_BASE_URL:-http://127.0.0.1:8443}}"
LONG_GATE_DIRECT_BASE_URL="${POCKETLAB_LONG_GATE_DIRECT_BASE_URL:-http://127.0.0.1:8080}"
LONG_GATE_CONNECT_TIMEOUT="${POCKETLAB_LONG_GATE_CONNECT_TIMEOUT:-2}"
LONG_GATE_HTTP_TIMEOUT="${POCKETLAB_LONG_GATE_HTTP_TIMEOUT:-5}"
LONG_GATE_REPORT_LIMIT_MB="${POCKETLAB_LONG_GATE_REPORT_LIMIT_MB:-128}"
LONG_GATE_REPORT_LIMIT_BYTES=0
LONG_GATE_IDLE_DURATION_SECONDS="${POCKETLAB_LONG_GATE_IDLE_DURATION_SECONDS:-86400}"
LONG_GATE_IDLE_SAMPLE_INTERVAL_SECONDS="${POCKETLAB_LONG_GATE_IDLE_SAMPLE_INTERVAL_SECONDS:-60}"
LONG_GATE_IDLE_HEAVY_INTERVAL_SECONDS="${POCKETLAB_LONG_GATE_IDLE_HEAVY_INTERVAL_SECONDS:-3600}"
LONG_GATE_IDLE_WARMUP_SECONDS="${POCKETLAB_LONG_GATE_IDLE_WARMUP_SECONDS:-900}"
LONG_GATE_IDLE_RSS_BUDGET_MB="${POCKETLAB_LONG_GATE_IDLE_RSS_BUDGET_MB:-128}"
LONG_GATE_IDLE_WAL_BUDGET_MB="${POCKETLAB_LONG_GATE_IDLE_WAL_BUDGET_MB:-64}"
LONG_GATE_IDLE_LOG_BUDGET_MB="${POCKETLAB_LONG_GATE_IDLE_LOG_BUDGET_MB:-128}"
LONG_GATE_IDLE_FD_BUDGET="${POCKETLAB_LONG_GATE_IDLE_FD_BUDGET:-32}"
LONG_GATE_IDLE_CPU_THRESHOLD="${POCKETLAB_LONG_GATE_IDLE_CPU_THRESHOLD:-20}"
LONG_GATE_REPEATED_COUNT="${POCKETLAB_LONG_GATE_REPEATED_COUNT:-10}"
LONG_GATE_REPEATED_COOLDOWN_SECONDS="${POCKETLAB_LONG_GATE_REPEATED_COOLDOWN_SECONDS:-5}"
LONG_GATE_RUN_TIMEOUT_SECONDS="${POCKETLAB_LONG_GATE_RUN_TIMEOUT_SECONDS:-5400}"
LONG_GATE_SUBMISSION_TIMEOUT_SECONDS="${POCKETLAB_LONG_GATE_SUBMISSION_TIMEOUT_SECONDS:-10}"
LONG_GATE_REPEATED_PARITY_EVERY="${POCKETLAB_LONG_GATE_REPEATED_PARITY_EVERY:-1}"
LONG_GATE_REPEATED_RESOURCE_EVERY="${POCKETLAB_LONG_GATE_REPEATED_RESOURCE_EVERY:-1}"
LONG_GATE_STOP_ON_FIRST_FAILURE="${POCKETLAB_LONG_GATE_STOP_ON_FIRST_FAILURE:-1}"
LONG_GATE_PROGRESS_SCAN_COUNT="${POCKETLAB_LONG_GATE_PROGRESS_SCAN_COUNT:-1}"
LONG_GATE_PROGRESS_SAMPLE_INTERVAL_MS="${POCKETLAB_LONG_GATE_PROGRESS_SAMPLE_INTERVAL_MS:-500}"
LONG_GATE_PROGRESS_ETAG_EVERY="${POCKETLAB_LONG_GATE_PROGRESS_ETAG_EVERY:-10}"
LONG_GATE_PROGRESS_MAX_AGE_MS="${POCKETLAB_LONG_GATE_PROGRESS_MAX_AGE_MS:-5000}"
LONG_GATE_PROGRESS_P95_BUDGET_SECONDS="${POCKETLAB_LONG_GATE_PROGRESS_P95_BUDGET_SECONDS:-1}"
LONG_GATE_PROGRESS_MAX_BUDGET_SECONDS="${POCKETLAB_LONG_GATE_PROGRESS_MAX_BUDGET_SECONDS:-3}"
LONG_GATE_RECOVERY_SCENARIO="${POCKETLAB_LONG_GATE_RECOVERY_SCENARIO:-both}"
LONG_GATE_CLIENT_TIMEOUT_SECONDS="${POCKETLAB_LONG_GATE_CLIENT_TIMEOUT_SECONDS:-2}"
LONG_GATE_RESPONSE_DELAY_MS="${POCKETLAB_LONG_GATE_RESPONSE_DELAY_MS:-5000}"
LONG_GATE_DISCOVERY_TIMEOUT_SECONDS="${POCKETLAB_LONG_GATE_DISCOVERY_TIMEOUT_SECONDS:-30}"
LONG_GATE_SERVICE_RECOVERY_TIMEOUT_SECONDS="${POCKETLAB_LONG_GATE_SERVICE_RECOVERY_TIMEOUT_SECONDS:-120}"
LONG_GATE_EXECUTION_EVIDENCE_TIMEOUT_SECONDS="${POCKETLAB_LONG_GATE_EXECUTION_EVIDENCE_TIMEOUT_SECONDS:-300}"
long_gate_group4_defaults

long_gate_require_option_value() {
  local option="$1" count="$2"
  (( count >= 2 )) || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "$option requires a value."
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --gate)
      [[ "$#" -ge 2 ]] || { usage >&2; exit "$LONG_GATE_EXIT_INVALID_CLI"; }
      SELECTED_GATES+=("$2")
      shift 2
      ;;
    --all) SELECT_ALL=1; shift ;;
    --resume) RESUME=1; shift ;;
    --report-dir)
      [[ "$#" -ge 2 ]] || { usage >&2; exit "$LONG_GATE_EXIT_INVALID_CLI"; }
      REPORT_ROOT="$2"
      shift 2
      ;;
    --run-id)
      [[ "$#" -ge 2 ]] || { usage >&2; exit "$LONG_GATE_EXIT_INVALID_CLI"; }
      RUN_ID="$2"
      shift 2
      ;;
    --list-gates) LIST_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --framework-self-test) FRAMEWORK_SELF_TEST=1; shift ;;
    --baseline-only) BASELINE_ONLY=1; shift ;;
    --recover-stale-lock) RECOVER_STALE_LOCK=1; shift ;;
    --allow-disruptive) ALLOW_DISRUPTIVE=1; shift ;;
    --allow-storage-pressure) ALLOW_STORAGE_PRESSURE=1; shift ;;
    --duration-seconds) long_gate_require_option_value "$1" "$#"; GENERIC_DURATION_SECONDS="$2"; shift 2 ;;
    --sample-interval-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_IDLE_SAMPLE_INTERVAL_SECONDS="$2"; shift 2 ;;
    --heavy-check-interval-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_IDLE_HEAVY_INTERVAL_SECONDS="$2"; shift 2 ;;
    --warmup-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_IDLE_WARMUP_SECONDS="$2"; shift 2 ;;
    --rss-budget-mb) long_gate_require_option_value "$1" "$#"; LONG_GATE_IDLE_RSS_BUDGET_MB="$2"; shift 2 ;;
    --wal-budget-mb) long_gate_require_option_value "$1" "$#"; LONG_GATE_IDLE_WAL_BUDGET_MB="$2"; shift 2 ;;
    --log-growth-budget-mb) long_gate_require_option_value "$1" "$#"; LONG_GATE_IDLE_LOG_BUDGET_MB="$2"; shift 2 ;;
    --fd-growth-budget) long_gate_require_option_value "$1" "$#"; LONG_GATE_IDLE_FD_BUDGET="$2"; shift 2 ;;
    --cpu-idle-threshold) long_gate_require_option_value "$1" "$#"; LONG_GATE_IDLE_CPU_THRESHOLD="$2"; shift 2 ;;
    --count) long_gate_require_option_value "$1" "$#"; LONG_GATE_REPEATED_COUNT="$2"; shift 2 ;;
    --cooldown-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_REPEATED_COOLDOWN_SECONDS="$2"; shift 2 ;;
    --run-timeout-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_RUN_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --submission-timeout-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_SUBMISSION_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --parity-every) long_gate_require_option_value "$1" "$#"; LONG_GATE_REPEATED_PARITY_EVERY="$2"; shift 2 ;;
    --resource-sample-every) long_gate_require_option_value "$1" "$#"; LONG_GATE_REPEATED_RESOURCE_EVERY="$2"; shift 2 ;;
    --stop-on-first-failure) LONG_GATE_STOP_ON_FIRST_FAILURE=1; shift ;;
    --scan-count) long_gate_require_option_value "$1" "$#"; LONG_GATE_PROGRESS_SCAN_COUNT="$2"; shift 2 ;;
    --sample-interval-ms) long_gate_require_option_value "$1" "$#"; LONG_GATE_PROGRESS_SAMPLE_INTERVAL_MS="$2"; shift 2 ;;
    --direct-base-url) long_gate_require_option_value "$1" "$#"; LONG_GATE_DIRECT_BASE_URL="$2"; shift 2 ;;
    --proxy-base-url) long_gate_require_option_value "$1" "$#"; LONG_GATE_PROXY_BASE_URL="$2"; shift 2 ;;
    --etag-check-every) long_gate_require_option_value "$1" "$#"; LONG_GATE_PROGRESS_ETAG_EVERY="$2"; shift 2 ;;
    --max-projection-age-ms) long_gate_require_option_value "$1" "$#"; LONG_GATE_PROGRESS_MAX_AGE_MS="$2"; shift 2 ;;
    --p95-budget-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_PROGRESS_P95_BUDGET_SECONDS="$2"; shift 2 ;;
    --max-budget-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_PROGRESS_MAX_BUDGET_SECONDS="$2"; shift 2 ;;
    --report-limit-mb) long_gate_require_option_value "$1" "$#"; LONG_GATE_REPORT_LIMIT_MB="$2"; shift 2 ;;
    --scenario) long_gate_require_option_value "$1" "$#"; GENERIC_SCENARIO="$2"; shift 2 ;;
    --wal-scenario) long_gate_require_option_value "$1" "$#"; LONG_GATE_WAL_SCENARIO="$2"; shift 2 ;;
    --storage-scenario) long_gate_require_option_value "$1" "$#"; LONG_GATE_STORAGE_SCENARIO="$2"; shift 2 ;;
    --android-scenario) long_gate_require_option_value "$1" "$#"; LONG_GATE_ANDROID_SCENARIO="$2"; shift 2 ;;
    --writer-interval-ms) long_gate_require_option_value "$1" "$#"; LONG_GATE_WAL_WRITER_INTERVAL_MS="$2"; shift 2 ;;
    --reader-interval-ms) long_gate_require_option_value "$1" "$#"; LONG_GATE_WAL_READER_INTERVAL_MS="$2"; shift 2 ;;
    --checkpoint-interval-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_WAL_CHECKPOINT_INTERVAL_SECONDS="$2"; shift 2 ;;
    --health-interval-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_WAL_HEALTH_INTERVAL_SECONDS="$2"; shift 2 ;;
    --wal-growth-budget-bytes) long_gate_require_option_value "$1" "$#"; LONG_GATE_WAL_GROWTH_BUDGET_BYTES="$2"; shift 2 ;;
    --reader-p95-budget-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_WAL_READER_P95_SECONDS="$2"; shift 2 ;;
    --writer-p95-budget-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_WAL_WRITER_P95_SECONDS="$2"; shift 2 ;;
    --contention-retry-budget) long_gate_require_option_value "$1" "$#"; LONG_GATE_WAL_CONTENTION_RETRY_BUDGET="$2"; shift 2 ;;
    --final-truncate-checkpoint) LONG_GATE_WAL_FINAL_TRUNCATE=1; shift ;;
    --min-free-space-bytes) long_gate_require_option_value "$1" "$#"; LONG_GATE_MIN_FREE_SPACE_BYTES="$2"; shift 2 ;;
    --min-free-space-percent) long_gate_require_option_value "$1" "$#"; LONG_GATE_MIN_FREE_SPACE_PERCENT="$2"; shift 2 ;;
    --emergency-reserve-bytes) long_gate_require_option_value "$1" "$#"; LONG_GATE_EMERGENCY_RESERVE_BYTES="$2"; shift 2 ;;
    --max-allocation-bytes) long_gate_require_option_value "$1" "$#"; LONG_GATE_MAX_ALLOCATION_BYTES="$2"; shift 2 ;;
    --absolute-allocation-cap-bytes) long_gate_require_option_value "$1" "$#"; LONG_GATE_ABSOLUTE_ALLOCATION_CAP_BYTES="$2"; shift 2 ;;
    --operator-timeout-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_ANDROID_OPERATOR_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --frontend-report-timeout-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_FRONTEND_REPORT_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --resume-cycles) long_gate_require_option_value "$1" "$#"; LONG_GATE_ANDROID_RESUME_CYCLES="$2"; shift 2 ;;
    --auto-confirm-operator) LONG_GATE_ANDROID_AUTO_CONFIRM=1; shift ;;
    --client-timeout-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_CLIENT_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --response-delay-ms) long_gate_require_option_value "$1" "$#"; LONG_GATE_RESPONSE_DELAY_MS="$2"; shift 2 ;;
    --discovery-timeout-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_DISCOVERY_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --service-recovery-timeout-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_SERVICE_RECOVERY_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --execution-evidence-timeout-seconds) long_gate_require_option_value "$1" "$#"; LONG_GATE_EXECUTION_EVIDENCE_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'ERROR: Unknown argument: %s\n' "$1" >&2; usage >&2; exit "$LONG_GATE_EXIT_INVALID_CLI" ;;
  esac
done

long_gate_require_command "$LONG_GATE_PYTHON"
[[ -f "$LONG_GATE_JSON_TOOL" ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Structured evidence helper is missing or not executable."
[[ -f "$LONG_GATE_GROUP2_TOOL" ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Group 2 gate helper is missing."
[[ -f "$LONG_GATE_GROUP3_TOOL" ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Group 3 gate helper is missing."
[[ -f "$LONG_GATE_GROUP4_TOOL" ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Group 4 gate helper is missing."
LONG_GATE_REPORT_LIMIT_BYTES=$(( LONG_GATE_REPORT_LIMIT_MB * 1024 * 1024 ))
LONG_GATE_RESUME="$RESUME"
export LONG_GATE_RESUME LONG_GATE_PROXY_BASE_URL LONG_GATE_DIRECT_BASE_URL LONG_GATE_CONNECT_TIMEOUT LONG_GATE_HTTP_TIMEOUT
export LONG_GATE_REPORT_LIMIT_MB LONG_GATE_REPORT_LIMIT_BYTES LONG_GATE_IDLE_DURATION_SECONDS LONG_GATE_IDLE_SAMPLE_INTERVAL_SECONDS
export LONG_GATE_IDLE_HEAVY_INTERVAL_SECONDS LONG_GATE_IDLE_WARMUP_SECONDS LONG_GATE_IDLE_RSS_BUDGET_MB
export LONG_GATE_IDLE_WAL_BUDGET_MB LONG_GATE_IDLE_LOG_BUDGET_MB LONG_GATE_IDLE_FD_BUDGET LONG_GATE_IDLE_CPU_THRESHOLD
export LONG_GATE_REPEATED_COUNT LONG_GATE_REPEATED_COOLDOWN_SECONDS LONG_GATE_RUN_TIMEOUT_SECONDS LONG_GATE_SUBMISSION_TIMEOUT_SECONDS
export LONG_GATE_REPEATED_PARITY_EVERY LONG_GATE_REPEATED_RESOURCE_EVERY LONG_GATE_STOP_ON_FIRST_FAILURE
export LONG_GATE_PROGRESS_SCAN_COUNT LONG_GATE_PROGRESS_SAMPLE_INTERVAL_MS LONG_GATE_PROGRESS_ETAG_EVERY
export LONG_GATE_PROGRESS_MAX_AGE_MS LONG_GATE_PROGRESS_P95_BUDGET_SECONDS LONG_GATE_PROGRESS_MAX_BUDGET_SECONDS
export LONG_GATE_RECOVERY_SCENARIO LONG_GATE_CLIENT_TIMEOUT_SECONDS LONG_GATE_RESPONSE_DELAY_MS LONG_GATE_DISCOVERY_TIMEOUT_SECONDS
export LONG_GATE_SERVICE_RECOVERY_TIMEOUT_SECONDS LONG_GATE_EXECUTION_EVIDENCE_TIMEOUT_SECONDS
long_gate_export_group4_configuration

if [[ "$LIST_ONLY" == "1" ]]; then
  list_gates
  exit 0
fi

selection_modes=$((SELECT_ALL + BASELINE_ONLY + FRAMEWORK_SELF_TEST))
if (( selection_modes > 1 )); then
  long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--all, --baseline-only, and --framework-self-test are mutually exclusive."
  exit $?
fi
if [[ "$SELECT_ALL" == "1" && "${#SELECTED_GATES[@]}" -gt 0 ]]; then
  long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "--all cannot be combined with --gate."
  exit $?
fi
if [[ "$FRAMEWORK_SELF_TEST" == "1" ]]; then
  SELECTED_GATES=(framework-self-test)
elif [[ "$SELECT_ALL" == "1" ]]; then
  mapfile -t SELECTED_GATES < <(implemented_real_gate_names)
fi
long_gate_resolve_shared_options
long_gate_validate_group2_configuration
long_gate_validate_group3_configuration
long_gate_validate_group4_configuration

if [[ "$BASELINE_ONLY" != "1" && "${#SELECTED_GATES[@]}" -eq 0 ]]; then
  if [[ "$DRY_RUN" == "1" ]]; then
    list_gates
    exit 0
  fi
  long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Select --gate, --all, --framework-self-test, or --baseline-only."
  exit $?
fi

for gate_id in "${SELECTED_GATES[@]}"; do
  if ! registry_contains "$gate_id"; then
    long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Unknown gate: $gate_id"
    exit $?
  fi
  if [[ "$(registry_field "$gate_id" disruptive)" == "1" && "$ALLOW_DISRUPTIVE" != "1" ]]; then
    long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Gate '$gate_id' is disruptive and requires --allow-disruptive."
    exit $?
  fi
  case "$gate_id" in
    nats-restart)
      [[ "$LONG_GATE_RECOVERY_SCENARIO" =~ ^(idle|active|both)$ ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "NATS --scenario must be idle, active, or both."
      ;;
    worker-restart)
      [[ "$LONG_GATE_RECOVERY_SCENARIO" =~ ^(before-claim|after-claim|both)$ ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Worker --scenario must be before-claim, after-claim, or both."
      ;;
    low-storage)
      if [[ "$LONG_GATE_STORAGE_SCENARIO" =~ ^(live|both)$ ]]; then
        [[ "$ALLOW_DISRUPTIVE" == '1' && "$ALLOW_STORAGE_PRESSURE" == '1' ]] || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Live low-storage requires --allow-disruptive and --allow-storage-pressure."
        (( LONG_GATE_MAX_ALLOCATION_BYTES > 0 )) || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Live low-storage requires an explicit positive --max-allocation-bytes."
      fi
      ;;
  esac
done
if [[ "$SELECT_ALL" == "1" && "$ALLOW_DISRUPTIVE" == "1" && "$LONG_GATE_RECOVERY_SCENARIO" != "both" ]]; then
  long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Disruptive --all requires --scenario both."
  exit $?
fi

REPORT_ROOT="$(mkdir -p "$REPORT_ROOT" && CDPATH='' cd -- "$REPORT_ROOT" && pwd)"
if [[ "$RESUME" == "1" && -z "$RUN_ID" ]]; then
  set +e
  RUN_ID="$(long_gate_find_resumable_run "$REPORT_ROOT")"
  rc=$?
  set -e
  if [[ "$rc" -ne 0 || -z "$RUN_ID" ]]; then
    long_gate_die "$LONG_GATE_EXIT_CHECKPOINT_CORRUPTION" "No resumable run was found; provide --run-id after reviewing the report directory."
    exit $?
  fi
fi
[[ -n "$RUN_ID" ]] || RUN_ID="$(long_gate_generate_run_id)"
if ! long_gate_safe_run_id "$RUN_ID"; then
  long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Run ID must use the pocketlab-long-gates-* safe form."
  exit $?
fi

LONG_GATE_RUN_ID="$RUN_ID"
LONG_GATE_RUN_DIR="$REPORT_ROOT/$RUN_ID"
export LONG_GATE_RUN_ID LONG_GATE_RUN_DIR
MODE='gates'
[[ "$FRAMEWORK_SELF_TEST" == "1" ]] && MODE='framework_self_test'
[[ "$BASELINE_ONLY" == "1" ]] && MODE='baseline_only'
GATES_CSV="$(join_by_comma "${SELECTED_GATES[@]}")"

if [[ "$DRY_RUN" == "1" ]]; then
  printf 'run_id=%s\n' "$LONG_GATE_RUN_ID"
  printf 'report_root=%s\n' "$REPORT_ROOT"
  printf 'mode=%s\n' "$MODE"
  printf 'selected_gates=%s\n' "${GATES_CSV:-none}"
  for gate_id in "${SELECTED_GATES[@]}"; do
    printf 'gate=%s status=%s risk=%s resume=%s disruptive=%s\n' \
      "$gate_id" \
      "$([[ "$(registry_field "$gate_id" implemented)" == '1' ]] && printf implemented || printf unavailable)" \
      "$(registry_field "$gate_id" risk)" \
      "$(registry_field "$gate_id" resume)" \
      "$([[ "$(registry_field "$gate_id" disruptive)" == '1' ]] && printf yes || printf no)"
    printf 'gate_defaults=%s capabilities=%s\n' "$(registry_field "$gate_id" defaults)" "$(registry_field "$gate_id" capabilities)"
    case "$gate_id" in
      submission-recovery) printf 'planned_actions=create short-lived gate activation; submit one Quick scan; no service restart\n' ;;
      nats-restart) printf 'planned_actions=restart pocket-nats only; scenario=%s\n' "$LONG_GATE_RECOVERY_SCENARIO" ;;
      worker-restart) printf 'planned_actions=stop/start or restart pocket-worker only; scenario=%s\n' "$LONG_GATE_RECOVERY_SCENARIO" ;;
      wal-pressure|low-storage|android-resume) long_gate_group4_dry_run "$gate_id" ;;
    esac
  done
  exit 0
fi

long_gate_prepare_run_layout "$LONG_GATE_RUN_DIR"
set +e
long_gate_lock_acquire "$([[ "$RESUME" == '1' && "$RECOVER_STALE_LOCK" == '1' ]] && printf 1 || printf 0)"
lock_rc=$?
set -e
[[ "$lock_rc" -eq 0 ]] || exit "$lock_rc"

cleanup_lock() {
  long_gate_lock_release
}
trap cleanup_lock EXIT

handle_interrupt() {
  local signal_name="$1"
  trap - INT TERM
  set +e
  long_gate_update_state interrupted "" "" "Interrupted by $signal_name; resume from the last safe checkpoint."
  long_gate_mark_interrupted_checkpoints
  set -e
  long_gate_lock_release
  exit "$LONG_GATE_EXIT_INTERRUPTED"
}
trap 'handle_interrupt SIGINT' INT
trap 'handle_interrupt SIGTERM' TERM

set +e
long_gate_init_run "$GATES_CSV" "$MODE" "$RESUME"
init_rc=$?
set -e
if [[ "$init_rc" -ne 0 ]]; then
  long_gate_die "$LONG_GATE_EXIT_CHECKPOINT_CORRUPTION" "Run manifest/state initialization or resume validation failed."
  exit $?
fi
if [[ "$RESUME" == "1" ]]; then
  set +e
  long_gate_mark_interrupted_checkpoints
  interrupted_rc=$?
  set -e
  if [[ "$interrupted_rc" -ne 0 ]]; then
    long_gate_die "$LONG_GATE_EXIT_CHECKPOINT_CORRUPTION" "Checkpoint validation failed while marking interrupted stages."
    exit $?
  fi
fi

baseline_failed=0
if [[ ! -f "$LONG_GATE_RUN_DIR/baseline/before.json" ]]; then
  long_gate_info "Capturing sanitized before baseline"
  set +e
  long_gate_capture_baseline before
  before_rc=$?
  set -e
  [[ "$before_rc" -eq 0 ]] || baseline_failed=1
else
  long_gate_info "Preserving existing before baseline for resumed run"
fi

unavailable_selected=0
gate_failed=0
for gate_id in "${SELECTED_GATES[@]}"; do
  prior_result="$(result_status "$gate_id")"
  if [[ "$RESUME" == "1" && "$prior_result" == "passed" ]]; then
    long_gate_info "Preserving completed gate result on resume: $gate_id"
    continue
  fi
  implemented="$(registry_field "$gate_id" implemented)"
  script_rel="$(registry_field "$gate_id" script)"
  if [[ "$implemented" != "1" || ! -f "$REPO_ROOT/$script_rel" ]]; then
    reason="Phase 5 gate '$gate_id' is registered but not implemented in the current group."
    long_gate_stage_unavailable "$gate_id" availability "$reason"
    long_gate_write_gate_result "$gate_id" unavailable 1 0 "$(long_gate_iso_timestamp)" 0 "$reason" availability 1 1 ""
    unavailable_selected=1
    continue
  fi

  LONG_GATE_GATE_ID="$gate_id"
  export LONG_GATE_GATE_ID
  started_at="$(long_gate_iso_timestamp)"
  started_epoch="$(long_gate_epoch_seconds)"
  long_gate_info "Running gate: $gate_id"
  set +e
  # Gate scripts inherit only the shared helper functions and sanitized run metadata.
  ( source "$REPO_ROOT/$script_rel" )
  gate_rc=$?
  set -e
  duration=$(( $(long_gate_epoch_seconds) - started_epoch ))
  detailed_status="$(result_status "$gate_id")"
  if [[ "$gate_rc" -eq 0 ]]; then
    if [[ "$detailed_status" != "passed" ]]; then
      phase5_gate=1
      framework_validation=0
      [[ "$gate_id" == "framework-self-test" ]] && { phase5_gate=0; framework_validation=1; }
      long_gate_write_gate_result \
        "$gate_id" passed "$phase5_gate" "$framework_validation" "$started_at" "$duration" \
        "" "" 1 1 "gates/$gate_id"
    fi
  else
    if [[ "$detailed_status" != "failed" ]]; then
      reason="Gate '$gate_id' exited with code $gate_rc. Review its sanitized checkpoint and result evidence."
      long_gate_write_gate_result \
        "$gate_id" failed "$([[ "$gate_id" == 'framework-self-test' ]] && printf 0 || printf 1)" \
        "$([[ "$gate_id" == 'framework-self-test' ]] && printf 1 || printf 0)" \
        "$started_at" "$duration" "$reason" execution 1 1 "gates/$gate_id"
    fi
    gate_failed=1
  fi
done

long_gate_info "Capturing sanitized after baseline"
set +e
long_gate_capture_baseline after
after_rc=$?
set -e
[[ "$after_rc" -eq 0 ]] || baseline_failed=1

set +e
long_gate_evaluate_invariants
invariant_rc=$?
long_gate_scan_sanitization
sanitize_rc=$?
long_gate_aggregate_summary
aggregate_rc=$?
# Scan once more so the generated summary is also covered, then aggregate again.
long_gate_scan_sanitization
sanitize_final_rc=$?
long_gate_aggregate_summary
aggregate_final_rc=$?
long_gate_generate_checksums
checksum_rc=$?
set -e

printf 'Run ID: %s\n' "$LONG_GATE_RUN_ID"
printf 'Evidence: %s\n' "$LONG_GATE_RUN_DIR"
printf 'Summary: %s\n' "$LONG_GATE_RUN_DIR/summary.json"

if [[ "$sanitize_rc" -ne 0 || "$sanitize_final_rc" -ne 0 ]]; then
  exit "$LONG_GATE_EXIT_SANITIZATION_FAILURE"
fi
if [[ "$baseline_failed" -ne 0 ]]; then
  exit "$LONG_GATE_EXIT_BASELINE_FAILURE"
fi
if [[ "$unavailable_selected" -ne 0 ]]; then
  exit "$LONG_GATE_EXIT_GATE_UNAVAILABLE"
fi
if [[ "$gate_failed" -ne 0 ]]; then
  exit "$LONG_GATE_EXIT_FINAL_INVARIANT_FAILURE"
fi
if [[ "$invariant_rc" -ne 0 || "$aggregate_rc" -ne 0 || "$aggregate_final_rc" -ne 0 || "$checksum_rc" -ne 0 ]]; then
  exit "$LONG_GATE_EXIT_FINAL_INVARIANT_FAILURE"
fi
exit 0
