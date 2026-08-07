---
title: "Backup, restore, and checkpoint state"
description: "Stores backup manifests, recovery operations, current state, database backups/restores, and restore checkpoints."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Backup, restore, and checkpoint state

Stores backup manifests, recovery operations, current state, database backups/restores, and restore checkpoints.

## Why it exists

Stores backup manifests, recovery operations, current state, database backups/restores, and restore checkpoints.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:recovery-state` |
| Owner | Recovery domain |
| Execution owner | recovery services |
| Data owner | SQLite / backup repository |
| Recovery owner | Recovery worker |
| Runtime owner | Recovery worker |
| Runtime process | recovery services |
| Runtime platform | SQLite and repository-owned manifests |
| Security boundary | durable-state |
| Confidence | verified |

## Responsibilities

- Stores backup manifests, recovery operations, current state, database backups/restores, and restore checkpoints.

## Inputs

- backup/verify/preview/restore lifecycle

## Outputs

- recovery projection

## Health signals

- repository readiness
- verification state

## Failure modes

- verification failed
- restore blocked

## Recovery behavior

- checkpoint
- preview
- explicit confirmation

## Evidence

- backup and restore receipts

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `SQLite control-plane store`
- depends_on: `backup_manifest_index`
- depends_on: `recovery_operations`
- protected_by: `Durable-state boundary`
- protected_by: `Durable-state boundary`
- recovers_with: `Backup failure`
- recovers_with: `Recovery projection stale`
- recovers_with: `Restore blocked or preview stale`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `App backup, restore preview, and update lifecycle`
- depends_on: `Backup and verification engine`
- depends_on: `Restore preview and confirmed restore`
- uses: `Backup creation and verification`
- uses: `Recovery reconciliation`
- uses: `Confirmed restore`
- uses: `Restore preview`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/recovery-state.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
