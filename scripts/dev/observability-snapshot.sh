#!/usr/bin/env bash
set -Eeuo pipefail
api="${POCKETLAB_API_URL:-http://127.0.0.1:8000}"; out=".pocketlab-dev/observability"; mkdir -p "$out"
for ep in ready api/nats/status api/workers/status api/events/status api/workflows/status api/reliability/status api/telemetry.json api/health-engine.json; do safe="${ep//\//_}"; curl -fsS "$api/$ep" > "$out/$safe.json" 2>/dev/null || true; done
cp .pocketlab-dev/logs/*.log "$out/" 2>/dev/null || true
cat > "$out/index.html" <<HTML
<!doctype html><html><head><meta charset="utf-8"><title>Pocket Lab Dev Observability</title><style>body{font-family:system-ui;margin:2rem;background:#0b1220;color:#e5edf8}a{color:#7dd3fc}li{margin:.4rem 0}</style></head><body><h1>Pocket Lab Dev Observability Snapshot</h1><p>Generated: $(date)</p><ul>$(find "$out" -maxdepth 1 -type f \( -name '*.json' -o -name '*.log' \) -printf '<li><a href="%f">%f</a></li>\n' | sort)</ul></body></html>
HTML
echo "Wrote $out/index.html"
