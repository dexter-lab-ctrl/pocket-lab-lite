---
title: "App backup, restore preview, and update lifecycle"
description: "Coordinates app backup, safe restore preview, update readiness/apply, verification, and rollback gates without browser-owned execution."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# App backup, restore preview, and update lifecycle

Coordinates app backup, safe restore preview, update readiness/apply, verification, and rollback gates without browser-owned execution.

## Why it exists

Coordinates app backup, safe restore preview, update readiness/apply, verification, and rollback gates without browser-owned execution.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:app-recovery-update` |
| Owner | Apps and Recovery |
| Execution owner | app/recovery services |
| Data owner | SQLite and backup manifests |
| Recovery owner | Checkpoint / rollback |
| Runtime owner | pocket-worker |
| Runtime process | app/recovery services |
| Runtime platform | Worker / release subprocess |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Coordinates app backup, safe restore preview, update readiness/apply, verification, and rollback gates without browser-owned execution.

## Inputs

- Confirmed action

## Outputs

- backup
- preview
- verified update result

## Health signals

- backup verified
- rollback ready

## Failure modes

- verification blocked

## Recovery behavior

- preview first
- rollback

## Evidence

- app backup/update receipts

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Backup, restore, and checkpoint state`
- depends_on: `app_action_lifecycle`
- depends_on: `backup_manifest_index`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- uses: `POST /api/lite/apps/{app_id}/backup`
- uses: `POST /api/lite/apps/{app_id}/restore/preview`
- uses: `POST /api/lite/apps/{app_id}/update/apply`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `App lifecycle worker`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/app-recovery-update.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
