---
title: "Restore preview and confirmed restore"
description: "Builds a non-destructive preview, requires explicit confirmation, creates a checkpoint, applies restore, and validates health."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 70e1e3dd1be588ab4eada0a05875282ebd5daa117f0b647e4f50d7977fccef16
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Restore preview and confirmed restore

Builds a non-destructive preview, requires explicit confirmation, creates a checkpoint, applies restore, and validates health.

![Restore preview and confirmed restore mini architecture](../../../../assets/diagrams/production/components/restore-preview.light.svg#only-light)
![Restore preview and confirmed restore mini architecture](../../../../assets/diagrams/production/components/restore-preview.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Recovery worker |
| Started / runtime owner | pocket-worker |
| Process owner | restore services |
| Execution owner | Recovery execution |
| Data owner | Recovery operations and backup repository |
| Recovery owner | Checkpoint rollback |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Backup selection
- confirmation

## Outputs

- preview
- restore result

## Protocols

- NATS
- SQLite
- filesystem

## Durable state

- recovery_operations

## Health and readiness

- post-restore API health

## Evidence

- preview and restore receipt

## Failure behavior

- preview unsafe
- health failed

## Recovery behavior

- checkpoint rollback

## Connections

### Incoming

- Backup and verification engine — verified backup input

### Outgoing

- updates restore state — Backup, restore, and checkpoint state
- creates checkpoint before apply — Checkpoints and retention policy

## Source verification

- `route` — `POST /api/lite/recovery/restore/preview`
- `route` — `POST /api/lite/recovery/restore`
- `contract` — `contracts/generated/recovery-contract.json`

## Existing documentation

- [recovery.md](../../recovery.md)

## Related architecture views

- [Backup and restore](../backup-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
