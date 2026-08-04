---
title: "Storybook scenario inventory"
description: "Lite Storybook uses the production screen components, global Lite styling, deterministic MSW behavior, an isolated query/offline cache reset, mobile/tablet/desktop viewports, accessibility, interactions, and reduced-motion defaults."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 21be19f097c735264b076d534ba9cf9cb0c1f4ee1a38dc978dbafec9357db900
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