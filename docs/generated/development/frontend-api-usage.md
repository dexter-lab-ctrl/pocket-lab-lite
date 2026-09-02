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
source_fingerprint: 75bba1dc85f710a18576dd92155d709b0719b18003b01fa5682813717dce3066
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
| src/hooks/useLiteSecurityEvents.js | liteApi.securityProgress | GET | `/api/lite/security/progress` | query | no | static |
| src/hooks/useLiteStatus.js | liteApi.status | GET | `/api/lite/status` | query | no | static |
| src/lite/LiteApp.jsx | liteApi.catalog | GET | `/api/lite/catalog` | query | no | static |
| src/lite/LiteDevices.jsx | liteApi.deviceRemovalAssessment | GET | `/api/lite/devices/{param}/removal-assessment` | query | no | dynamic |
| src/lite/LiteDevices.jsx | liteApi.fleet | GET | `/api/lite/fleet` | query | no | static |
| src/lite/LiteDevices.jsx | liteApi.addDevice | POST | `/api/lite/fleet/add-device` | mutation | no | static |
| src/lite/LiteDevices.jsx | liteApi.restartDeviceAgent | POST | `/api/lite/fleet/devices/{param}/restart-agent` | mutation | no | dynamic |
| src/lite/LiteDevices.jsx | liteApi.restartDeviceAgentStatus | GET | `/api/lite/fleet/devices/{param}/restart-agent/status` | query | no | dynamic |
| src/lite/LiteDevices.jsx | liteApi.removeDevice | POST | `/api/lite/fleet/remove-device` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.setEnterpriseMode | PUT | `/api/lite/enterprise/identity/mode` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.identity | GET | `/api/lite/identity` | query | no | static |
| src/lite/LiteIdentity.jsx | liteApi.loginIdentity | POST | `/api/lite/identity/login` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.logoutIdentity | POST | `/api/lite/identity/logout` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.consumeOwnerClaim | POST | `/api/lite/identity/owner-claim/consume` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.ownerClaimPasskeyOptions | POST | `/api/lite/identity/owner-claim/passkey/options` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.verifyOwnerClaimPasskey | POST | `/api/lite/identity/owner-claim/passkey/verify` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.ownerClaimStatus | GET | `/api/lite/identity/owner-claim/status` | query | no | static |
| src/lite/LiteIdentity.jsx | liteApi.passkeyLoginOptions | POST | `/api/lite/identity/passkeys/login/options` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.verifyPasskeyLogin | POST | `/api/lite/identity/passkeys/login/verify` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.passkeyRegistrationOptions | POST | `/api/lite/identity/passkeys/registration/options` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.verifyPasskeyRegistration | POST | `/api/lite/identity/passkeys/registration/verify` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.revokeIdentityPasskey | GET | `/api/lite/identity/passkeys/{param}` | query | no | dynamic |
| src/lite/LiteIdentity.jsx | liteApi.renameIdentityPasskey | PUT | `/api/lite/identity/passkeys/{param}` | mutation | no | dynamic |
| src/lite/LiteIdentity.jsx | liteApi.changeIdentityPassword | POST | `/api/lite/identity/password` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.recoverIdentity | POST | `/api/lite/identity/recover` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.regenerateIdentityRecovery | POST | `/api/lite/identity/recovery/regenerate` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.revokeOtherIdentitySessions | POST | `/api/lite/identity/sessions/revoke-others` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.revokeIdentitySession | GET | `/api/lite/identity/sessions/{param}` | query | no | dynamic |
| src/lite/LiteIdentity.jsx | liteApi.setupIdentity | POST | `/api/lite/identity/setup` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.passkeyStepUpOptions | POST | `/api/lite/identity/step-up/options` | mutation | no | static |
| src/lite/LiteIdentity.jsx | liteApi.verifyPasskeyStepUp | POST | `/api/lite/identity/step-up/verify` | mutation | no | static |
| src/lite/LiteIdentityEnterprise.jsx | liteApi.enterpriseMembers | GET | `/api/lite/enterprise/identity/members` | query | no | static |
| src/lite/LiteIdentityEnterprise.jsx | liteApi.updateEnterpriseMember | PUT | `/api/lite/enterprise/identity/members/{param}` | mutation | no | dynamic |
| src/lite/LiteRecovery.jsx | liteApi.backupApp | POST | `/api/lite/apps/{param}/backup` | mutation | no | dynamic |
| src/lite/LiteRecovery.jsx | liteApi.backupNow | POST | `/api/lite/recovery/backup` | mutation | no | static |
| src/lite/LiteRecovery.jsx | liteApi.verifyBackup | POST | `/api/lite/recovery/backups/{param}/verify` | mutation | no | dynamic |
| src/lite/LiteRecovery.jsx | liteApi.databaseRecovery | GET | `/api/lite/recovery/database` | query | no | static |
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
| src/lite/LiteRules.jsx | liteApi.enterpriseIdentity | GET | `/api/lite/enterprise/identity` | query | no | static |
| src/lite/LiteRules.jsx | liteApi.policy | GET | `/api/lite/policy` | query | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.enterpriseRulesAnalysis | GET | `/api/lite/enterprise/rules/analysis` | query | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.enterpriseRuleApprovals | GET | `/api/lite/enterprise/rules/approvals` | query | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.enterpriseRuleApproval | GET | `/api/lite/enterprise/rules/approvals/{param}` | query | no | dynamic |
| src/lite/LiteRulesEnterprise.jsx | liteApi.transitionEnterpriseRuleApproval | POST | `/api/lite/enterprise/rules/approvals/{param}` | mutation | no | dynamic |
| src/lite/LiteRulesEnterprise.jsx | liteApi.enterpriseRuleDecisions | GET | `/api/lite/enterprise/rules/decisions` | query | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.enterpriseRuleDecision | GET | `/api/lite/enterprise/rules/decisions/{param}` | query | no | dynamic |
| src/lite/LiteRulesEnterprise.jsx | liteApi.enterpriseRuleExceptions | GET | `/api/lite/enterprise/rules/exceptions` | query | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.createEnterpriseRuleException | POST | `/api/lite/enterprise/rules/exceptions` | mutation | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.revokeEnterpriseRuleException | POST | `/api/lite/enterprise/rules/exceptions/{param}/revoke` | mutation | no | dynamic |
| src/lite/LiteRulesEnterprise.jsx | liteApi.enterpriseRulesHealth | GET | `/api/lite/enterprise/rules/health` | query | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.enterpriseRuleRevisions | GET | `/api/lite/enterprise/rules/revisions` | query | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.simulateEnterpriseRule | POST | `/api/lite/enterprise/rules/simulations` | mutation | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.fleet | GET | `/api/lite/fleet` | query | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.passkeyStepUpOptions | POST | `/api/lite/identity/step-up/options` | mutation | no | static |
| src/lite/LiteRulesEnterprise.jsx | liteApi.verifyPasskeyStepUp | POST | `/api/lite/identity/step-up/verify` | mutation | no | static |
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
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/identity/login` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/identity/logout` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/identity/password` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/identity/recover` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | DELETE | `/api/lite/identity/recovery/regenerate` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/identity/rotate` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/identity/sessions/:sessionId` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/identity/sessions/revoke-others` | mock | yes | static |
| src/mocks/handlers.js | MSW handler | POST | `/api/lite/identity/setup` | mock | yes | static |
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
| src/mocks/handlers.js | MSW handler | GET | `/api/lite/recovery/database` | mock | yes | static |
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
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/enterprise/identity` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/enterprise/rules/analysis` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/enterprise/rules/approvals` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/enterprise/rules/approvals/:approvalId` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/enterprise/rules/approvals/:approvalId` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/enterprise/rules/decisions` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/enterprise/rules/decisions/:decisionId` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/enterprise/rules/exceptions` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/enterprise/rules/exceptions` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/enterprise/rules/exceptions/:exceptionId/revoke` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/enterprise/rules/health` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/enterprise/rules/revisions` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/enterprise/rules/simulations` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/identity` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/identity/owner-claim/consume` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/identity/owner-claim/passkey/options` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/identity/owner-claim/passkey/verify` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/identity/owner-claim/status` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/identity/passkeys/:credentialId` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | PUT | `/api/lite/identity/passkeys/:credentialId` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/identity/passkeys/login/options` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/identity/passkeys/login/verify` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/identity/passkeys/registration/options` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/identity/passkeys/registration/verify` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/identity/step-up/options` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | POST | `/api/lite/identity/step-up/verify` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/policy` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | GET | `/api/lite/policy/decisions/:decisionId` | mock | yes | static |
| src/mocks/identityRulesP1Handlers.js | MSW handler | DELETE | `/api/lite/policy/templates` | mock | yes | static |

## Unsupported frontend route references

- None

## Backend Lite routes with no detected frontend consumer

- `/api/lite/apps/lifecycle`
- `/api/lite/apps/photoprism/storage-mappings/{mapping_id}`
- `/api/lite/apps/{app_id}/backup/storage-device`
- `/api/lite/apps/{app_id}/backups/{backup_id}/receipt`
- `/api/lite/apps/{app_id}/restore/preview`
- `/api/lite/apps/{app_id}/restore/previews/{preview_id}`
- `/api/lite/apps/{app_id}/update/apply`
- `/api/lite/apps/{app_id}/update/receipts/{operation_id}`
- `/api/lite/catalog/remove`
- `/api/lite/commands/history`
- `/api/lite/diagnostics/frontend-lifecycle`
- `/api/lite/diagnostics/frontend-lifecycle/challenge`
- `/api/lite/diagnostics/runtime/full`
- `/api/lite/enterprise/rules/activations`
- `/api/lite/enterprise/rules/activations/{operation_id}`
- `/api/lite/enterprise/rules/activations/{operation_id}/resolve`
- `/api/lite/enterprise/rules/revisions/{left_revision_id}/compare/{right_revision_id}`
- `/api/lite/enterprise/rules/revisions/{revision_id}`
- `/api/lite/enterprise/rules/rollbacks`
- `/api/lite/events`
- `/api/lite/fleet/agent/bootstrap-blocked`
- `/api/lite/fleet/agent/bootstrap.env`
- `/api/lite/fleet/agent/bootstrap.sh`
- `/api/lite/fleet/devices/{device_id}/recovery-history`
- `/api/lite/fleet/health-summary`
- `/api/lite/fleet/invites/latest`
- `/api/lite/fleet/invites/{invite_id}/revoke`
- `/api/lite/identity/owner-claim`
- `/api/lite/identity/rotate`
- `/api/lite/policy/apply`
- `/api/lite/policy/decisions/{decision_id}`
- `/api/lite/policy/templates`
- `/api/lite/recovery`
- `/api/lite/recovery/apps`
- `/api/lite/recovery/apps/{app_id}`
- `/api/lite/recovery/apps/{app_id}/backup`
- `/api/lite/recovery/apps/{app_id}/backup-targets`
- `/api/lite/recovery/apps/{app_id}/backup-to-target`
- `/api/lite/recovery/apps/{app_id}/restore`
- `/api/lite/recovery/apps/{app_id}/restore/preview`
- `/api/lite/recovery/backup-targets`
- `/api/lite/recovery/backups/{backup_id}`
- `/api/lite/recovery/database/backups`
- `/api/lite/recovery/database/backups/{backup_id}`
- `/api/lite/recovery/database/restore/previews/{preview_id}`
- `/api/lite/recovery/database/restore/{restore_id}`
- `/api/lite/recovery/maintenance`
- `/api/lite/recovery/maintenance/checkpoint`
- `/api/lite/recovery/maintenance/retention`
- `/api/lite/recovery/operations`
- `/api/lite/recovery/receipts/{backup_id}`
- `/api/lite/recovery/restore/checkpoints/{checkpoint_id}`
- `/api/lite/recovery/restore/previews/{preview_id}`
- `/api/lite/recovery/restore/runs/{restore_id}`
- `/api/lite/remote-access/readiness`
- `/api/lite/security/apps`
- `/api/lite/security/apps/{app_id}`
- `/api/lite/security/details/{run_id}`
- `/api/lite/security/events`
- `/api/lite/security/evidence/{run_id}`
- `/api/lite/security/runs/{run_id}`
- `/api/lite/security/scan`
- `/api/lite/system/activity-summary`
- `/api/lite/system/agent`
- `/api/lite/system/health`
- `/api/lite/system/nats-readiness`
- `/api/lite/system/processes`
- `/api/lite/system/sqlite-health`
- `/api/lite/system/storage-pressure`
- `/api/lite/system/supervisor`
- `/api/lite/system/telemetry-thresholds`
