---
title: "Frontend API usage"
description: "Module-level frontend to FastAPI Lite route ownership and compatibility."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: 51bd4578964f7f3b2d99b6bff07e2d3df9949f70dbe97f2b3c4fddd162dc46d1
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Frontend API usage

| Source module | Owner | Method | Route | Kind | Mocked | Resolution |
| --- | --- | --- | --- | --- | --- | --- |
| src/hooks/useLiteHotPathDiagnostics.js | liteApi.hotPathDiagnostics | GET | `/api/lite/diagnostics/runtime` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/lifecycle` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/lifecycle/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/photoprism/actions` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | DELETE | `/api/lite/apps/photoprism/storage-mappings` | mutation | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/photoprism/storage-mappings` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | DELETE | `/api/lite/apps/photoprism/storage-mappings/{param}` | mutation | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/photoprism/storage-preview` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/action-history` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/actions` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/actions/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/backup` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/backup/storage-device` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/backups` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/backups/{param}/receipt` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/evidence` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/restore/preview` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/restore/previews/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/update` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/update/apply` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/apps/{param}/update/receipts/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/catalog` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/catalog/install` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/commands/history` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/devices/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/devices/{param}/health` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/devices/{param}/health/history` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/devices/{param}/history` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/devices/{param}/removal-assessment` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/diagnostics/frontend-lifecycle` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/diagnostics/frontend-lifecycle/challenge` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/diagnostics/runtime` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/fleet` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/fleet/add-device` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/fleet/devices/{param}/display-model` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/fleet/devices/{param}/recovery-history` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/fleet/devices/{param}/restart-agent` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/fleet/devices/{param}/restart-agent/status` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/fleet/health-summary` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/fleet/invites/{param}/revoke` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/fleet/remove-device` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/identity` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | DELETE | `/api/lite/identity/rotate` | mutation | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/policy` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/policy/apply` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/apps` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/apps/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/apps/{param}/backup-targets` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/apps/{param}/restore` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/backup` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/backup-targets` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/backups` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/backups/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/backups/{param}/verify` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/database` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/database/backup` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/database/backups` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/database/backups/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/database/backups/{param}/preview` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/database/backups/{param}/restore` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/database/backups/{param}/verify` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/database/restore/previews/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/database/restore/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/details` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/maintenance` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/maintenance/checkpoint` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/maintenance/retention` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/operations` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/receipts/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/restore` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/restore/preview` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/restore/previews/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/recovery/summary` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/release` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/release/apply` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/release/check` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/remote-access/readiness` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/revisions` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/apps` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/apps/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/apps/{param}/check` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | DELETE | `/api/lite/security/check` | mutation | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/details/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/evidence/{param}/summary` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/freshness` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/history` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/profiles/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/progress` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/runs/{param}` | query | no | dynamic |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/security/summary` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/status` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/system/activity-summary` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/system/agent` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/system/health` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/system/nats-readiness` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/system/processes` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/system/sqlite-health` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/system/storage-pressure` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/system/supervisor` | query | no | static |
| src/hooks/useLiteQuery.js | isLiteNotModified | GET | `/api/lite/system/telemetry-thresholds` | query | no | static |
| src/hooks/useLiteSecurityEvents.js | liteApi.securityProgress | GET | `/api/lite/security/progress` | query | no | static |
| src/hooks/useLiteStatus.js | liteApi.status | GET | `/api/lite/status` | query | no | static |
| src/lite/LiteApp.jsx | liteApi.catalog | GET | `/api/lite/catalog` | query | no | static |
| src/lite/LiteDevices.jsx | liteApi.deviceRemovalAssessment | GET | `/api/lite/devices/{param}/removal-assessment` | query | no | dynamic |
| src/lite/LiteDevices.jsx | liteApi.fleet | GET | `/api/lite/fleet` | query | no | static |
| src/lite/LiteDevices.jsx | liteApi.addDevice | POST | `/api/lite/fleet/add-device` | mutation | no | static |
| src/lite/LiteDevices.jsx | liteApi.restartDeviceAgent | POST | `/api/lite/fleet/devices/{param}/restart-agent` | mutation | no | dynamic |
| src/lite/LiteDevices.jsx | liteApi.restartDeviceAgentStatus | GET | `/api/lite/fleet/devices/{param}/restart-agent/status` | query | no | dynamic |
| src/lite/LiteDevices.jsx | liteApi.removeDevice | POST | `/api/lite/fleet/remove-device` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.identity | GET | `/api/lite/identity` | query | no | static |
| src/lite/LiteIdentity.jsx | liteApi.rotateIdentity | POST | `/api/lite/identity/rotate` | mutation | no | static |
| src/lite/LiteRecovery.jsx | liteApi.backupApp | POST | `/api/lite/apps/{param}/backup` | mutation | no | dynamic |
| src/lite/LiteRecovery.jsx | liteApi.previewAppRestore | POST | `/api/lite/apps/{param}/restore/preview` | mutation | no | dynamic |
| src/lite/LiteRecovery.jsx | liteApi.backupNow | POST | `/api/lite/recovery/backup` | mutation | no | static |
| src/lite/LiteRecovery.jsx | liteApi.verifyBackup | POST | `/api/lite/recovery/backups/{param}/verify` | mutation | no | dynamic |
| src/lite/LiteRecovery.jsx | liteApi.backupDatabase | POST | `/api/lite/recovery/database/backup` | mutation | no | static |
| src/lite/LiteRecovery.jsx | liteApi.previewDatabaseRestore | POST | `/api/lite/recovery/database/backups/{param}/preview` | mutation | no | dynamic |
| src/lite/LiteRecovery.jsx | liteApi.restoreDatabase | POST | `/api/lite/recovery/database/backups/{param}/restore` | mutation | no | dynamic |
| src/lite/LiteRecovery.jsx | liteApi.verifyDatabaseBackup | POST | `/api/lite/recovery/database/backups/{param}/verify` | mutation | no | dynamic |
| src/lite/LiteRecovery.jsx | liteApi.recoveryDetails | GET | `/api/lite/recovery/details` | query | no | static |
| src/lite/LiteRecovery.jsx | liteApi.restoreBackup | POST | `/api/lite/recovery/restore` | mutation | no | static |
| src/lite/LiteRecovery.jsx | liteApi.previewRestore | POST | `/api/lite/recovery/restore/preview` | mutation | no | static |
| src/lite/LiteRecovery.jsx | liteApi.recoverySummary | GET | `/api/lite/recovery/summary` | query | no | static |
| src/lite/LiteReleaseUpdateCard.jsx | liteApi.releaseStatus | GET | `/api/lite/release` | query | no | static |
| src/lite/LiteReleaseUpdateCard.jsx | liteApi.applyRelease | POST | `/api/lite/release/apply` | mutation | no | static |
| src/lite/LiteReleaseUpdateCard.jsx | liteApi.checkRelease | POST | `/api/lite/release/check` | mutation | no | static |
| src/lite/LiteRevisionSyncBridge.jsx | liteApi.domainRevisions | GET | `/api/lite/revisions` | query | no | static |
| src/lite/LiteRules.jsx | liteApi.policy | GET | `/api/lite/policy` | query | no | static |
| src/lite/LiteRules.jsx | liteApi.applyPolicy | POST | `/api/lite/policy/apply` | mutation | no | static |
| src/lite/LiteSecurity.jsx | liteApi.checkSecurityApp | POST | `/api/lite/security/apps/{param}/check` | mutation | no | dynamic |
| src/lite/LiteSecurity.jsx | liteApi.runSecurityScan | POST | `/api/lite/security/check` | mutation | no | static |
| src/lite/LiteSecurity.jsx | liteApi.securityEvidenceSummary | GET | `/api/lite/security/evidence/{param}/summary` | query | no | dynamic |
| src/lite/LiteSecurity.jsx | liteApi.securityFreshness | GET | `/api/lite/security/freshness` | query | no | static |
| src/lite/LiteSecurity.jsx | liteApi.securityHistory | GET | `/api/lite/security/history` | query | no | static |
| src/lite/LiteSecurity.jsx | liteApi.securityProfile | GET | `/api/lite/security/profiles/{param}` | query | no | dynamic |
| src/lite/LiteSecurity.jsx | liteApi.securityProgress | GET | `/api/lite/security/progress` | query | no | static |
| src/lite/LiteSecurity.jsx | liteApi.security | GET | `/api/lite/security/summary` | query | no | static |
| src/lite/LiteSecurity.jsx | liteApi.securitySummary | GET | `/api/lite/security/summary` | query | no | static |
| src/lite/catalog/AppCatalogScreen.jsx | liteApi.appLifecycleProfile | GET | `/api/lite/apps/lifecycle/{param}` | query | no | dynamic |
| src/lite/catalog/AppCatalogScreen.jsx | liteApi.appActions | GET | `/api/lite/apps/photoprism/actions` | query | no | static |
| src/lite/catalog/AppCatalogScreen.jsx | liteApi.photoprismStorageMappings | GET | `/api/lite/apps/photoprism/storage-mappings` | query | no | static |
| src/lite/catalog/AppCatalogScreen.jsx | liteApi.connectPhotoPrismStorage | POST | `/api/lite/apps/photoprism/storage-mappings` | mutation | no | static |
| src/lite/catalog/AppCatalogScreen.jsx | liteApi.photoprismStoragePreview | GET | `/api/lite/apps/photoprism/storage-preview` | query | no | static |
| src/lite/catalog/AppCatalogScreen.jsx | liteApi.appActions | GET | `/api/lite/apps/{param}/actions` | query | no | dynamic |
| src/lite/catalog/AppCatalogScreen.jsx | liteApi.runAppAction | POST | `/api/lite/apps/{param}/actions/{param}` | mutation | no | dynamic |
| src/lite/catalog/AppCatalogScreen.jsx | liteApi.catalog | GET | `/api/lite/catalog` | query | no | static |
| src/lite/catalog/AppCatalogScreen.jsx | liteApi.installApp | POST | `/api/lite/catalog/install` | mutation | no | static |
| src/lite/devices/DeviceDetailsLazy.jsx | liteApi.device | GET | `/api/lite/devices/{param}` | query | no | dynamic |
| src/lite/devices/DeviceDetailsLazy.jsx | liteApi.deviceHealth | GET | `/api/lite/devices/{param}/health` | query | no | dynamic |
| src/lite/devices/DeviceDetailsLazy.jsx | liteApi.deviceHealthHistory | GET | `/api/lite/devices/{param}/health/history` | query | no | dynamic |
| src/lite/devices/DeviceDetailsLazy.jsx | liteApi.deviceHistory | GET | `/api/lite/devices/{param}/history` | query | no | dynamic |
| src/lite/devices/DeviceModelPickerLazy.jsx | liteApi.updateDeviceDisplayModel | PUT | `/api/lite/fleet/devices/{param}/display-model` | mutation | no | dynamic |
| src/lite/recovery/RecoveryBackupHistory.jsx | liteApi.recoveryHistory | GET | `/api/lite/recovery/backups` | query | no | static |
| src/lite/security/SecurityHistoryLazy.jsx | liteApi.securityHistory | GET | `/api/lite/security/history` | query | no | static |
| src/lite/security/securityPreload.js | liteApi.securityDetails | GET | `/api/lite/security` | query | no | static |
| src/lite/security/securityPreload.js | liteApi.securitySummary | GET | `/api/lite/security/summary` | query | no | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/apps/lifecycle` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/apps/lifecycle/photoprism` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/apps/photoprism/actions` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/apps/photoprism/actions/:actionId` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/apps/photoprism/evidence` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/apps/photoprism/storage-mappings` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | DELETE | `/api/lite/apps/photoprism/storage-mappings/:mappingId` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/apps/photoprism/storage-preview` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/apps/photoprism/update` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/apps/photoprism/update/apply` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/apps/photoprism/update/receipts/:operationId` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/catalog` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/catalog/install` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/diagnostics/frontend-lifecycle/challenge` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/events` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/fleet` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/fleet/add-device` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/fleet/devices/:nodeId/restart-agent` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/fleet/remove-device` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/identity` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/identity/rotate` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/policy` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/policy/apply` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/apps` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/apps/photoprism` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/apps/photoprism/backup` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/apps/photoprism/backup-targets` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/recovery/apps/photoprism/backup-to-target` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/recovery/apps/photoprism/restore/preview` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/recovery/backup` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/recovery/backup-targets` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/backups` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/backups/:backupId` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/recovery/backups/:backupId/verify` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/receipts/:backupId` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/recovery/restore` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/recovery/restore/preview` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/restore/previews/:previewId` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/summary` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/release` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/revisions` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/security` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/security/apps` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/security/apps/photoprism` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/security/apps/photoprism/check` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/security/check` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/security/evidence/:runId` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/security/freshness` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/security/scan` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/security/summary` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/status` | mock | yes | static |

## Unsupported frontend route references

- None

## Backend Lite routes with no detected frontend consumer

- `/api/lite/catalog/remove`
- `/api/lite/diagnostics/runtime/full`
- `/api/lite/events`
- `/api/lite/fleet/agent/bootstrap-blocked`
- `/api/lite/fleet/agent/bootstrap.env`
- `/api/lite/fleet/agent/bootstrap.sh`
- `/api/lite/fleet/invites/latest`
- `/api/lite/recovery/apps/{app_id}/backup`
- `/api/lite/recovery/apps/{app_id}/backup-to-target`
- `/api/lite/recovery/apps/{app_id}/restore/preview`
- `/api/lite/recovery/restore/checkpoints/{checkpoint_id}`
- `/api/lite/recovery/restore/runs/{restore_id}`
- `/api/lite/security/events`
- `/api/lite/security/evidence/{run_id}`
- `/api/lite/security/scan`
