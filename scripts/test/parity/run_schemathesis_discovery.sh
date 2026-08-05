#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCHEMATHESIS="${POCKETLAB_SCHEMATHESIS_BIN:-$ROOT/.pocketlab-dev/tools/parity/bin/schemathesis}"
PYTHON_BIN="${POCKETLAB_DEV_PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="${PYTHON:-python3}"
BASE_URL="${LITE_API_DIRECT_URL:-http://127.0.0.1:8000}"
OPENAPI="${LITE_PARITY_OPENAPI_URL:-$BASE_URL/openapi.json}"
REPORT_DIR="${VALIDATION_DIR:-$ROOT/.pocketlab-dev/validation}/parity/schemathesis-discovery"
SCHEMA="$REPORT_DIR/openapi-discovery.json"
MANIFEST="$REPORT_DIR/selection-manifest.json"

case "$BASE_URL" in
  http://127.0.0.1:*|http://localhost:*) ;;
  *) printf 'ERROR discovery is restricted to an isolated loopback API target
' >&2; exit 2 ;;
esac
case "$OPENAPI" in
  http://127.0.0.1:*|http://localhost:*) ;;
  *) printf 'ERROR OpenAPI source is restricted to an isolated loopback API target
' >&2; exit 2 ;;
esac
[[ -x "$SCHEMATHESIS" ]] || { printf 'UNAVAILABLE Schemathesis; run setup-parity-tools.sh --install-missing
' >&2; exit 2; }
if ! curl -fsS --connect-timeout 2 --max-time 8 "$OPENAPI" >/dev/null; then
  printf 'ERROR Lite OpenAPI is not reachable: %s
' "$OPENAPI" >&2
  exit 2
fi
mkdir -p "$REPORT_DIR"

"$PYTHON_BIN" "$ROOT/scripts/test/parity/prepare_schemathesis_schema.py"   --profile discovery   --openapi-url "$OPENAPI"   --base-url "$BASE_URL"   --output "$SCHEMA"   --manifest "$MANIFEST"   --timeout "${LITE_PARITY_SCHEMA_TIMEOUT:-12}"

rm -f "$REPORT_DIR/junit.xml" "$REPORT_DIR/events.ndjson" "$REPORT_DIR/summary.json"
set +e
"$SCHEMATHESIS" run "$SCHEMA"   --url "$BASE_URL"   --phases examples,fuzzing   --mode all   --checks status_code_conformance,content_type_conformance,response_schema_conformance   --max-examples "${LITE_PARITY_SCHEMATHESIS_DISCOVERY_EXAMPLES:-12}"   --max-failures "${LITE_PARITY_SCHEMATHESIS_DISCOVERY_MAX_FAILURES:-100}"   --continue-on-failure   --workers 1   --generation-deterministic   --generation-allow-x00 false   --generation-unique-inputs   --rate-limit "${LITE_PARITY_SCHEMATHESIS_DISCOVERY_RATE_LIMIT:-3/s}"   --request-timeout "${LITE_PARITY_SCHEMATHESIS_DISCOVERY_TIMEOUT:-20}"   --request-retries 1   --output-sanitize true   --report junit,ndjson   --report-junit-path "$REPORT_DIR/junit.xml"   --report-ndjson-path "$REPORT_DIR/events.ndjson"
status=$?
set -e
"$PYTHON_BIN" "$ROOT/scripts/test/parity/summarize_schemathesis.py"   --junit "$REPORT_DIR/junit.xml"   --output "$REPORT_DIR/summary.json"   --profile discovery   --exit-status "$status"
printf 'INFO Schemathesis discovery completed with status %s
' "$status"
printf 'INFO Discovery reports: %s
' "$REPORT_DIR"
exit 0
