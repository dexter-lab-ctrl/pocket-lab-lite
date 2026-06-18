# Phase 10: NATS-backed Fleet Agent

Phase 10 makes Fleet Scaling real across multiple devices by adding a lightweight node agent and a control-plane registry that consumes live NATS fleet events.

## Runtime pieces

- `runtime/agents/pocketlab_node_agent.py` runs on each device.
- `runtime/api_fastapi/services/fleet_registry.py` persists agent state in `$POCKETLAB_STATE_DIR/fleet_agents.json` and command history in `$POCKETLAB_STATE_DIR/fleet_agent_commands.json`.
- `runtime/api_fastapi/routers/fleet.py` exposes agent, command, bootstrap, and health APIs.
- `runtime/api_fastapi/services/nats_bus.py` records `pocketlab.events.fleet.node_*` events into the fleet registry.

## Subjects

Agents publish:

- `pocketlab.events.fleet.node_seen`
- `pocketlab.events.fleet.node_heartbeat`
- `pocketlab.events.fleet.node_telemetry`
- `pocketlab.events.fleet.node_health`
- `pocketlab.events.fleet.node_command_result`
- `pocketlab.events.fleet.node_left`

Control-plane commands are sent to:

- `pocketlab.commands.node.<node_id>.>`
- `pocketlab.commands.node.all.>`

The generic worker deliberately ignores `pocketlab.commands.node.*` so node agents own device-scoped commands.

## APIs

- `GET /api/fleet/agents`
- `GET /api/fleet/agents/{node_id}`
- `GET /api/fleet/agents/{node_id}/commands`
- `POST /api/fleet/agents/{node_id}/commands`
- `POST /api/fleet/agents/broadcast`
- `GET /api/fleet/agent/bootstrap`
- `GET /api/fleet/health.json`

## Node agent environment

```bash
export POCKETLAB_NATS_URL=nats://127.0.0.1:4222
export POCKETLAB_NODE_ID=pixel-edge-01
export POCKETLAB_NODE_NAME=pixel-edge-01
export POCKETLAB_NODE_ROLE=compute
export POCKETLAB_AGENT_TOKEN=<enrollment-token>
python3 runtime/agents/pocketlab_node_agent.py
```

## Bootstrap

- `scripts/install-fleet-agent.sh` installs and optionally starts the agent through PM2.
- `scripts/start-dashboard.sh` starts the control-plane agent as `pocket-node-agent` unless `POCKETLAB_DISABLE_FLEET_AGENT=1`.

## Simple Mode behavior

Simple Mode shows live devices as “My Devices” and translates agent events into plain device check-in messages. Professional Mode exposes node IDs, agent versions, telemetry, command subjects, and command result payloads.
