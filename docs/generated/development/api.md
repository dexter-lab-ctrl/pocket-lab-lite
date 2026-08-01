---
title: "HTTP API inventory"
description: "FastAPI OpenAPI is the canonical browser/backend contract. Redocly validates the generated Lite-only view."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 9c85652565724d5d11b3040bd5fba4bf44d565f5e4593ba7967518e620081b6b
schema_revision: 1
validation_status: generated
---

# HTTP API inventory

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

FastAPI OpenAPI is the canonical browser/backend contract. Redocly validates the generated Lite-only view.

## Lite paths (116)

- `/api/lite/apps/lifecycle`
- `/api/lite/apps/lifecycle/{app_id}`
- `/api/lite/apps/photoprism/storage-mappings`
- `/api/lite/apps/photoprism/storage-mappings/{mapping_id}`
- `/api/lite/apps/photoprism/storage-preview`
- `/api/lite/apps/{app_id}/action-history`
- `/api/lite/apps/{app_id}/actions`
- `/api/lite/apps/{app_id}/actions/{action_id}`
- `/api/lite/apps/{app_id}/backup`
- `/api/lite/apps/{app_id}/backup/storage-device`
- `/api/lite/apps/{app_id}/backups`
- `/api/lite/apps/{app_id}/backups/{backup_id}/receipt`
- `/api/lite/apps/{app_id}/evidence`
- `/api/lite/apps/{app_id}/restore/preview`
- `/api/lite/apps/{app_id}/restore/previews/{preview_id}`
- `/api/lite/apps/{app_id}/update`
- `/api/lite/apps/{app_id}/update/apply`
- `/api/lite/apps/{app_id}/update/receipts/{operation_id}`
- `/api/lite/catalog`
- `/api/lite/catalog/install`
- `/api/lite/catalog/remove`
- `/api/lite/commands/history`
- `/api/lite/devices/{device_id}`
- `/api/lite/devices/{device_id}/health`
- `/api/lite/devices/{device_id}/health/history`
- `/api/lite/devices/{device_id}/history`
- `/api/lite/devices/{device_id}/removal-assessment`
- `/api/lite/diagnostics/frontend-lifecycle`
- `/api/lite/diagnostics/frontend-lifecycle/challenge`
- `/api/lite/diagnostics/runtime`
- `/api/lite/diagnostics/runtime/full`
- `/api/lite/events`
- `/api/lite/fleet`
- `/api/lite/fleet/add-device`
- `/api/lite/fleet/agent/bootstrap-blocked`
- `/api/lite/fleet/agent/bootstrap.env`
- `/api/lite/fleet/agent/bootstrap.sh`
- `/api/lite/fleet/devices/{device_id}/display-model`
- `/api/lite/fleet/devices/{device_id}/recovery-history`
- `/api/lite/fleet/devices/{node_id}/restart-agent`
- `/api/lite/fleet/devices/{node_id}/restart-agent/status`
- `/api/lite/fleet/health-summary`
- `/api/lite/fleet/invites/latest`
- `/api/lite/fleet/invites/{invite_id}/revoke`
- `/api/lite/fleet/remove-device`
- `/api/lite/identity`
- `/api/lite/identity/rotate`
- `/api/lite/policy`
- `/api/lite/policy/apply`
- `/api/lite/recovery`
- `/api/lite/recovery/apps`
- `/api/lite/recovery/apps/{app_id}`
- `/api/lite/recovery/apps/{app_id}/backup`
- `/api/lite/recovery/apps/{app_id}/backup-targets`
- `/api/lite/recovery/apps/{app_id}/backup-to-target`
- `/api/lite/recovery/apps/{app_id}/restore`
- `/api/lite/recovery/apps/{app_id}/restore/preview`
- `/api/lite/recovery/backup`
- `/api/lite/recovery/backup-targets`
- `/api/lite/recovery/backups`
- `/api/lite/recovery/backups/{backup_id}`
- `/api/lite/recovery/backups/{backup_id}/verify`
- `/api/lite/recovery/database`
- `/api/lite/recovery/database/backup`
- `/api/lite/recovery/database/backups`
- `/api/lite/recovery/database/backups/{backup_id}`
- `/api/lite/recovery/database/backups/{backup_id}/preview`
- `/api/lite/recovery/database/backups/{backup_id}/restore`
- `/api/lite/recovery/database/backups/{backup_id}/verify`
- `/api/lite/recovery/database/restore/previews/{preview_id}`
- `/api/lite/recovery/database/restore/{restore_id}`
- `/api/lite/recovery/details`
- `/api/lite/recovery/maintenance`
- `/api/lite/recovery/maintenance/checkpoint`
- `/api/lite/recovery/maintenance/retention`
- `/api/lite/recovery/operations`
- `/api/lite/recovery/receipts/{backup_id}`
- `/api/lite/recovery/restore`
- `/api/lite/recovery/restore/checkpoints/{checkpoint_id}`
- `/api/lite/recovery/restore/preview`
- `/api/lite/recovery/restore/previews/{preview_id}`
- `/api/lite/recovery/restore/runs/{restore_id}`
- `/api/lite/recovery/summary`
- `/api/lite/release`
- `/api/lite/release/apply`
- `/api/lite/release/check`
- `/api/lite/remote-access/readiness`
- `/api/lite/revisions`
- `/api/lite/security`
- `/api/lite/security/apps`
- `/api/lite/security/apps/{app_id}`
- `/api/lite/security/apps/{app_id}/check`
- `/api/lite/security/check`
- `/api/lite/security/details/{run_id}`
- `/api/lite/security/events`
- `/api/lite/security/evidence/{run_id}`
- `/api/lite/security/evidence/{run_id}/summary`
- `/api/lite/security/freshness`
- `/api/lite/security/history`
- `/api/lite/security/profiles/{profile}`
- `/api/lite/security/progress`
- `/api/lite/security/runs/{run_id}`
- `/api/lite/security/scan`
- `/api/lite/security/summary`
- `/api/lite/status`
- `/api/lite/system/activity-summary`
- `/api/lite/system/agent`
- `/api/lite/system/health`
- `/api/lite/system/nats-readiness`
- `/api/lite/system/processes`
- `/api/lite/system/sqlite-health`
- `/api/lite/system/storage-pressure`
- `/api/lite/system/supervisor`
- `/api/lite/system/telemetry-thresholds`
- `/health`
- `/ready`
