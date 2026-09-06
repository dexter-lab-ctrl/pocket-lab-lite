---
title: "Storybook scenario inventory"
description: "Lite Storybook uses the production screen components, global Lite styling, deterministic MSW behavior, an isolated query/offline cache reset, mobile/tablet/desktop viewports, accessibility, interactions, and reduced-motion defaults."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: f395bcea9154f56908d6334ff8a318182bac9a3a0769b31a98339a49cf6f2733
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
- `InstalledManageOpen`
- `InstallAvailableManageOpen`
- `ActionFailedManageOpen`
- `Mobile320`

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
- `HealthyDeviceManageOpen`
- `MobileVerticalConnection`
- `DesktopHorizontalConnection`
- `RepairingManageOpen`
- `ResourceFactsComplete`
- `ResourceFactsPartial`
- `ResourceFactsStale`
- `ResourceFactsUnsupported`
- `ResourceFactsPermissionDenied`
- `ResourceFactsMissing`
- `CapabilityStale`
- `CapabilityUnsupported`
- `CapabilityBlocked`
- `CapabilityNotApplicable`
- `CapabilityMixed`
- `CapabilityUnknownFuture`
- `RuntimeServicesMixed`
- `RuntimeServicesStale`
- `RuntimeServiceUnknownFuture`
- `RuntimeServicesDisappeared`
- `SecondaryDeviceFacts`
- `SecondarySavedFactsOffline`
- `SoftwareCurrent`
- `SoftwareOutdated`
- `SoftwareIncompatible`
- `SoftwareStale`
- `LongDeviceName`
- `DeviceFactsDaylight`
- `DeviceFactsDark`
- `DeviceFactsReducedMotion`
- `DeviceFactsText200Percent`

## LiteHome

- `Healthy`
- `ReviewRecommended`
- `ReleaseUpToDate`
- `ReleaseAvailable`
- `ReleaseCheckFailed`
- `SavedOfflineSnapshot`
- `APIUnavailable`
- `HealthyManageOpen`
- `AttentionManageOpen`
- `SavedOfflineManageOpen`
- `Narrow320`
- `Mobile`
- `Desktop`

## LiteIdentity

- `IdentitySummary`
- `OwnerReady`
- `PasswordConfigured`
- `PasswordChangeRequired`
- `IdentityLoading`
- `IdentityUnavailable`
- `ManageAccessOpen`
- `ContextHelpOpen`
- `EnterpriseOwner`
- `EnterpriseAdmin`
- `EnterpriseOperator`
- `EnterpriseAuditor`
- `EnterpriseViewer`
- `EnterprisePeopleManagement`
- `Mobile320`
- `EnterpriseMobile`
- `EnterpriseRoleAwareFixture`
- `FutureRoleAwareState`

## LitePrimitives

- `OperationalReady`
- `OperationalAttention`
- `OperationalSaved`
- `LongCopy`
- `ActionRowReady`
- `ActionRowBlocked`
- `OutcomeFailed`
- `FlowWorking`
- `FlowFailed`
- `ManageSheetOpen`
- `ManageSheetMobile`
- `DetailsPanelOpen`

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
- `ManageOverview`
- `ManageBackups`
- `ManageRestore`
- `ManageRestoreBlocked`
- `OfflineSavedManage`
- `Mobile320`

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
- `ProtectionHealthy`
- `RuleEnabled`
- `RuleDisabled`
- `RuleValidationError`
- `RuleExecutionPending`
- `RulesUnavailable`
- `ManageRulesOpen`
- `ValidationErrorOpen`
- `ContextHelpOpen`
- `EnterpriseOwnerProtection`
- `EnterpriseOwnerPolicies`
- `EnterpriseAdminReview`
- `EnterpriseOperatorReview`
- `EnterpriseAuditorReadOnly`
- `EnterpriseViewerReadOnly`
- `EnterpriseRequests`
- `Mobile320`
- `EnterpriseMobile`
- `EnterpriseApprovalFixture`
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
- `HealthyManageOverview`
- `ManageChanges`
- `ManageIssues`
- `ManageCheckPath`
- `ManageEvidence`
- `ManageHistory`
- `ManageTechnicalDetails`
- `UrgentFindingManageOpen`
- `ScannerUnavailableManageOpen`
- `OfflineSavedManageOpen`