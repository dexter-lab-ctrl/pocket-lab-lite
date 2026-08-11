---
title: "Restore preview and confirmed restore"
description: "Builds a non-destructive preview, requires explicit confirmation, creates a checkpoint, applies restore, and validates health."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Restore preview and confirmed restore

Builds a non-destructive preview, requires explicit confirmation, creates a checkpoint, applies restore, and validates health.

## Why it exists

Builds a non-destructive preview, requires explicit confirmation, creates a checkpoint, applies restore, and validates health.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:restore-preview` |
| Owner | Recovery execution |
| Execution owner | restore services |
| Data owner | Recovery operations and backup repository |
| Recovery owner | Checkpoint rollback |
| Runtime owner | pocket-worker |
| Runtime process | restore services |
| Runtime platform | Recovery worker |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Builds a non-destructive preview, requires explicit confirmation, creates a checkpoint, applies restore, and validates health.

## Inputs

- Backup selection
- confirmation

## Outputs

- preview
- restore result

## Health signals

- post-restore API health

## Failure modes

- preview unsafe
- health failed

## Recovery behavior

- checkpoint rollback

## Evidence

- preview and restore receipt

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Checkpoints and retention policy`
- depends_on: `Backup, restore, and checkpoint state`
- depends_on: `recovery_operations`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- recovers_with: `Recovery projection stale`
- recovers_with: `Restore blocked or preview stale`
- uses: `POST /api/lite/recovery/restore`
- uses: `POST /api/lite/recovery/restore/preview`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Backup and verification engine`
- uses: `Confirmed restore`
- uses: `Restore preview`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/restore-preview.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
