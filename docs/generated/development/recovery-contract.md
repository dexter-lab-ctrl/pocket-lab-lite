---
title: "Recovery contract"
description: "Authoritative source-derived Backup and Restore lifecycle and ownership contract."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: e90a1a018821f80a921cb0fac9ed0825af56a98d3b89528afea5e642d75d2908
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Recovery contract

| Lifecycle | Canonical states |
| --- | --- |
| Backup | queued, running, succeeded, degraded, failed |
| Verification | not_run, running, verified, failed |
| Restore Preview | not_ready, running, ready, blocked, failed |
| Checkpoint | not_created, creating, created, failed |
| Restore | queued, running, validating, succeeded, rolled_back, failed |
| Confirmation Required | restore_latest, destructive replacement |
| Endpoints | /api/lite/fleet/devices/{device_id}/recovery-history, /api/lite/identity/recovery/regenerate, /api/lite/recovery, /api/lite/recovery/apps, /api/lite/recovery/apps/{app_id}, /api/lite/recovery/apps/{app_id}/backup, /api/lite/recovery/apps/{app_id}/backup-targets, /api/lite/recovery/apps/{app_id}/backup-to-target, /api/lite/recovery/apps/{app_id}/restore, /api/lite/recovery/apps/{app_id}/restore/preview, /api/lite/recovery/backup, /api/lite/recovery/backup-targets, /api/lite/recovery/backups, /api/lite/recovery/backups/{backup_id}, /api/lite/recovery/backups/{backup_id}/verify, /api/lite/recovery/database, /api/lite/recovery/database/backup, /api/lite/recovery/database/backups, /api/lite/recovery/database/backups/{backup_id}, /api/lite/recovery/database/backups/{backup_id}/preview, /api/lite/recovery/database/backups/{backup_id}/restore, /api/lite/recovery/database/backups/{backup_id}/verify, /api/lite/recovery/database/restore/previews/{preview_id}, /api/lite/recovery/database/restore/{restore_id}, /api/lite/recovery/details, /api/lite/recovery/maintenance, /api/lite/recovery/maintenance/checkpoint, /api/lite/recovery/maintenance/retention, /api/lite/recovery/operations, /api/lite/recovery/receipts/{backup_id}, /api/lite/recovery/restore, /api/lite/recovery/restore/checkpoints/{checkpoint_id}, /api/lite/recovery/restore/preview, /api/lite/recovery/restore/previews/{preview_id}, /api/lite/recovery/restore/runs/{restore_id}, /api/lite/recovery/summary |
| Evidence | backup manifest, verification receipt, restore preview, checkpoint receipt, restore run, health result |

## Ownership

- API: FastAPI validates and admits requests.
- Execution: workers own backup, verification, checkpoint, restore, post-restore health, and rollback.
- Browser: display and confirmation only.
