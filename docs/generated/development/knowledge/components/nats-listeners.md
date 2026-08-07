---
title: "Primary and secondary NATS listeners"
description: "Exposes local and verified Tailnet-reachable NATS listeners for agents without hardcoding credentials or addresses."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Primary and secondary NATS listeners

Exposes local and verified Tailnet-reachable NATS listeners for agents without hardcoding credentials or addresses.

## Why it exists

Exposes local and verified Tailnet-reachable NATS listeners for agents without hardcoding credentials or addresses.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:nats-listeners` |
| Owner | NATS runtime |
| Execution owner | NATS server |
| Data owner | NATS configuration |
| Recovery owner | startup scripts |
| Runtime owner | pocket-nats |
| Runtime process | NATS server |
| Runtime platform | Server host |
| Security boundary | server-host |
| Confidence | verified |

## Responsibilities

- Exposes local and verified Tailnet-reachable NATS listeners for agents without hardcoding credentials or addresses.

## Inputs

- Generated listener config

## Outputs

- Primary and secondary agent connectivity

## Health signals

- local listener
- Tailnet listener reachability

## Failure modes

- listener bound incorrectly

## Recovery behavior

- regenerate config
- verify connectivity

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `NATS / JetStream`
- depends_on: `Remote-access readiness checks`
- protected_by: `Server-host boundary`
- protected_by: `Server-host boundary`
- recovers_with: `NATS or JetStream unavailable`
- recovers_with: `Remote access not ready`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_device_system_profile.py`
- verified_by: `tests/backend/test_lite_security_s6_frontend_contract.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Tailscale remote access`
- uses: `Tailscale and remote access readiness`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/nats-listeners.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh`
