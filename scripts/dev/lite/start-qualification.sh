#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

bootstrap_principal_id=""
bootstrap_public_key_file=""
bootstrap_profile=""
target_device_id=""
recovery_target_main_sha=""
recovery_target_schema=""
bootstrap_requested=0
fault_control_requested=0
forward_args=()
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --bootstrap-principal-id)
      [[ "${2:-}" != "" ]] || { echo "ERROR --bootstrap-principal-id requires a value" >&2; exit 2; }
      bootstrap_principal_id="$2"
      bootstrap_requested=1
      shift 2
      ;;
    --bootstrap-public-key-file)
      [[ "${2:-}" != "" ]] || { echo "ERROR --bootstrap-public-key-file requires a value" >&2; exit 2; }
      bootstrap_public_key_file="$2"
      bootstrap_requested=1
      shift 2
      ;;
    --bootstrap-profile)
      [[ "${2:-}" != "" ]] || { echo "ERROR --bootstrap-profile requires a value" >&2; exit 2; }
      bootstrap_profile="$2"
      bootstrap_requested=1
      shift 2
      ;;
    --target-device-id)
      [[ "${2:-}" != "" ]] || { echo "ERROR --target-device-id requires a value" >&2; exit 2; }
      target_device_id="$2"
      shift 2
      ;;
    --recovery-target-main-sha)
      [[ "${2:-}" != "" ]] || { echo "ERROR --recovery-target-main-sha requires a value" >&2; exit 2; }
      recovery_target_main_sha="$2"
      shift 2
      ;;
    --recovery-target-schema)
      [[ "${2:-}" != "" ]] || { echo "ERROR --recovery-target-schema requires a value" >&2; exit 2; }
      recovery_target_schema="$2"
      shift 2
      ;;
    --enable-fault-control)
      fault_control_requested=1
      shift
      ;;
    --profile|--profile=*)
      echo "ERROR qualification startup owns the --profile lite selection" >&2
      exit 2
      ;;
    *)
      forward_args+=("$1")
      shift
      ;;
  esac
done

if [[ "$bootstrap_requested" -eq 1 ]]; then
  [[ -n "$bootstrap_principal_id" && -n "$bootstrap_public_key_file" && -n "$bootstrap_profile" ]] || {
    echo "ERROR bootstrap approval requires principal id, public-key file, and profile" >&2
    exit 2
  }
  [[ "$bootstrap_principal_id" =~ ^[a-z][a-z0-9._-]{2,79}$ ]] || {
    echo "ERROR bootstrap principal id is invalid" >&2
    exit 2
  }
  case "$bootstrap_profile" in
    security-assurance-runner|qualification-owner|fleet-role-qualifier|recovery-qualifier) ;;
    *)
      echo "ERROR bootstrap approval profile is not permitted" >&2
      exit 2
      ;;
  esac
  if [[ "$bootstrap_profile" == "fleet-role-qualifier" ]]; then
    [[ "$target_device_id" =~ ^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$ ]] || {
      echo "ERROR fleet-role-qualifier bootstrap requires one exact target device id" >&2
      exit 2
    }
  elif [[ -n "$target_device_id" ]]; then
    echo "ERROR --target-device-id is only valid for fleet-role-qualifier bootstrap" >&2
    exit 2
  fi
  if [[ "$bootstrap_profile" == "recovery-qualifier" ]]; then
    [[ "${recovery_target_main_sha:-}" =~ ^[0-9a-fA-F]{40}$ ]] || {
      echo "ERROR recovery-qualifier bootstrap requires the exact target main SHA" >&2
      exit 2
    }
    [[ "${recovery_target_schema:-}" =~ ^[1-9][0-9]{0,2}$ ]] || {
      echo "ERROR recovery-qualifier bootstrap requires the target main schema version" >&2
      exit 2
    }
  elif [[ -n "$recovery_target_main_sha" || -n "$recovery_target_schema" ]]; then
    echo "ERROR recovery target binding is only valid for recovery-qualifier bootstrap" >&2
    exit 2
  fi
  [[ -f "$bootstrap_public_key_file" ]] || {
    echo "ERROR bootstrap public-key file is unavailable" >&2
    exit 2
  }
  bootstrap_fingerprint="$(python3 - "$bootstrap_public_key_file" <<'PYKEY'
import base64
import hashlib
import re
import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
raw = path.read_bytes()
if len(raw) > 512 or b"PRIVATE KEY" in raw or b"BEGIN OPENSSH PRIVATE" in raw:
    raise SystemExit(2)
value = raw.decode("ascii").strip()
if not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
    raise SystemExit(2)
try:
    public = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
except (ValueError, base64.binascii.Error):
    raise SystemExit(2)
if len(public) != 32:
    raise SystemExit(2)
print("sha256:" + hashlib.sha256(public).hexdigest())
PYKEY
)" || {
    echo "ERROR bootstrap public-key file must contain one raw Ed25519 public key" >&2
    exit 2
  }
  flag_is_off() {
    case "${1:-0}" in
      0|false|FALSE|False|no|NO|No|off|OFF|Off|"") return 0 ;;
      *) return 1 ;;
    esac
  }
  flag_is_on() {
    ! flag_is_off "${1:-0}"
  }
  if ! flag_is_off "${POCKETLAB_HARNESS_DESTRUCTIVE:-0}" \
    || ! flag_is_off "${POCKETLAB_TEST_AUTH_BYPASS:-0}"; then
    echo "ERROR key-bound qualification bootstrap requires destructive and test-bypass flags to be off" >&2
    exit 2
  fi
  if [[ "$bootstrap_profile" == "security-assurance-runner" ]] && ! flag_is_off "${POCKETLAB_QUALIFICATION_OWNER:-0}"; then
    echo "ERROR security-assurance-runner bootstrap requires the Owner gate to be off" >&2
    exit 2
  fi
  if [[ "$bootstrap_profile" == "qualification-owner" ]] && ! flag_is_on "${POCKETLAB_QUALIFICATION_OWNER:-0}"; then
    echo "ERROR qualification-owner bootstrap requires the explicit Owner gate" >&2
    exit 2
  fi
  if [[ "$bootstrap_profile" == "qualification-owner" && "$fault_control_requested" -eq 1 ]]; then
    echo "ERROR qualification-owner UI bootstrap cannot enable assurance fault control" >&2
    exit 2
  fi
else
  if [[ "$fault_control_requested" -eq 1 ]]; then
    echo "ERROR --enable-fault-control requires key-bound assurance bootstrap" >&2
    exit 2
  fi
  if [[ -z "${POCKETLAB_HARNESS_PROVISIONING_TOKEN:-}" ]]; then
    echo "ERROR POCKETLAB_HARNESS_PROVISIONING_TOKEN is required for explicit qualification startup" >&2
    exit 2
  fi
fi

# Qualification is an explicit opt-in. The production Lite launcher continues
# to default to a disabled harness and a production environment.
export POCKETLAB_ENVIRONMENT=qualification
export POCKETLAB_HARNESS_ENABLED=1
export POCKETLAB_BASE_DIR="${POCKETLAB_BASE_DIR:-${POCKET_LAB_BASE_DIR:-$HOME/pocket-lab-lite}}"
qualification_state_dir="$(python3 - "$POCKETLAB_BASE_DIR" <<'PYSTATE'
from pathlib import Path
import sys

base = Path(sys.argv[1]).expanduser().resolve(strict=False)
main = (base / "state").resolve(strict=False)
qualification = (base / "qualification-state").resolve(strict=False)
if qualification == main:
    raise SystemExit("qualification state must differ from the production state")
print(qualification)
PYSTATE
)" || {
  echo "ERROR could not derive an isolated qualification state directory" >&2
  exit 2
}
export POCKETLAB_QUALIFICATION=1
export POCKETLAB_QUALIFICATION_STATE_DIR="$qualification_state_dir"
export POCKETLAB_STATE_DIR="$qualification_state_dir"
export POCKETLAB_LITE_DB_PATH="$qualification_state_dir/pocketlab-lite.sqlite3"
if [[ -z "${POCKETLAB_QUALIFICATION_NATS_CREDENTIALS_FILE:-}" ]]; then
  main_nats_credentials="$HOME/.pocket_lab/nats/pocketlab-nats.env"
  if [[ -f "$main_nats_credentials" ]]; then
    export POCKETLAB_NATS_CREDENTIALS_FILE="$main_nats_credentials"
  fi
else
  export POCKETLAB_NATS_CREDENTIALS_FILE="$POCKETLAB_QUALIFICATION_NATS_CREDENTIALS_FILE"
fi
if [[ "$bootstrap_requested" -eq 1 ]]; then
  export POCKETLAB_HARNESS_DESTRUCTIVE=0
  if [[ "$bootstrap_profile" == "qualification-owner" ]]; then
    export POCKETLAB_QUALIFICATION_OWNER=1
  else
    export POCKETLAB_QUALIFICATION_OWNER=0
  fi
  export POCKETLAB_TEST_AUTH_BYPASS=0
  export POCKETLAB_HARNESS_BOOTSTRAP_APPROVED=1
  export POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID="$bootstrap_principal_id"
  export POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT="$bootstrap_fingerprint"
  export POCKETLAB_HARNESS_BOOTSTRAP_PROFILE="$bootstrap_profile"
  export POCKETLAB_HARNESS_FAULT_CONTROL="$fault_control_requested"
  if [[ "$bootstrap_profile" == "fleet-role-qualifier" ]]; then
    export POCKETLAB_HARNESS_TARGET_DEVICE_ID="$target_device_id"
  else
    unset POCKETLAB_HARNESS_TARGET_DEVICE_ID
  fi
  if [[ "$bootstrap_profile" == "recovery-qualifier" ]]; then
    export POCKETLAB_RECOVERY_TARGET_MAIN_SHA="${recovery_target_main_sha,,}"
    export POCKETLAB_RECOVERY_TARGET_SCHEMA="$recovery_target_schema"
  else
    unset POCKETLAB_RECOVERY_TARGET_MAIN_SHA POCKETLAB_RECOVERY_TARGET_SCHEMA
  fi
else
  export POCKETLAB_HARNESS_DESTRUCTIVE="${POCKETLAB_HARNESS_DESTRUCTIVE:-0}"
  export POCKETLAB_QUALIFICATION_OWNER="${POCKETLAB_QUALIFICATION_OWNER:-0}"
  export POCKETLAB_TEST_AUTH_BYPASS="${POCKETLAB_TEST_AUTH_BYPASS:-0}"
  export POCKETLAB_HARNESS_FAULT_CONTROL=0
fi

exec bash "$SCRIPT_DIR/../../../pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh" --profile lite "${forward_args[@]}"
