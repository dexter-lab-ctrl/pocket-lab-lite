#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${POCKETLAB_REPO_ROOT:-$(CDPATH='' cd -- "$SCRIPT_DIR/../../../.." && pwd)}"
STATE_DIR="${POCKETLAB_STATE_DIR:-${POCKETLAB_BASE_DIR:-$HOME/.pocket_lab}/state}"
SOURCE_DIR="${POCKETLAB_OPA_POLICY_SOURCE_DIR:-$REPO_ROOT/security/policies/opa/pocketlab}"
OPA_BIN="${POCKETLAB_OPA_BIN:-$(command -v opa || true)}"

[[ -n "$OPA_BIN" && -x "$OPA_BIN" ]] || { printf '%s\n' 'OPA is not installed; protected changes will remain fail-closed.' >&2; exit 1; }
[[ -f "$SOURCE_DIR/pocketlab.rego" ]] || { printf 'Missing policy source: %s\n' "$SOURCE_DIR/pocketlab.rego" >&2; exit 1; }

mapfile -d '' policy_files < <(find "$SOURCE_DIR" -type f -name '*.rego' -print0 | sort -z)
[[ "${#policy_files[@]}" -gt 0 ]] || { printf 'No Rego policy files found under: %s\n' "$SOURCE_DIR" >&2; exit 1; }
for policy_file in "${policy_files[@]}"; do
  "$OPA_BIN" fmt --fail --check-result "$policy_file" >/dev/null
done
"$OPA_BIN" check --strict "$SOURCE_DIR"
"$OPA_BIN" test --fail-on-empty "$SOURCE_DIR"

revision="$(sha256sum "$SOURCE_DIR/pocketlab.rego" | awk '{print substr($1,1,24)}')"
opa_root="$STATE_DIR/opa"
stage_root="$opa_root/stage"
stage="$stage_root/$revision"
active="$opa_root/active"
next_link="$opa_root/.active.$$.next"

mkdir -p "$stage_root"
chmod 700 "$opa_root" "$stage_root"
if [[ ! -d "$stage" ]]; then
  tmp="$stage_root/.${revision}.$$.tmp"
  rm -rf "$tmp"
  mkdir -p "$tmp"
  install -m 0644 "$SOURCE_DIR/pocketlab.rego" "$tmp/pocketlab.rego"
  printf '%s\n' "$revision" > "$tmp/revision.txt"
  chmod 0644 "$tmp/revision.txt"
  mv "$tmp" "$stage"
fi
cleanup() {
  rm -f "$next_link"
  [[ -n "${tmp:-}" ]] && rm -rf "$tmp"
}
trap cleanup EXIT INT TERM

rm -f "$next_link"
ln -s "$stage" "$next_link"
if [[ -e "$active" && ! -L "$active" ]]; then
  printf 'Refusing to replace unexpected OPA active path: %s\n' "$active" >&2
  exit 1
fi
python3 - "$next_link" "$active" <<'PYACTIVATE'
import os
import sys
os.replace(sys.argv[1], sys.argv[2])
PYACTIVATE
trap - EXIT INT TERM
printf 'OPA policy ready revision=%s\n' "$revision"
