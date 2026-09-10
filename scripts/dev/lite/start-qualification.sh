#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${POCKETLAB_HARNESS_PROVISIONING_TOKEN:-}" ]]; then
  echo "ERROR POCKETLAB_HARNESS_PROVISIONING_TOKEN is required for explicit qualification startup" >&2
  exit 2
fi

for arg in "$@"; do
  case "$arg" in
    --profile|--profile=*)
      echo "ERROR qualification startup owns the --profile lite selection" >&2
      exit 2
      ;;
  esac
done

# Qualification is an explicit opt-in. The production Lite launcher continues
# to default to a disabled harness and a production environment.
export POCKETLAB_ENVIRONMENT=qualification
export POCKETLAB_HARNESS_ENABLED=1
export POCKETLAB_HARNESS_DESTRUCTIVE="${POCKETLAB_HARNESS_DESTRUCTIVE:-0}"
export POCKETLAB_QUALIFICATION_OWNER="${POCKETLAB_QUALIFICATION_OWNER:-0}"
export POCKETLAB_TEST_AUTH_BYPASS="${POCKETLAB_TEST_AUTH_BYPASS:-0}"

exec bash "$SCRIPT_DIR/../../../pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh" --profile lite "$@"
