---
title: "Heartbeat, telemetry, and health publishers"
description: "Publish fresh runtime signals used to derive Online, Offline, Stale, Agent stopped, and Remote access not ready states."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Heartbeat, telemetry, and health publishers

Publish fresh runtime signals used to derive Online, Offline, Stale, Agent stopped, and Remote access not ready states.

## Why it exists

Publish fresh runtime signals used to derive Online, Offline, Stale, Agent stopped, and Remote access not ready states.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:agent-signals` |
| Owner | Device runtime |
| Execution owner | node agent |
| Data owner | Server SQLite projections |
| Recovery owner | Reconnect watchdog |
| Runtime owner | node agent |
| Runtime process | node agent |
| Runtime platform | Node agent |
| Security boundary | managed-device |
| Confidence | verified |

## Responsibilities

- Publish fresh runtime signals used to derive Online, Offline, Stale, Agent stopped, and Remote access not ready states.

## Inputs

- Local runtime samples

## Outputs

- heartbeat
- telemetry
- health

## Health signals

- signal freshness

## Failure modes

- signal stale

## Recovery behavior

- fresh publish after reconnect

## Evidence

- device health events

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Enrollment and device lifecycle state`
- depends_on: `NATS / JetStream`
- depends_on: `device_health_current`
- depends_on: `device_heartbeats`
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
- recovers_with: `Device offline or reconnecting`
- related_to: `pocketlab.commands.node.all`
- related_to: `pocketlab.commands.node.{self.node_id}`
- related_to: `pocketlab.events.fleet.node_heartbeat`
- verified_by: `tests/backend/test_lite_device_system_profile.py`
- verified_by: `tests/backend/test_lite_devices_production_readiness.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Lite node agent`
- uses: `Device bootstrap and enrollment`
- uses: `Device offline and reconnect recovery`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/agent-signals.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`
