---
title: "App lifecycle worker"
description: "Owns install, repair, media import, backup, restore preview, update readiness/apply, and removal paths only where implemented and safe."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# App lifecycle worker

Owns install, repair, media import, backup, restore preview, update readiness/apply, and removal paths only where implemented and safe.

## Why it exists

Owns install, repair, media import, backup, restore preview, update readiness/apply, and removal paths only where implemented and safe.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:app-lifecycle-worker` |
| Owner | Apps execution |
| Execution owner | pocket-worker |
| Data owner | App lifecycle SQLite state |
| Recovery owner | Worker retry / repair |
| Runtime owner | PM2 |
| Runtime process | pocket-worker |
| Runtime platform | pocket-worker |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Owns install, repair, media import, backup, restore preview, update readiness/apply, and removal paths only where implemented and safe.

## Inputs

- App command

## Outputs

- App lifecycle state
- sanitized details

## Health signals

- action progress
- route health

## Failure modes

- operation failed

## Recovery behavior

- non-destructive repair
- explicit retry

## Evidence

- app action lifecycle

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `App backup, restore preview, and update lifecycle`
- depends_on: `App, command, and workflow state`
- depends_on: `Completion and audit evidence`
- depends_on: `Media readiness and app health probes`
- depends_on: `app_action_lifecycle`
- depends_on: `app_current_state`
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
- recovers_with: `App installation failure`
- related_to: `pocketlab.commands.lite.app.repair`
- related_to: `pocketlab.commands.lite.app.update.check`
- related_to: `pocketlab.events.operation.succeeded`
- verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`
- verified_by: `tests/backend/test_lite_projection_semantic_hardening.py`
- verified_by: `tests/backend/test_lite_security_s8_recovery.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/backend/test_lite_worker_recovery.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Worker process`
- uses: `App installation`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/app-lifecycle-worker.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/workers/pocketlab_worker.py`
