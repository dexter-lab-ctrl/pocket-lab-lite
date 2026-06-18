#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Pocket Lab Day-0 bootstrap dispatcher.
#
# This script intentionally acts only as the orchestrator. The actual work stays
# in the idempotent stage scripts beside this file. The dispatcher is strict:
# every required stage script must exist, each stage must exit successfully
# before the next stage runs, and a stage is marked complete only after success.

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

BOOTSTRAP_VERSION="2026-06-02-fastapi-nats-enterprise"
BOOTSTRAP_DRY_RUN="${POCKETLAB_BOOTSTRAP_DRY_RUN:-0}"
FORCE_STAGE="0"
FORCE_ALL="0"
TARGET_STAGE=""
FROM_STAGE=""
LIST_ONLY="0"
CURRENT_STAGE_ID=""
CURRENT_STAGE_NAME=""

# Stage fields are pipe-delimited:
#   index|id|script|description
# Keep this order aligned with the Day-0 dependency graph.
BOOTSTRAP_STAGES=(
  "1|install_termux_packages|install-termux-packages.sh|Install Termux packages, base CLI tools, Node, PM2, MariaDB, Gitea, Caddy, and build dependencies"
  "2|install_proot_ubuntu|install-proot-ubuntu.sh|Install and prepare the proot Ubuntu compatibility layer"
  "3|install_binaries|install-binaries.sh|Install Vault, act_runner, Python runtime packages, NATS tooling, and observability binaries"
  "4|init_vault|init-vault.sh|Start and initialize Vault, unseal it, enable engines, and seed initial platform secrets"
  "5|init_mariadb|init-mariadb.sh|Initialize MariaDB, create Pocket Lab service users, and register Vault database integration"
  "6|start_gitea|start-gitea.sh|Start Gitea and act_runner, create the admin user, and prepare GitOps repositories"
  "7|seed_gitops_repo|seed-gitops-repo.sh|Seed or refresh the GitOps/IaC repository in local Gitea"
  "8|install_tailscale|install-tailscale.sh|Install or prepare Tailscale connectivity for fleet access"
  "9|install_pwa_ui|install-pwa-ui.sh|Install the production React/Vite PWA assets"
  "10|start_dashboard|start-dashboard.sh|Start enterprise NATS/JetStream, FastAPI, worker, node agent, Caddy, and observability services"
  "11|install_fleet_agent|install-fleet-agent.sh|Install the local NATS-backed fleet agent wrapper using generated NATS credentials"
  "12|smoke_test|smoke-test.sh|Run Day-0 smoke tests against Vault, Gitea, FastAPI, NATS, workflows, telemetry, and MariaDB"
)

usage() {
  cat <<EOF_USAGE
Usage: $(basename "$0") [options]

Runs the Pocket Lab Day-0 bootstrap sequence in dependency order.

Options:
  --stage N|ID       Run one stage after validating that all earlier stages are complete.
  --from-stage N|ID  Resume from a stage and continue through the end.
  --force-stage      Clear the selected stage marker before running it.
  --force-all        Clear all bootstrap stage markers before running.
  --dry-run          Validate and print the execution plan without running stage scripts.
  --list             Print the Day-0 stage plan and exit.
  -h, --help         Show this help text.

Environment:
  POCKETLAB_BOOTSTRAP_DRY_RUN=1      Same as --dry-run.
  POCKET_LAB_ALLOW_NON_TERMUX=1      Allows non-Termux syntax/test harness execution.
  POCKET_LAB_NO_NETWORK=1            Blocks downloads inside stage scripts.

Examples:
  ./bootstrap.sh
  ./bootstrap.sh --dry-run
  ./bootstrap.sh --from-stage start_dashboard
  ./bootstrap.sh --stage init_vault --force-stage
EOF_USAGE
}

stage_count() { printf '%s\n' "${#BOOTSTRAP_STAGES[@]}"; }

parse_stage_record() {
  local record="$1"
  IFS='|' read -r _stage_index _stage_id _stage_script _stage_description <<< "$record"
}

stage_marker_key() {
  local index="$1" id="$2"
  printf 'bootstrap_stage_%02d_%s' "$index" "$id"
}

legacy_stage_marker_key() {
  local index="$1"
  printf 'bootstrap_stage_%d' "$index"
}

stage_is_done() {
  local index="$1" id="$2" key legacy_key
  key="$(stage_marker_key "$index" "$id")"
  legacy_key="$(legacy_stage_marker_key "$index")"
  is_done "$key" || is_done "$legacy_key"
}

stage_mark_done() {
  local index="$1" id="$2" key
  key="$(stage_marker_key "$index" "$id")"
  mark_done "$key"
}

stage_mark_clear() {
  local index="$1" id="$2"
  mark_clear "$(stage_marker_key "$index" "$id")"
  mark_clear "$(legacy_stage_marker_key "$index")"
}

find_stage_index() {
  local selector="$1" record index id script description
  [[ -n "$selector" ]] || return 1
  for record in "${BOOTSTRAP_STAGES[@]}"; do
    IFS='|' read -r index id script description <<< "$record"
    if [[ "$selector" == "$index" || "$selector" == "$id" || "$selector" == "$script" ]]; then
      printf '%s\n' "$index"
      return 0
    fi
  done
  return 1
}

stage_record_by_index() {
  local wanted="$1" record index id script description
  for record in "${BOOTSTRAP_STAGES[@]}"; do
    IFS='|' read -r index id script description <<< "$record"
    if [[ "$index" == "$wanted" ]]; then
      printf '%s\n' "$record"
      return 0
    fi
  done
  return 1
}

print_plan() {
  local record index id script description marker state
  log INFO "Pocket Lab Day-0 bootstrap plan, version $BOOTSTRAP_VERSION"
  for record in "${BOOTSTRAP_STAGES[@]}"; do
    IFS='|' read -r index id script description <<< "$record"
    marker="$(stage_marker_key "$index" "$id")"
    if stage_is_done "$index" "$id"; then state="done"; else state="pending"; fi
    printf '%2s. %-24s %-28s [%s]\n    %s\n    marker: %s\n' "$index" "$id" "$script" "$state" "$description" "$marker"
  done
}

validate_stage_graph() {
  local expected=1 record index id script description script_path seen_ids=" "
  for record in "${BOOTSTRAP_STAGES[@]}"; do
    IFS='|' read -r index id script description <<< "$record"
    [[ "$index" =~ ^[0-9]+$ ]] || die "Invalid non-numeric stage index: $index"
    [[ "$index" -eq "$expected" ]] || die "Invalid bootstrap stage graph: expected index $expected but found $index ($id)"
    [[ " $seen_ids " != *" $id "* ]] || die "Duplicate bootstrap stage id: $id"
    seen_ids+="$id "
    script_path="$SCRIPT_DIR/$script"
    [[ -f "$script_path" ]] || die "Required Day-0 stage script is missing: $script_path"
    [[ -r "$script_path" ]] || die "Required Day-0 stage script is not readable: $script_path"
    bash -n "$script_path" || die "Syntax check failed for stage script: $script_path"
    expected=$((expected + 1))
  done
}

load_generated_nats_credentials_if_available() {
  local cred_file="$STATE_DIR/nats/pocketlab-nats.env"
  if [[ -f "$cred_file" ]]; then
    # shellcheck disable=SC1090
    source "$cred_file"
    export POCKETLAB_NATS_API_USER POCKETLAB_NATS_API_PASSWORD \
      POCKETLAB_NATS_WORKER_USER POCKETLAB_NATS_WORKER_PASSWORD \
      POCKETLAB_NATS_AGENT_USER POCKETLAB_NATS_AGENT_PASSWORD
  fi
}

prepare_stage_environment() {
  local id="$1"
  case "$id" in
    install_fleet_agent)
      load_generated_nats_credentials_if_available
      ;;
    smoke_test)
      load_generated_nats_credentials_if_available
      ;;
  esac
}

require_prior_stages_done() {
  local target_index="$1" record index id script description
  for record in "${BOOTSTRAP_STAGES[@]}"; do
    IFS='|' read -r index id script description <<< "$record"
    [[ "$index" -ge "$target_index" ]] && break
    if ! stage_is_done "$index" "$id"; then
      die "Cannot run stage $target_index directly because dependency stage $index ($id) is not marked complete. Use --from-stage $index or run ./bootstrap.sh."
    fi
  done
}

run_stage_by_index() {
  local requested_index="$1" record index id script description marker script_path start_ts
  record="$(stage_record_by_index "$requested_index")" || die "Unknown bootstrap stage index: $requested_index"
  IFS='|' read -r index id script description <<< "$record"
  CURRENT_STAGE_ID="$id"
  CURRENT_STAGE_NAME="$script"
  marker="$(stage_marker_key "$index" "$id")"
  script_path="$SCRIPT_DIR/$script"

  if stage_is_done "$index" "$id" && [[ "$FORCE_STAGE" != "1" && "$FORCE_ALL" != "1" ]]; then
    log INFO "Stage $index/$id already completed; skipping. Marker: $marker"
    return 0
  fi

  if [[ "$FORCE_STAGE" == "1" || "$FORCE_ALL" == "1" ]]; then
    stage_mark_clear "$index" "$id"
  fi

  log INFO "Starting stage $index/$id: $description"
  log INFO "Executing: $script_path"

  if [[ "$BOOTSTRAP_DRY_RUN" == "1" ]]; then
    log INFO "Dry-run: would execute stage $index/$id and mark $marker on success"
    return 0
  fi

  start_ts="$(timestamp)"
  prepare_stage_environment "$id"
  bash "$script_path"
  stage_mark_done "$index" "$id"
  log INFO "Completed stage $index/$id. Started: $start_ts Finished: $(timestamp) Marker: $marker"
}

clear_all_stage_markers() {
  local record index id script description
  for record in "${BOOTSTRAP_STAGES[@]}"; do
    IFS='|' read -r index id script description <<< "$record"
    stage_mark_clear "$index" "$id"
  done
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --stage)
        [[ $# -ge 2 ]] || die "--stage requires a stage number or id"
        TARGET_STAGE="$2"
        shift 2
        ;;
      --stage=*)
        TARGET_STAGE="${1#--stage=}"
        shift
        ;;
      --from-stage)
        [[ $# -ge 2 ]] || die "--from-stage requires a stage number or id"
        FROM_STAGE="$2"
        shift 2
        ;;
      --from-stage=*)
        FROM_STAGE="${1#--from-stage=}"
        shift
        ;;
      --force-stage)
        FORCE_STAGE="1"
        shift
        ;;
      --force-all)
        FORCE_ALL="1"
        shift
        ;;
      --dry-run)
        BOOTSTRAP_DRY_RUN="1"
        shift
        ;;
      --list)
        LIST_ONLY="1"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown argument: $1"
        ;;
    esac
  done

  if [[ -n "$TARGET_STAGE" && -n "$FROM_STAGE" ]]; then
    die "Use either --stage or --from-stage, not both"
  fi
  if [[ "$FORCE_STAGE" == "1" && -z "$TARGET_STAGE" && -z "$FROM_STAGE" ]]; then
    die "--force-stage requires --stage or --from-stage. Use --force-all to rerun the full bootstrap."
  fi
}

main() {
  SCRIPT_NAME="bootstrap.sh"
  parse_args "$@"
  acquire_lock "$SCRIPT_NAME"
  ensure_root_dirs
  validate_stage_graph

  if [[ "$LIST_ONLY" == "1" ]]; then
    print_plan
    return 0
  fi

  if [[ "$FORCE_ALL" == "1" ]]; then
    log WARN "Clearing all bootstrap stage markers because --force-all was supplied"
    clear_all_stage_markers
  fi

  log INFO "Starting Pocket Lab Day-0 bootstrap dispatcher version $BOOTSTRAP_VERSION"
  log INFO "Mode: $([[ "$BOOTSTRAP_DRY_RUN" == "1" ]] && printf 'dry-run' || printf 'execute')"

  local start_index end_index i selector_index total
  total="$(stage_count)"

  if [[ -n "$TARGET_STAGE" ]]; then
    selector_index="$(find_stage_index "$TARGET_STAGE")" || die "Unknown stage selector: $TARGET_STAGE"
    require_prior_stages_done "$selector_index"
    run_stage_by_index "$selector_index"
    log INFO "Requested single stage completed: $TARGET_STAGE"
    return 0
  fi

  if [[ -n "$FROM_STAGE" ]]; then
    start_index="$(find_stage_index "$FROM_STAGE")" || die "Unknown stage selector: $FROM_STAGE"
  else
    start_index="1"
  fi
  end_index="$total"

  for (( i=start_index; i<=end_index; i++ )); do
    run_stage_by_index "$i"
  done

  log INFO "Pocket Lab Day-0 bootstrap complete. Verify services with: pm2 status"
}

on_error() {
  local rc=$? line=${BASH_LINENO[0]:-unknown} cmd=${BASH_COMMAND:-unknown}
  if [[ -n "${CURRENT_STAGE_ID:-}" ]]; then
    log FATAL "Bootstrap failed during stage '$CURRENT_STAGE_ID' ($CURRENT_STAGE_NAME), rc=$rc, line=$line, command: $cmd"
  else
    log FATAL "Bootstrap failed before stage execution, rc=$rc, line=$line, command: $cmd"
  fi
  exit "$rc"
}
trap on_error ERR

main "$@"
