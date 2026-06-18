#!/usr/bin/env bash
set -Eeuo pipefail
api="${POCKETLAB_API_URL:-http://127.0.0.1:8000}"
operation="${1:-catalog_refresh}"
correlation_id="dev-$(date +%Y%m%d%H%M%S)-$RANDOM"
payload=$(jq -n --arg op "$operation" --arg cid "$correlation_id" '{operation:$op,target:{source:"dev-trace"},params:{correlation_id:$cid},correlation_id:$cid}')
echo "Correlation ID: $correlation_id"
echo "Submitting operation: $operation"
curl -fsS -H "Content-Type: application/json" -H "X-PocketLab-Request-ID: $correlation_id" -d "$payload" "$api/api/operations/execute" | tee ".pocketlab-dev/trace-$correlation_id.json"
echo
echo "Trace files: .pocketlab-dev/trace-$correlation_id.json"
echo "Search logs: grep -R '$correlation_id' .pocketlab-dev/logs pocket-lab-final-structure 2>/dev/null || true"
