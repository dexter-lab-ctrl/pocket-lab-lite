#!/usr/bin/env bash
# Capability-aware completion checks for Lite bootstrap stages.
#
# Bootstrap markers are durable across source upgrades. A marker therefore proves
# only that an older stage invocation once succeeded; it must not be allowed to
# suppress newly-added runtime prerequisites. These checks are deliberately
# read-only and bounded. They never install, restart, or mutate runtime state.

POCKETLAB_LITE_STAGE_HEALTH_REASON=""

pocketlab_lite_stage_completion_is_valid() {
  local stage_id="${1:-}"
  POCKETLAB_LITE_STAGE_HEALTH_REASON=""

  case "$stage_id" in
    install_binaries)
      if ! is_done lite_opa_ready; then
        POCKETLAB_LITE_STAGE_HEALTH_REASON="OPA capability marker is missing"
        return 1
      fi
      if ! command -v opa >/dev/null 2>&1; then
        POCKETLAB_LITE_STAGE_HEALTH_REASON="OPA command is missing"
        return 1
      fi
      if ! opa version >/dev/null 2>&1; then
        POCKETLAB_LITE_STAGE_HEALTH_REASON="OPA command is not usable"
        return 1
      fi
      return 0
      ;;

    start_dashboard)
      if ! pocketlab_lite_stage_completion_is_valid install_binaries; then
        return 1
      fi
      if ! command -v pm2 >/dev/null 2>&1 || ! pm2 describe pocket-opa >/dev/null 2>&1; then
        POCKETLAB_LITE_STAGE_HEALTH_REASON="pocket-opa is not registered with PM2"
        return 1
      fi
      if ! command -v curl >/dev/null 2>&1 || ! curl -fsS --max-time 2 http://127.0.0.1:8181/health >/dev/null 2>&1; then
        POCKETLAB_LITE_STAGE_HEALTH_REASON="OPA loopback health is not ready"
        return 1
      fi

      local lite_base_dir state_dir policy_dir
      lite_base_dir="${POCKETLAB_BASE_DIR:-${POCKET_LAB_BASE_DIR:-$HOME/pocket-lab-lite}}"
      state_dir="${POCKETLAB_STATE_DIR:-$lite_base_dir/state}"
      policy_dir="${POCKETLAB_OPA_ACTIVE_POLICY_DIR:-$state_dir/opa/active}"
      if [[ ! -f "$policy_dir/pocketlab.rego" || ! -s "$policy_dir/revision.txt" ]]; then
        POCKETLAB_LITE_STAGE_HEALTH_REASON="active OPA policy revision is missing"
        return 1
      fi

      local api_port="${API_PORT:-8080}"
      if ! curl -fsS --max-time 3 "http://127.0.0.1:${api_port}/api/lite/policy" \
        | python3 -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

engine = payload.get("engine")
policy = payload.get("active_policy")
valid = (
    payload.get("status") == "ready"
    and isinstance(engine, dict)
    and engine.get("healthy") is True
    and engine.get("endpoint_exposed_to_browser") is False
    and isinstance(policy, dict)
    and policy.get("bundle_ready") is True
)
raise SystemExit(0 if valid else 1)
' >/dev/null 2>&1; then
        POCKETLAB_LITE_STAGE_HEALTH_REASON="FastAPI Rules projection is not bound to the ready OPA runtime"
        return 1
      fi
      return 0
      ;;

    *)
      return 0
      ;;
  esac
}
