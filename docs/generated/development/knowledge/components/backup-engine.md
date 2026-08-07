---
title: "Backup and verification engine"
description: "Creates and verifies local encrypted backups through backend/worker-owned operations."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Backup and verification engine

Creates and verifies local encrypted backups through backend/worker-owned operations.

## Why it exists

Creates and verifies local encrypted backups through backend/worker-owned operations.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:backup-engine` |
| Owner | Recovery execution |
| Execution owner | backup services |
| Data owner | Backup repository and manifest index |
| Recovery owner | Recovery worker |
| Runtime owner | pocket-worker |
| Runtime process | backup services |
| Runtime platform | Recovery worker |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Creates and verifies local encrypted backups through backend/worker-owned operations.

## Inputs

- Backup command

## Outputs

- verified backup manifest

## Health signals

- repository readiness
- verification status

## Failure modes

- repository unavailable
- verification failed

## Recovery behavior

- retry
- repair repository

## Evidence

- backup receipt

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Completion and audit evidence`
- depends_on: `Backup, restore, and checkpoint state`
- depends_on: `Restore preview and confirmed restore`
- depends_on: `backup_manifest_index`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- publishes: `pocketlab.events.lite.backup.snapshot_created`
- publishes: `pocketlab.events.lite.backup.started`
- publishes: `pocketlab.events.lite.restore.checkpoint_created`
- publishes: `pocketlab.events.lite.restore.completed`
- publishes: `pocketlab.events.lite.restore.health_validated`
- publishes: `pocketlab.events.lite.restore.service_restart_checked`
- publishes: `pocketlab.events.lite.restore.started`
- recovers_with: `Backup failure`
- related_to: `pocketlab.commands.lite.backup.create`
- uses: `POST /api/lite/recovery/backup`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Worker process`
- uses: `Backup creation and verification`
- uses: `Confirmed restore`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/backup-engine.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_backup.py`
