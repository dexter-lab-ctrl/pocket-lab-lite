#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
AGENT_SRC="$SCRIPT_DIR/../../runtime/agents/pocketlab_node_agent.py"
AGENT_DST="${POCKETLAB_AGENT_PATH:-$HOME/.local/bin/pocketlab-node-agent}"
NODE_ID="${POCKETLAB_NODE_ID:-$(hostname 2>/dev/null || echo pocket-node)}"
NODE_ROLE="${POCKETLAB_NODE_ROLE:-compute}"
NATS_URL="${POCKETLAB_NATS_URL:-nats://127.0.0.1:4222}"
NATS_USER="${POCKETLAB_NATS_USER:-${POCKETLAB_NATS_AGENT_USER:-pocketlab_agent}}"
NATS_PASSWORD="${POCKETLAB_NATS_PASSWORD:-${POCKETLAB_NATS_AGENT_PASSWORD:-}}"
main(){
  SCRIPT_NAME="install-fleet-agent.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_termux; require_cmd python3
  [[ -f "$AGENT_SRC" ]] || die "Missing fleet agent source: $AGENT_SRC"
  python3 - <<'PYCHECK' || python3 -m pip install --user 'nats-py>=2.7.2'
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec('nats') else 1)
PYCHECK
  mkdir -p "$(dirname "$AGENT_DST")"
  cp "$AGENT_SRC" "$AGENT_DST"
  chmod +x "$AGENT_DST"
  cat <<EOF | atomic_write "$STATE_DIR/fleet-agent.env" 0600
export POCKETLAB_NODE_ID="$NODE_ID"
export POCKETLAB_NODE_NAME="${POCKETLAB_NODE_NAME:-$NODE_ID}"
export POCKETLAB_NODE_ROLE="$NODE_ROLE"
export POCKETLAB_NATS_URL="$NATS_URL"
export POCKETLAB_NATS_USER="$NATS_USER"
export POCKETLAB_NATS_PASSWORD="$NATS_PASSWORD"
export POCKETLAB_AGENT_TOKEN="${POCKETLAB_AGENT_TOKEN:-}"
export POCKETLAB_AGENT_HEARTBEAT_SECONDS="${POCKETLAB_AGENT_HEARTBEAT_SECONDS:-15}"
export POCKETLAB_AGENT_TELEMETRY_SECONDS="${POCKETLAB_AGENT_TELEMETRY_SECONDS:-20}"
EOF
  if have pm2 && [[ "${POCKETLAB_START_AGENT:-1}" == "1" ]]; then
    pm2_start_or_restart pocket-node-agent bash -- -lc "source '$STATE_DIR/fleet-agent.env'; exec '$AGENT_DST'"
    pm2 save >/dev/null || true
  fi
  mark_done fleet_agent_installed
  log INFO "Pocket Lab NATS-backed fleet agent installed at $AGENT_DST"
}
main "$@"
