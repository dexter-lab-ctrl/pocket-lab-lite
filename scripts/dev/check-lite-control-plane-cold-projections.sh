#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${POCKETLAB_STATE_DIR:-$HOME/pocket-lab-lite/state}"
PROXY_BASE="${POCKETLAB_PROXY_BASE:-http://127.0.0.1:8443}"
RUN_DIR="${1:-$STATE_DIR/.pocketlab-dev/sqlite-p3-subprojection-check}"
mkdir -p "$RUN_DIR"


READY_ATTEMPTS="${POCKETLAB_READY_ATTEMPTS:-60}"
READY_CONNECT_TIMEOUT="${POCKETLAB_READY_CONNECT_TIMEOUT:-2}"
READY_MAX_TIME="${POCKETLAB_READY_MAX_TIME:-3}"
API_READY=0

for attempt in $(seq 1 "$READY_ATTEMPTS"); do
  if curl -fsS \
    --connect-timeout "$READY_CONNECT_TIMEOUT" \
    --max-time "$READY_MAX_TIME" \
    "$PROXY_BASE/health" \
    > "$RUN_DIR/health.json"
  then
    API_READY=1
    printf 'Pocket API ready after attempt %s\n' "$attempt"
    break
  fi
  sleep 1
done

if [[ "$API_READY" -ne 1 ]]; then
  printf 'Pocket API did not become ready after %s attempts.\n' "$READY_ATTEMPTS" >&2
  exit 1
fi

paths=(
  /api/lite/apps/lifecycle
  /api/lite/recovery/summary
  /api/lite/recovery/details
)

for path in "${paths[@]}"; do
  name="$(printf '%s' "$path" | tr '/?' '__')"
  curl -sS \
    -D "$RUN_DIR/${name}.headers" \
    -o "$RUN_DIR/${name}.json" \
    -w "$path status=%{http_code} starttransfer=%{time_starttransfer} total=%{time_total}\n" \
    "$PROXY_BASE$path"

  etag="$(
    awk -F': ' 'tolower($1)=="etag"{print $2}' "$RUN_DIR/${name}.headers" \
      | tr -d '\r' \
      | tail -1
  )"
  if [[ -n "$etag" ]]; then
    curl -sS \
      -D "$RUN_DIR/${name}-304.headers" \
      -o /dev/null \
      -H "If-None-Match: $etag" \
      "$PROXY_BASE$path"
    status="$(awk 'NR==1{print $2}' "$RUN_DIR/${name}-304.headers")"
    if [[ "$status" != "304" ]]; then
      printf 'Expected 304 for %s, got %s\n' "$path" "$status" >&2
      exit 1
    fi
  fi
done

curl -fsS "$PROXY_BASE/api/lite/revisions" \
  | tee "$RUN_DIR/revisions.json" \
  | python3 -m json.tool

if [[ ! -s "$RUN_DIR/revisions.json" ]]; then
  printf 'Missing or empty revisions response: %s\n' "$RUN_DIR/revisions.json" >&2
  exit 1
fi
python3 -m json.tool "$RUN_DIR/revisions.json" >/dev/null
