---
title: "Explicit retirement and database recovery"
description: "Requires assessment and confirmation for device retirement and provides verified database backup/preview/restore without coupling command cleanup to device deletion."
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

# Explicit retirement and database recovery

Requires assessment and confirmation for device retirement and provides verified database backup/preview/restore without coupling command cleanup to device deletion.

![Explicit retirement and database recovery mini architecture](../../../../assets/diagrams/production/components/retirement-database-recovery.light.svg#only-light)
![Explicit retirement and database recovery mini architecture](../../../../assets/diagrams/production/components/retirement-database-recovery.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | FastAPI / worker |
| Started / runtime owner | pocket-api / pocket-worker |
| Process owner | domain services |
| Execution owner | Fleet and Recovery |
| Data owner | SQLite |
| Recovery owner | Explicit repair/rejoin or database restore |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Confirmed retirement/restore

## Outputs

- retirement receipt
- database restore

## Protocols

- HTTP JSON
- NATS
- SQLite

## Durable state

- device_removal_receipts
- security_database_backups

## Health and readiness

- dependency assessment
- database verification

## Evidence

- retirement/restore evidence

## Failure behavior

- healthy device removal blocked
- restore verification failed

## Recovery behavior

- cancel
- use verified backup

## Connections

### Incoming

- Checkpoints and retention policy — provides recovery point

### Outgoing

- verified backup/restore — SQLite control-plane store

## Source verification

- `route` — `GET /api/lite/devices/{device_id}/removal-assessment`
- `route` — `POST /api/lite/fleet/remove-device`
- `route` — `POST /api/lite/recovery/database/backup`
- `route` — `POST /api/lite/recovery/database/backups/{backup_id}/restore`

## Existing documentation

- [devices.md](../../devices.md)
- [recovery.md](../../recovery.md)

## Related architecture views

- [Backup and restore](../backup-recovery.md)
- [Devices and offline recovery](../device-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
