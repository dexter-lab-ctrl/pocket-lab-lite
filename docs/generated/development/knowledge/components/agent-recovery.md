---
title: "Reconnect watchdog and supervisor recovery"
description: "Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Reconnect watchdog and supervisor recovery

Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available.

## Why it exists

Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:agent-recovery` |
| Owner | Device recovery |
| Execution owner | separate processes |
| Data owner | Server lifecycle state |
| Recovery owner | agent/supervisor |
| Runtime owner | agent and supervisor |
| Runtime process | separate processes |
| Runtime platform | Joined device |
| Security boundary | managed-device |
| Confidence | verified |

## Responsibilities

- Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available.

## Inputs

- connection state
- PM2 state

## Outputs

- reconnect
- restart
- recovery evidence

## Health signals

- agent connection
- supervisor status

## Failure modes

- disconnected
- stopped

## Recovery behavior

- reconnect watchdog
- supervisor restart
- guidance

## Evidence

- recovery transitions

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Agents and supervisors own device execution and recovery`
- depends_on: `Lite node agent`
- depends_on: `device_recovery_history`
- protected_by: `Managed-device boundary`
- protected_by: `Managed-device boundary`
- publishes: `pocketlab.events.fleet.node_capabilities`
- publishes: `pocketlab.events.fleet.node_command_result`
- publishes: `pocketlab.events.fleet.node_health`
- publishes: `pocketlab.events.fleet.node_heartbeat`
- publishes: `pocketlab.events.fleet.node_left`
- publishes: `pocketlab.events.fleet.node_profile`
- publishes: `pocketlab.events.fleet.node_seen`
- publishes: `pocketlab.events.fleet.node_supervisor`
- publishes: `pocketlab.events.fleet.node_telemetry`
- recovers_with: `Node agent stopped`
- recovers_with: `Device joining, waiting, or repairing`
- recovers_with: `Device offline or reconnecting`
- related_to: `pocketlab.commands.node.all`
- related_to: `pocketlab.commands.node.{self.node_id}`
- verified_by: `tests/backend/test_lite_device_system_profile.py`
- verified_by: `tests/backend/test_lite_devices_durable_enrollment.py`
- verified_by: `tests/backend/test_lite_devices_production_readiness.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Lite agent supervisor`
- depends_on: `Lite node agent`
- uses: `Device offline and reconnect recovery`
- uses: `Restart Agent`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/agent-recovery.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py`
- `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`
