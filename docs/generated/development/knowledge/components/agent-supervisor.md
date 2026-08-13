---
title: "Lite agent supervisor"
description: "Runs separately from the agent, reads the protected agent environment, and starts or restarts failed agents without overwriting identity."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Lite agent supervisor

Runs separately from the agent, reads the protected agent environment, and starts or restarts failed agents without overwriting identity.

## Why it exists

Runs separately from the agent, reads the protected agent environment, and starts or restarts failed agents without overwriting identity.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:agent-supervisor` |
| Owner | Device recovery |
| Execution owner | pocketlab-agent-supervisor-<node_id> |
| Data owner | No canonical state |
| Recovery owner | Self / PM2 |
| Runtime owner | PM2 |
| Runtime process | pocketlab-agent-supervisor-<node_id> |
| Runtime platform | Joined device |
| Security boundary | managed-device |
| Confidence | verified |

## Responsibilities

- Runs separately from the agent, reads the protected agent environment, and starts or restarts failed agents without overwriting identity.

## Inputs

- PM2 agent status
- protected environment

## Outputs

- agent restart
- sanitized recovery evidence

## Health signals

- supervisor status

## Failure modes

- supervisor absent

## Recovery behavior

- UI recovery guidance
- explicit repair

## Evidence

- supervisor recovery

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Agents and supervisors own device execution and recovery`
- depends_on: `Reconnect watchdog and supervisor recovery`
- protected_by: `Managed-device boundary`
- protected_by: `Managed-device boundary`
- publishes: `pocketlab.events.fleet.node_supervisor`
- recovers_with: `Node agent stopped`
- recovers_with: `Supervisor stopped`
- verified_by: `tests/backend/test_lite_devices_durable_enrollment.py`
- verified_by: `tests/backend/test_lite_devices_production_readiness.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

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

- [Production architecture component page](../../../production/architecture/components/agent-supervisor.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py`
