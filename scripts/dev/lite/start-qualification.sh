#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

bootstrap_principal_id=""
bootstrap_public_key_file=""
bootstrap_profile=""
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
  [[ "$bootstrap_profile" == "security-assurance-runner" ]] || {
    echo "ERROR bootstrap approval permits only security-assurance-runner" >&2
    exit 2
  }
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
  if ! flag_is_off "${POCKETLAB_HARNESS_DESTRUCTIVE:-0}" \
    || ! flag_is_off "${POCKETLAB_QUALIFICATION_OWNER:-0}" \
    || ! flag_is_off "${POCKETLAB_TEST_AUTH_BYPASS:-0}"; then
    echo "ERROR key-bound assurance bootstrap requires destructive, Owner, and test-bypass flags to be off" >&2
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
if [[ "$bootstrap_requested" -eq 1 ]]; then
  export POCKETLAB_HARNESS_DESTRUCTIVE=0
  export POCKETLAB_QUALIFICATION_OWNER=0
  export POCKETLAB_TEST_AUTH_BYPASS=0
  export POCKETLAB_HARNESS_BOOTSTRAP_APPROVED=1
  export POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID="$bootstrap_principal_id"
  export POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT="$bootstrap_fingerprint"
  export POCKETLAB_HARNESS_BOOTSTRAP_PROFILE="$bootstrap_profile"
  export POCKETLAB_HARNESS_FAULT_CONTROL="$fault_control_requested"
else
  export POCKETLAB_HARNESS_DESTRUCTIVE="${POCKETLAB_HARNESS_DESTRUCTIVE:-0}"
  export POCKETLAB_QUALIFICATION_OWNER="${POCKETLAB_QUALIFICATION_OWNER:-0}"
  export POCKETLAB_TEST_AUTH_BYPASS="${POCKETLAB_TEST_AUTH_BYPASS:-0}"
  export POCKETLAB_HARNESS_FAULT_CONTROL=0
fi

exec bash "$SCRIPT_DIR/../../../pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh" --profile lite "${forward_args[@]}"
