#!/usr/bin/env bash
set -Eeuo pipefail
url="${1:?usage: wait-http.sh URL [timeout_seconds]}"
timeout="${2:-30}"
deadline=$((SECONDS + timeout))
until curl -fsS "$url" >/dev/null 2>&1; do
  (( SECONDS < deadline )) || { echo "Timed out waiting for $url" >&2; exit 1; }
  sleep 1
done
echo "OK: $url"
