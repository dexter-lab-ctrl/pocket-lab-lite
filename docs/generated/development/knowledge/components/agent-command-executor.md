---
title: "Device command executor"
description: "Executes approved device commands in the node agent and publishes truthful results."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Device command executor

Executes approved device commands in the node agent and publishes truthful results.

## Why it exists

Executes approved device commands in the node agent and publishes truthful results.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:agent-command-executor` |
| Owner | Device execution |
| Execution owner | node agent |
| Data owner | Command lifecycle in server SQLite |
| Recovery owner | Command reconciliation |
| Runtime owner | node agent |
| Runtime process | node agent |
| Runtime platform | Node agent |
| Security boundary | managed-device |
| Confidence | verified |

## Responsibilities

- Executes approved device commands in the node agent and publishes truthful results.

## Inputs

- Validated NATS command

## Outputs

- command result
- fresh heartbeat

## Health signals

- command progress

## Failure modes

- undeliverable
- agent disconnected

## Recovery behavior

- do not fake delivery
- retry after reconnect

## Evidence

- device command result

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Agents and supervisors own device execution and recovery`
- depends_on: `Completion and audit evidence`
- depends_on: `Lite node agent`
- depends_on: `command_lifecycle`
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
- related_to: `pocketlab.commands.lite.device.restart`
- related_to: `pocketlab.commands.node.all`
- related_to: `pocketlab.commands.node.{self.node_id}`
- verified_by: `tests/backend/test_lite_device_system_profile.py`
- verified_by: `tests/backend/test_lite_devices_production_readiness.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `NATS / JetStream`
- uses: `Restart Agent`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/agent-command-executor.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`
