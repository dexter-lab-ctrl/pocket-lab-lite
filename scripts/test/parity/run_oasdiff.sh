#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
OASDIFF="${POCKETLAB_OASDIFF_BIN:-$ROOT/.pocketlab-dev/tools/parity/bin/oasdiff}"
BASELINE="${LITE_PARITY_OPENAPI_BASELINE:-$ROOT/contracts/parity/openapi-baseline.json}"
CURRENT="${LITE_PARITY_OPENAPI_CURRENT:-$ROOT/contracts/generated/lite-openapi.json}"
REPORT="${VALIDATION_DIR:-$ROOT/.pocketlab-dev/validation}/parity/oasdiff-breaking.json"

[[ -x "$OASDIFF" ]] || { printf 'UNAVAILABLE oasdiff; run setup-parity-tools.sh --install-missing\n' >&2; exit 2; }
[[ -f "$BASELINE" ]] || { printf 'UNAVAILABLE OpenAPI baseline: %s\n' "$BASELINE" >&2; exit 2; }
[[ -f "$CURRENT" ]] || { printf 'ERROR current OpenAPI contract missing: %s\n' "$CURRENT" >&2; exit 2; }
mkdir -p "$(dirname "$REPORT")"
"$OASDIFF" breaking "$BASELINE" "$CURRENT" --format json --output "$REPORT"
printf 'PASS no unapproved OpenAPI breaking changes\n'
