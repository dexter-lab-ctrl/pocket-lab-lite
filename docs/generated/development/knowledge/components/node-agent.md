---
title: "Lite node agent"
description: "Connects to NATS, publishes heartbeat/telemetry/health, handles device commands, and reconnects after outages."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Lite node agent

Connects to NATS, publishes heartbeat/telemetry/health, handles device commands, and reconnects after outages.

## Why it exists

Connects to NATS, publishes heartbeat/telemetry/health, handles device commands, and reconnects after outages.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:node-agent` |
| Owner | Device runtime |
| Execution owner | pocketlab-agent-<node_id> |
| Data owner | Local identity environment; server SQLite is canonical |
| Recovery owner | Reconnect watchdog and supervisor |
| Runtime owner | PM2 |
| Runtime process | pocketlab-agent-<node_id> |
| Runtime platform | Server host or joined device |
| Security boundary | managed-device |
| Confidence | verified |

## Responsibilities

- Connects to NATS, publishes heartbeat/telemetry/health, handles device commands, and reconnects after outages.

## Inputs

- NATS commands
- agent environment

## Outputs

- heartbeat
- telemetry
- health
- command result

## Health signals

- fresh heartbeat
- connection state

## Failure modes

- disconnected
- stopped
- identity mismatch

## Recovery behavior

- reconnect
- supervisor restart
- explicit repair/rejoin

## Evidence

- device lifecycle events

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Agents and supervisors own device execution and recovery`
- depends_on: `Reconnect watchdog and supervisor recovery`
- depends_on: `Heartbeat, telemetry, and health publishers`
- protected_by: `Managed-device boundary`
- protected_by: `Managed-device boundary`
- publishes: `pocketlab.events.fleet.node_capabilities`
- publishes: `pocketlab.events.fleet.node_command_result`
- publishes: `pocketlab.events.fleet.node_health`
- publishes: `pocketlab.events.fleet.node_heartbeat`
- publishes: `pocketlab.events.fleet.node_left`
- publishes: `pocketlab.events.fleet.node_profile`
- publishes: `pocketlab.events.fleet.node_seen`
- publishes: `pocketlab.events.fleet.node_telemetry`
- recovers_with: `Node agent stopped`
- recovers_with: `Supervisor stopped`
- related_to: `pocketlab.commands.node.all`
- related_to: `pocketlab.commands.node.{self.node_id}`
- verified_by: `tests/backend/test_lite_device_system_profile.py`
- verified_by: `tests/backend/test_lite_devices_production_readiness.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Device command executor`
- depends_on: `Reconnect watchdog and supervisor recovery`
- depends_on: `Identity, authentication, and invite guards`
- depends_on: `PM2 process manager`
- uses: `Add Device`
- uses: `Device bootstrap and enrollment`
- uses: `Device offline and reconnect recovery`
- uses: `Restart Agent`
- uses: `Sanitized Termux runtime capture`
- uses: `Pocket Lab Lite startup`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/node-agent.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`
