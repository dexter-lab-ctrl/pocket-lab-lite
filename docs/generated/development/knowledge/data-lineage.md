---
title: "Data lineage explorer"
description: "Field and route lineage using explicit API/UI/table relationships."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Data lineage explorer

Verified relationships are generated from frontend API usage, parity field mappings, and SQLite reader metadata. Missing links remain unvalidated rather than guessed.

## Route lineage

| API | UI | SQLite | Confidence |
| --- | --- | --- | --- |
| `GET /api/lite/catalog` | ui:liteapp | table:app_action_lifecycle, table:app_current_state | contract-derived |
| `GET /api/lite/devices/{device_id}/removal-assessment` | ui:litedevices | — | unvalidated |
| `GET /api/lite/enterprise/identity` | ui:literules | — | unvalidated |
| `GET /api/lite/enterprise/identity/members` | ui:liteidentityenterprise | — | unvalidated |
| `GET /api/lite/enterprise/rules/analysis` | ui:literulesenterprise | — | unvalidated |
| `GET /api/lite/enterprise/rules/approvals` | ui:literulesenterprise | — | unvalidated |
| `GET /api/lite/enterprise/rules/approvals/{approval_id}` | ui:literulesenterprise | — | unvalidated |
| `GET /api/lite/enterprise/rules/decisions` | ui:literulesenterprise | — | unvalidated |
| `GET /api/lite/enterprise/rules/decisions/{decision_id}` | ui:literulesenterprise | — | unvalidated |
| `GET /api/lite/enterprise/rules/exceptions` | ui:literulesenterprise | — | unvalidated |
| `GET /api/lite/enterprise/rules/health` | ui:literulesenterprise | — | unvalidated |
| `GET /api/lite/enterprise/rules/revisions` | ui:literulesenterprise | — | unvalidated |
| `GET /api/lite/fleet` | ui:litedevices, ui:literulesenterprise | table:device_awareness_state, table:device_enrollment_registry, table:device_health_attention, table:device_health_current, table:device_health_transitions, table:device_heartbeats, table:device_identity_guards, table:device_invite_lifecycle, table:device_lifecycle_events, table:device_lifecycle_transactions, table:device_recovery_history, table:device_removal_receipts, table:device_supervisor_state, table:device_system_profiles | contract-derived |
| `GET /api/lite/fleet/devices/{node_id}/restart-agent/status` | ui:litedevices | — | unvalidated |
| `GET /api/lite/identity` | ui:liteidentity | — | unvalidated |
| `GET /api/lite/identity/owner-claim/status` | ui:liteidentity | — | unvalidated |
| `GET /api/lite/policy` | ui:literules | — | unvalidated |
| `GET /api/lite/recovery/database` | ui:literecovery | — | unvalidated |
| `GET /api/lite/recovery/details` | ui:literecovery | table:backup_manifest_index, table:recovery_code_batches, table:recovery_codes, table:recovery_current_state, table:recovery_operations | contract-derived |
| `GET /api/lite/recovery/summary` | ui:literecovery | — | unvalidated |
| `GET /api/lite/release` | ui:litereleaseupdatecard | table:lite_installed_release_identity, table:release_runtime_projection | contract-derived |
| `GET /api/lite/revisions` | ui:literevisionsyncbridge | table:domain_revisions, table:projection_dirty_signals | contract-derived |
| `GET /api/lite/security/evidence/{run_id}/summary` | ui:litesecurity | — | unvalidated |
| `GET /api/lite/security/freshness` | ui:litesecurity | — | unvalidated |
| `GET /api/lite/security/history` | ui:litesecurity | — | unvalidated |
| `GET /api/lite/security/profiles/{profile}` | ui:litesecurity | table:security_database_backups, table:security_database_restores, table:security_maintenance_runs, table:security_profile_snapshots, table:security_scan_evidence_refs, table:security_scan_findings, table:security_scan_progress_events, table:security_scan_tool_runs, table:security_store_metadata | contract-derived |
| `GET /api/lite/security/progress` | ui:litesecurity | — | unvalidated |
| `GET /api/lite/security/summary` | ui:litesecurity | table:security_database_backups, table:security_database_restores, table:security_maintenance_runs, table:security_profile_snapshots, table:security_scan_evidence_refs, table:security_scan_findings, table:security_scan_progress_events, table:security_scan_tool_runs, table:security_store_metadata | contract-derived |
| `POST /api/lite/apps/{app_id}/backup` | ui:literecovery | — | unvalidated |
| `POST /api/lite/apps/{app_id}/restore/preview` | ui:literecovery | — | unvalidated |
| `POST /api/lite/enterprise/rules/approvals/{approval_id}` | ui:literulesenterprise | — | unvalidated |
| `POST /api/lite/enterprise/rules/exceptions` | ui:literulesenterprise | — | unvalidated |
| `POST /api/lite/enterprise/rules/exceptions/{exception_id}/revoke` | ui:literulesenterprise | — | unvalidated |
| `POST /api/lite/enterprise/rules/simulations` | ui:literulesenterprise | — | unvalidated |
| `POST /api/lite/fleet/add-device` | ui:litedevices | — | unvalidated |
| `POST /api/lite/fleet/devices/{node_id}/restart-agent` | ui:litedevices | — | unvalidated |
| `POST /api/lite/fleet/remove-device` | ui:litedevices | — | unvalidated |
| `POST /api/lite/identity/login` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/logout` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/owner-claim/consume` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/owner-claim/passkey/options` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/owner-claim/passkey/verify` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/passkeys/login/options` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/passkeys/login/verify` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/passkeys/registration/options` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/passkeys/registration/verify` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/password` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/recover` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/recovery/regenerate` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/sessions/revoke-others` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/setup` | ui:liteidentity | — | unvalidated |
| `POST /api/lite/identity/step-up/options` | ui:liteidentity, ui:literulesenterprise | — | unvalidated |
| `POST /api/lite/identity/step-up/verify` | ui:liteidentity, ui:literulesenterprise | — | unvalidated |
| `POST /api/lite/recovery/backup` | ui:literecovery | — | unvalidated |
| `POST /api/lite/recovery/backups/{backup_id}/verify` | ui:literecovery | — | unvalidated |
| `POST /api/lite/recovery/database/backup` | ui:literecovery | — | unvalidated |
| `POST /api/lite/recovery/database/backups/{backup_id}/preview` | ui:literecovery | — | unvalidated |
| `POST /api/lite/recovery/database/backups/{backup_id}/restore` | ui:literecovery | — | unvalidated |
| `POST /api/lite/recovery/database/backups/{backup_id}/verify` | ui:literecovery | — | unvalidated |
| `POST /api/lite/recovery/restore` | ui:literecovery | — | unvalidated |
| `POST /api/lite/recovery/restore/preview` | ui:literecovery | — | unvalidated |
| `POST /api/lite/release/apply` | ui:litereleaseupdatecard | — | unvalidated |
| `POST /api/lite/release/check` | ui:litereleaseupdatecard | — | unvalidated |
| `POST /api/lite/security/apps/{app_id}/check` | ui:litesecurity | — | unvalidated |
| `POST /api/lite/security/check` | ui:litesecurity | — | unvalidated |
| `PUT /api/lite/enterprise/identity/members/{human_id}` | ui:liteidentityenterprise | — | unvalidated |
| `PUT /api/lite/enterprise/identity/mode` | ui:liteidentity | — | unvalidated |
| `PUT /api/lite/identity/passkeys/{credential_id}` | ui:liteidentity | — | unvalidated |

## Field lineage

| Mapping | Domain | Boundary | Source field | Target field | Transformation | APIs | UI consumers | Test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| recovery-status | recovery | backend-api | recovery current status | status | normalize status enum | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-recovery-status |
| recovery-summary | recovery | backend-api | recovery summary | summary | allowlisted text | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-recovery-summary |
| latest-backup-id | recovery | backend-api | manifest.backup_id | last_backup.backup_id | direct stable identifier | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-latest-backup-id |
| verification-status | recovery | backend-api | manifest.verification_status | last_backup.verification_status | normalized enum | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-verification-status |
| preview-id | recovery | backend-api | restore preview.preview_id | latest_restore_preview.preview_id | direct stable identifier | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-preview-id |
| restore-allowed | recovery | backend-api | restore preview.restore_allowed | latest_restore_preview.restore_allowed | derived guard boolean | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-restore-allowed |
| checkpoint-id | recovery | backend-api | checkpoint.checkpoint_id | pre_restore_checkpoint.checkpoint_id | direct stable identifier | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-checkpoint-id |
| restore-id | recovery | backend-api | restore run.restore_id | last_restore.restore_id | direct stable identifier | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-restore-id |
| api-status-selector | recovery | api-selector | status | status | normalizeRecoveryStatus | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-selector-status |
| api-backup-selector | recovery | api-selector | last_backup | latest_backup | normalizeRecoveryBackup allowlist | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-selector-backup |
| api-preview-selector | recovery | api-selector | latest_restore_preview | restore_preview | normalizeRecoveryPreview allowlist | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-selector-preview |
| selector-render-protection | recovery | selector-render | latest_backup.verification_status | Latest protected backup card | verified -> Verified; other -> Needs verification | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-render-backup |
| selector-render-preview | recovery | selector-render | restore_preview.status | Recovery status strip | ready -> Restore preview ready; otherwise Restore preview needed | GET /api/lite/recovery/backups?limit={limit}&cursor={cursor}, GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/operations?limit={limit}&cursor={cursor}, GET /api/lite/recovery/receipts/{backup_id}, GET /api/lite/recovery/summary | LiteRecovery, liteApi.databaseRecovery, liteApi.recoveryDetails, liteApi.recoveryHistory, liteApi.recoveryOperations, liteApi.recoveryReceipt, liteApi.recoverySummary, liteQueryKeys.recoveryOperations, selectRecoveryHistorySnapshotView, selectRecoveryScreenView, selectRecoverySummaryView | parity-render-preview |
