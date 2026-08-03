---
title: "App backup, restore preview, and update lifecycle"
description: "Coordinates app backup, safe restore preview, update readiness/apply, verification, and rollback gates without browser-owned execution."
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

# App backup, restore preview, and update lifecycle

Coordinates app backup, safe restore preview, update readiness/apply, verification, and rollback gates without browser-owned execution.

![App backup, restore preview, and update lifecycle mini architecture](../../../../assets/diagrams/production/components/app-recovery-update.light.svg#only-light)
![App backup, restore preview, and update lifecycle mini architecture](../../../../assets/diagrams/production/components/app-recovery-update.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Worker / release subprocess |
| Started / runtime owner | pocket-worker |
| Process owner | app/recovery services |
| Execution owner | Apps and Recovery |
| Data owner | SQLite and backup manifests |
| Recovery owner | Checkpoint / rollback |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Confirmed action

## Outputs

- backup
- preview
- verified update result

## Protocols

- NATS
- SQLite

## Durable state

- backup_manifest_index
- app_action_lifecycle

## Health and readiness

- backup verified
- rollback ready

## Evidence

- app backup/update receipts

## Failure behavior

- verification blocked

## Recovery behavior

- preview first
- rollback

## Connections

### Incoming

- App lifecycle worker — runs backup/update paths

### Outgoing

- stores manifests/operations — Backup, restore, and checkpoint state

## Source verification

- `route` — `POST /api/lite/apps/{app_id}/backup`
- `route` — `POST /api/lite/apps/{app_id}/restore/preview`
- `route` — `POST /api/lite/apps/{app_id}/update/apply`

## Existing documentation

- [apps.md](../../apps.md)
- [recovery.md](../../recovery.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
