---
title: "Storybook scenario inventory"
description: "Lite Storybook uses the production screen components, global Lite styling, deterministic MSW behavior, an isolated query/offline cache reset, mobile/tablet/desktop viewports, accessibility, interactions, and reduced-motion defaults."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 3ffdc3e01fe1268519d71f92deb29a6e89cd71a0487664cb7778b66c72cd9093
schema_revision: 1
validation_status: generated
---

# Storybook scenario inventory

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Lite Storybook uses the production screen components, global Lite styling, deterministic MSW behavior, an isolated query/offline cache reset, mobile/tablet/desktop viewports, accessibility, interactions, and reduced-motion defaults.

## LiteCatalog

- `CatalogReady`
- `AppInstalledRunning`
- `AppStopped`
- `InstallAvailable`
- `ActionInProgress`
- `ActionFailed`
- `MediaNotReady`
- `RouteNotReady`
- `PreparedProjectionStale`
- `SavedOfflineSnapshot`

## LiteDevices

- `ServerHostOnline`
- `JoinedDeviceOnline`
- `JoinedDeviceOffline`
- `AgentStopped`
- `Repairing`
- `RemoteAccessNotReady`
- `ProtectedServerHost`
- `CapabilityVerified`
- `CapabilityPending`
- `CapabilityNotAdvertised`
- `InviteReady`
- `InviteExpired`
- `InviteIdentityMismatch`
- `SavedOfflineSnapshot`

## LiteHome

- `Healthy`
- `ReviewRecommended`
- `ReleaseUpToDate`
- `ReleaseAvailable`
- `ReleaseCheckFailed`
- `SavedOfflineSnapshot`
- `APIUnavailable`
- `Mobile`
- `Desktop`

## LiteIdentity

- `IdentitySummary`
- `PasswordConfigured`
- `PasswordChangeRequired`
- `IdentityLoading`
- `IdentityUnavailable`
- `FutureRoleAwareState`

## LiteRecovery

- `RecoveryReady`
- `ProjectionTooOld`
- `NoBackupsYet`
- `LatestBackupVerified`
- `BackupRunning`
- `BackupFailed`
- `RestorePreviewReady`
- `RestoreBlocked`
- `CheckpointReady`
- `NoStorageNodeConfigured`
- `RepositoryUnavailable`
- `SavedOfflineSnapshot`

## LiteRecoveryParity

- `BackendUnavailable`
- `BackupFailed`
- `BackupRunning`
- `ConfirmationRequired`
- `Empty`
- `OfflineSnapshot`
- `PreviewReady`
- `ProjectionStale`
- `RestoreCompleted`
- `RestoreFailed`
- `RestoreRunning`
- `RollbackCompleted`
- `VerificationFailed`
- `VerificationRunning`
- `Verified`

## LiteRules

- `NoRules`
- `RulesPresent`
- `RuleEnabled`
- `RuleDisabled`
- `RuleValidationError`
- `RuleExecutionPending`
- `RulesUnavailable`
- `FutureApprovalRequired`

## LiteSecurity

- `QuickCheckHealthy`
- `QuickCheckReviewRecommended`
- `FullCheckRunning`
- `AppCheckHealthy`
- `UrgentFinding`
- `NoScanHistory`
- `ProfileDataStale`
- `ProgressStages`
- `ScannerUnavailable`
- `UnsupportedAppProfileRoute`
- `SavedOfflineSnapshot`