#!/usr/bin/env bash
# Staging is immutable. Activation is an explicit supervisor-only pointer update.
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${POCKETLAB_REPO_ROOT:-$(CDPATH='' cd -- "$SCRIPT_DIR/../../../.." && pwd)}"
STATE_DIR="${POCKETLAB_STATE_DIR:-${POCKETLAB_BASE_DIR:-$HOME/.pocket_lab}/state}"
SOURCE_DIR="${POCKETLAB_OPA_POLICY_SOURCE_DIR:-$REPO_ROOT/security/policies/opa/pocketlab}"
OPA_BIN="${POCKETLAB_OPA_BIN:-$(command -v opa || true)}"
ACTION="${1:-stage}"
REQUESTED_REVISION="${2:-}"

[[ -n "$OPA_BIN" && -x "$OPA_BIN" ]] || { printf '%s\n' 'OPA is not installed; protected changes remain fail-closed.' >&2; exit 1; }
[[ -d "$SOURCE_DIR" ]] || { printf '%s\n' 'OPA policy source directory is missing.' >&2; exit 1; }
case "$ACTION" in stage|activate|known-good) ;; *) printf '%s\n' 'Usage: prepare-opa-policy.sh [stage|activate|known-good] [revision]' >&2; exit 64;; esac

opa_root="$STATE_DIR/opa"; stage_root="$opa_root/stage"
mkdir -p "$stage_root"; chmod 700 "$opa_root" "$stage_root"

switch_pointer() {
  local name target next
  name="$1"; target="$2"; next="$opa_root/.${name}.$$.next"
  [[ -d "$target" && -f "$target/manifest.json" ]] || { printf '%s\n' 'Refusing an unknown policy stage.' >&2; exit 1; }
  [[ -e "$opa_root/$name" && ! -L "$opa_root/$name" ]] && { printf '%s\n' 'Refusing to replace unmanaged policy pointer.' >&2; exit 1; }
  rm -f "$next"; ln -s "$target" "$next"
  python3 - "$next" "$opa_root/$name" <<'PY'
import os, sys
os.replace(sys.argv[1], sys.argv[2])
PY
}

if [[ "$ACTION" != stage ]]; then
  [[ -n "$REQUESTED_REVISION" && "$REQUESTED_REVISION" =~ ^[A-Za-z0-9._-]{8,80}$ ]] || { printf '%s\n' 'A bounded revision is required.' >&2; exit 64; }
  target="$stage_root/$REQUESTED_REVISION"
  [[ -f "$target/revision.txt" && "$(tr -d '\r\n' < "$target/revision.txt")" == "$REQUESTED_REVISION" ]] || { printf '%s\n' 'Requested policy stage is corrupt.' >&2; exit 1; }
  switch_pointer "$([[ "$ACTION" == known-good ]] && printf known-good || printf active)" "$target"
  printf 'OPA pointer updated revision=%s pointer=%s\n' "$REQUESTED_REVISION" "$ACTION"
  exit 0
fi

mapfile -d '' source_files < <(find "$SOURCE_DIR" -type f -name '*.rego' -print0 | sort -z)
[[ "${#source_files[@]}" -gt 0 ]] || { printf '%s\n' 'No approved OPA source modules found.' >&2; exit 1; }
for policy_file in "${source_files[@]}"; do "$OPA_BIN" fmt --fail --check-result "$policy_file" >/dev/null; done
"$OPA_BIN" check --strict "$SOURCE_DIR"; "$OPA_BIN" test --fail-on-empty "$SOURCE_DIR"
default_template_json='{"parameters":{},"template_id":"baseline","template_version":"1"}'
template_json="${POCKETLAB_POLICY_TEMPLATE_JSON:-$default_template_json}"
template_digest="$(printf '%s' "$template_json" | sha256sum | awk '{print $1}')"
source_digest="$({ for policy_file in "${source_files[@]}"; do rel="${policy_file#"$SOURCE_DIR"/}"; printf '%s  %s\n' "$(sha256sum "$policy_file" | awk '{print $1}')" "$rel"; done; printf '%s  template.json\n' "$template_digest"; } | sha256sum | awk '{print $1}')"
revision="${POCKETLAB_POLICY_REVISION:-plr-${source_digest:0:32}}"
[[ "$revision" =~ ^[A-Za-z0-9._-]{8,80}$ ]] || { printf '%s\n' 'Configured policy revision is invalid.' >&2; exit 64; }
stage="$stage_root/$revision"
if [[ -d "$stage" ]]; then [[ -f "$stage/manifest.json" && "$(tr -d '\r\n' < "$stage/revision.txt")" == "$revision" ]] || { printf '%s\n' 'Existing policy stage is corrupt.' >&2; exit 1; }; printf 'OPA candidate already staged revision=%s\n' "$revision"; exit 0; fi
tmp="$stage_root/.${revision}.$$.tmp"; cleanup() { [[ -n "${tmp:-}" ]] && rm -rf "$tmp"; }; trap cleanup EXIT INT TERM
mkdir -p "$tmp"
for policy_file in "${source_files[@]}"; do rel="${policy_file#"$SOURCE_DIR"/}"; mkdir -p "$tmp/$(dirname -- "$rel")"; install -m 0644 "$policy_file" "$tmp/$rel"; done
printf '%s\n' "$template_json" > "$tmp/template.json"
printf 'package pocketlab.meta\n\nrevision := "%s"\n' "$revision" > "$tmp/revision.rego"
"$OPA_BIN" fmt -w "$tmp/revision.rego"; "$OPA_BIN" check --strict "$tmp"
printf '%s\n' "$revision" > "$tmp/revision.txt"
python3 - "$tmp" "$revision" <<'PY'
import hashlib, json, pathlib, sys
root, revision = pathlib.Path(sys.argv[1]), sys.argv[2]
files = [{'path': p.relative_to(root).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(root.rglob('*')) if p.is_file() and p.name not in {'manifest.json', 'revision.txt'}]
candidate_hash = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
(root / 'manifest.json').write_text(json.dumps({'revision': revision, 'candidate_hash': candidate_hash, 'files': files}, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
chmod -R go-rwx "$tmp"; mv "$tmp" "$stage"; tmp=""; trap - EXIT INT TERM
printf 'OPA candidate staged revision=%s\n' "$revision"
