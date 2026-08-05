#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCHEMATHESIS="${POCKETLAB_SCHEMATHESIS_BIN:-$ROOT/.pocketlab-dev/tools/parity/bin/schemathesis}"
BASE_URL="${LITE_API_DIRECT_URL:-http://127.0.0.1:8000}"
OPENAPI="${LITE_PARITY_OPENAPI_URL:-$BASE_URL/openapi.json}"
REPORT_DIR="${VALIDATION_DIR:-$ROOT/.pocketlab-dev/validation}/parity/schemathesis"

case "$BASE_URL" in
  http://127.0.0.1:*|http://localhost:*) ;;
  *) printf 'ERROR Schemathesis parity runs are restricted to an isolated loopback API target\n' >&2; exit 2 ;;
esac

EXCLUDE='/(backup|restore|check|restart|remove|install|update|repair|invite)(/|$)'

[[ -x "$SCHEMATHESIS" ]] || { printf 'UNAVAILABLE Schemathesis; run setup-parity-tools.sh --install-missing\n' >&2; exit 2; }
mkdir -p "$REPORT_DIR"

# Read-only, bounded API property testing. Destructive/write endpoints are always excluded.
exec "$SCHEMATHESIS" run "$OPENAPI" \
  --url "$BASE_URL" \
  --include-method GET \
  --exclude-path-regex "$EXCLUDE" \
  --max-examples "${LITE_PARITY_SCHEMATHESIS_EXAMPLES:-20}" \
  --workers 1 \
  --generation-deterministic \
  --generation-database ":memory:" \
  --rate-limit "10/s" \
  --request-timeout 5 \
  --report junit \
  --report-junit-path "$REPORT_DIR/junit.xml"
