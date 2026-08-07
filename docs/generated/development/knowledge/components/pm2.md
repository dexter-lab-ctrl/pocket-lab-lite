---
title: "PM2 process manager"
description: "Starts and supervises approved server-host and joined-device processes with bounded restart policies."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# PM2 process manager

Starts and supervises approved server-host and joined-device processes with bounded restart policies.

## Why it exists

Starts and supervises approved server-host and joined-device processes with bounded restart policies.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:pm2` |
| Owner | Runtime process management |
| Execution owner | PM2 daemon |
| Data owner | None |
| Recovery owner | PM2 plus supervisors |
| Runtime owner | PM2 |
| Runtime process | PM2 daemon |
| Runtime platform | Server host and joined devices |
| Security boundary | server-host |
| Confidence | verified |

## Responsibilities

- Starts and supervises approved server-host and joined-device processes with bounded restart policies.

## Inputs

- Generated process definitions

## Outputs

- Managed processes
- status

## Health signals

- pm2 status

## Failure modes

- process stopped

## Recovery behavior

- bounded restart
- separate supervisor

## Evidence

- process status/restart count

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Lite agent supervisor`
- depends_on: `Lite node agent`
- depends_on: `PROot Ubuntu application container`
- protected_by: `Server-host boundary`
- protected_by: `Server-host boundary`
- recovers_with: `Supervisor stopped`
- recovers_with: `Worker stopped`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_device_system_profile.py`
- verified_by: `tests/backend/test_lite_security_s6_frontend_contract.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- uses: `Pocket Lab Lite startup`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/pm2.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh`
