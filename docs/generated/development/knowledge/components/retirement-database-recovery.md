---
title: "Explicit retirement and database recovery"
description: "Requires assessment and confirmation for device retirement and provides verified database backup/preview/restore without coupling command cleanup to device deletion."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Explicit retirement and database recovery

Requires assessment and confirmation for device retirement and provides verified database backup/preview/restore without coupling command cleanup to device deletion.

## Why it exists

Requires assessment and confirmation for device retirement and provides verified database backup/preview/restore without coupling command cleanup to device deletion.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:retirement-database-recovery` |
| Owner | Fleet and Recovery |
| Execution owner | domain services |
| Data owner | SQLite |
| Recovery owner | Explicit repair/rejoin or database restore |
| Runtime owner | pocket-api / pocket-worker |
| Runtime process | domain services |
| Runtime platform | FastAPI / worker |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Requires assessment and confirmation for device retirement and provides verified database backup/preview/restore without coupling command cleanup to device deletion.

## Inputs

- Confirmed retirement/restore

## Outputs

- retirement receipt
- database restore

## Health signals

- dependency assessment
- database verification

## Failure modes

- healthy device removal blocked
- restore verification failed

## Recovery behavior

- cancel
- use verified backup

## Evidence

- retirement/restore evidence

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `SQLite control-plane store`
- depends_on: `device_removal_receipts`
- depends_on: `security_database_backups`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- uses: `GET /api/lite/devices/{device_id}/removal-assessment`
- uses: `POST /api/lite/fleet/remove-device`
- uses: `POST /api/lite/recovery/database/backup`
- uses: `POST /api/lite/recovery/database/backups/{backup_id}/restore`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Checkpoints and retention policy`
- uses: `Remove Old Device`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/retirement-database-recovery.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
