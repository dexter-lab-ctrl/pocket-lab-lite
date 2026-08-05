#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
OASDIFF="${POCKETLAB_OASDIFF_BIN:-$ROOT/.pocketlab-dev/tools/parity/bin/oasdiff}"
PYTHON_BIN="${POCKETLAB_DEV_PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="${PYTHON:-python3}"
BASELINE="${LITE_PARITY_OPENAPI_BASELINE:-$ROOT/contracts/parity/openapi-baseline.json}"
CURRENT="${LITE_PARITY_OPENAPI_CURRENT:-$ROOT/contracts/generated/lite-openapi.json}"
PROMOTION="${LITE_PARITY_OPENAPI_PROMOTION:-$ROOT/contracts/parity/openapi-baseline-promotion.json}"
REPORT="${VALIDATION_DIR:-$ROOT/.pocketlab-dev/validation}/parity/oasdiff-breaking.json"
TEMP_REPORT="${REPORT}.tmp"

[[ -x "$OASDIFF" ]] || { printf 'UNAVAILABLE oasdiff; run setup-parity-tools.sh --install-missing\n' >&2; exit 2; }
[[ -f "$BASELINE" ]] || { printf 'UNAVAILABLE OpenAPI baseline: %s\n' "$BASELINE" >&2; exit 2; }
[[ -f "$CURRENT" ]] || { printf 'ERROR current OpenAPI contract missing: %s\n' "$CURRENT" >&2; exit 2; }
[[ -f "$PROMOTION" ]] || { printf 'ERROR baseline promotion evidence missing: %s\n' "$PROMOTION" >&2; exit 2; }

"$PYTHON_BIN" - "$BASELINE" "$PROMOTION" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

baseline = Path(sys.argv[1])
promotion_path = Path(sys.argv[2])
promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
actual = hashlib.sha256(baseline.read_bytes()).hexdigest()
if promotion.get("status") != "promoted" or promotion.get("promoted_sha256") != actual:
    raise SystemExit("ERROR OpenAPI baseline is not backed by matching explicit promotion evidence")
if promotion.get("security_review", {}).get("raw_secrets_included") is not False:
    raise SystemExit("ERROR OpenAPI baseline promotion did not record a secret-safety review")
print(f"PASS promoted OpenAPI baseline verified: {actual[:12]}")
PY

mkdir -p "$(dirname "$REPORT")"
rm -f "$TEMP_REPORT"
trap 'rm -f "$TEMP_REPORT"' EXIT

"$OASDIFF" breaking "$BASELINE" "$CURRENT" \
  --allow-external-refs=false \
  --fail-on ERR \
  --format json \
  > "$TEMP_REPORT"

[[ -s "$TEMP_REPORT" ]] || printf '{}\n' > "$TEMP_REPORT"
"$PYTHON_BIN" -m json.tool "$TEMP_REPORT" >/dev/null
mv -f "$TEMP_REPORT" "$REPORT"
trap - EXIT
printf 'PASS no unapproved OpenAPI breaking changes; report: %s\n' "$REPORT"
