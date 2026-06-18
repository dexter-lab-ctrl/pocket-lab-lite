#!/usr/bin/env bash
set -Eeuo pipefail
ANDROID_HOST="${ANDROID_HOST:-}"; ANDROID_USER="${ANDROID_USER:-darkwizard}"; ANDROID_PORT="${ANDROID_PORT:-8022}"; ANDROID_REPO="${ANDROID_REPO:-~/pocket-lab}"
[[ -n "$ANDROID_HOST" ]] || { echo "Set ANDROID_HOST" >&2; exit 2; }
target="$ANDROID_USER@$ANDROID_HOST"
ssh -p "$ANDROID_PORT" "$target" "set -e
  cd '$ANDROID_REPO'
  git status --short || true
  bash pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/bootstrap.sh --dry-run
  bash pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/smoke-test.sh || true
  command -v pm2 >/dev/null 2>&1 && pm2 status || true
  curl -fsS http://127.0.0.1:8000/ready || true
  curl -fsS http://127.0.0.1:8000/api/nats/status || true
"
