---
title: "Worker process"
description: "Consumes durable commands and owns backend execution for apps, security, recovery, releases, and lifecycle work."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Worker process

Consumes durable commands and owns backend execution for apps, security, recovery, releases, and lifecycle work.

## Why it exists

Consumes durable commands and owns backend execution for apps, security, recovery, releases, and lifecycle work.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:worker` |
| Owner | Execution plane |
| Execution owner | pocket-worker |
| Data owner | Domain state via services |
| Recovery owner | Durable-consumer watchdog / PM2 |
| Runtime owner | PM2 |
| Runtime process | pocket-worker |
| Runtime platform | Server host |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Consumes durable commands and owns backend execution for apps, security, recovery, releases, and lifecycle work.

## Inputs

- JetStream commands

## Outputs

- Domain state
- events
- evidence

## Health signals

- worker heartbeat
- durable consumer health

## Failure modes

- consumer stale
- subprocess timeout

## Recovery behavior

- consumer re-enrollment
- bounded retry

## Evidence

- command received/running/terminal

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `App lifecycle worker`
- depends_on: `Backup and verification engine`
- depends_on: `Command admission and lifecycle`
- depends_on: `Release subprocess`
- depends_on: `Security scan coordinator`
- depends_on: `Workflow execution`
- depends_on: `command_lifecycle`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- publishes: `pocketlab.commands`
- publishes: `pocketlab.commands.lite.security.scan`
- publishes: `pocketlab.commands.node`
- publishes: `pocketlab.commands.operation.execute`
- publishes: `pocketlab.commands.runbook.approve`
- publishes: `pocketlab.commands.runbook.execute`
- publishes: `pocketlab.commands.runbook.reject`
- publishes: `pocketlab.events.command.deferred`
- publishes: `pocketlab.events.command.failed`
- publishes: `pocketlab.events.command.received`
- publishes: `pocketlab.events.command.retry_scheduled`
- publishes: `pocketlab.events.command.running`
- publishes: `pocketlab.events.command.succeeded`
- publishes: `pocketlab.events.command.worker_claimed`
- publishes: `pocketlab.events.operation.failed`
- publishes: `pocketlab.events.operation.worker_claimed`
- publishes: `pocketlab.events.release.available`
- publishes: `pocketlab.events.release.check_degraded`
- publishes: `pocketlab.events.release.current`
- publishes: `pocketlab.events.worker.error`
- publishes: `pocketlab.events.worker.heartbeat`
- publishes: `pocketlab.events.worker.ignored`
- publishes: `pocketlab.events.worker.maintenance_deferred`
- publishes: `pocketlab.events.worker.started`
- publishes: `pocketlab.events.worker.stopped`
- recovers_with: `Backup failure`
- recovers_with: `NATS or JetStream unavailable`
- recovers_with: `Security scan failure`
- recovers_with: `Worker stopped`
- related_to: `pocketlab.events.operation.succeeded`
- verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`
- verified_by: `tests/backend/test_lite_projection_semantic_hardening.py`
- verified_by: `tests/backend/test_lite_security_s8_recovery.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/backend/test_lite_worker_recovery.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `NATS / JetStream`
- uses: `Backup creation and verification`
- uses: `Security scan`
- uses: `Pocket Lab Lite startup`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/worker.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/workers/pocketlab_worker.py`
