import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArchiveRestore,
  Copy,
  Database,
  Maximize2,
  Move,
  RotateCcw,
  ShieldCheck,
} from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { useLiteRecoveryActions } from '../hooks/useLiteRecoveryActions.js';
import { useLiteUiStore } from '../stores/liteUiStore.js';
import { useLiteRecoveryFlow } from '../hooks/useLiteRecoveryFlow.js';
import { useLiteServiceWorkerUpdateBlocker } from '../hooks/useLiteServiceWorkerUpdateBlocker.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { createLiteFeedbackDeduper, triggerLiteHaptic } from '../lib/liteNativeFeedback.js';
import { LiteSheet } from './LiteOverlay.jsx';
import { useDesktopManageGeometry } from './components/useDesktopManageGeometry.js';
import { LiteMotionReveal } from './LiteMotion.jsx';
import { selectRecoveryScreenView, selectRecoverySummaryView, isLiteRecoveryViewLive } from '../lib/liteViewModels.js';
import {
  GlassCard,
  StateSurface,
  copyTextToClipboard,
  PageHeader,
  LiteButton,
  LiteRefreshButton,
  LoadingCard,
  LiteFlowStatusPanel,
} from './LiteUi.jsx';
import { LiteFreshness } from './LiteUx.jsx';
import RecoveryJourney from './recovery/RecoveryJourney.jsx';
import RecoveryPremiumTimeline from './recovery/RecoveryPremiumTimeline.jsx';
import { isRecoveryLocationReady, recoveryPremiumHero, recoveryJourneyStatus, recoveryPremiumActivity, recoveryOverviewFacts } from './recovery/recoveryPremiumView.js';
import './recovery/recoveryPremium.css';

const RECOVERY_LAYOUT_SIMPLIFICATION_PHASE_R1 = true;
const RECOVERY_SHARED_MANAGE_SHELL_PHASE_R2 = true;
const RECOVERY_SUMMARY_DETAILS_API_SPLIT_PHASE_R3 = true;
const RECOVERY_NATIVE_POLISH_PHASE_R4 = true;
const loadRecoveryManageSheet = () => import('./recovery/RecoveryManageSheetLazy.jsx');
const loadRecoveryHistory = () => import('./recovery/RecoveryBackupHistory.jsx');
const loadRecoveryActionDetails = () => import('./recovery/RecoveryActionDetailsLazy.jsx');
const loadRecoveryDatabaseDetails = () => import('./recovery/RecoveryDatabaseDetailsLazy.jsx');
const loadRecoveryConfirmSheet = () => import('./recovery/RecoveryConfirmSheetLazy.jsx');
const RecoveryManageSheetLazy = React.lazy(loadRecoveryManageSheet);
const RecoveryActionDetailsLazy = React.lazy(loadRecoveryActionDetails);
const RecoveryDatabaseDetailsLazy = React.lazy(loadRecoveryDatabaseDetails);
const RecoveryConfirmSheetLazy = React.lazy(loadRecoveryConfirmSheet);
void RECOVERY_LAYOUT_SIMPLIFICATION_PHASE_R1;
void RECOVERY_SHARED_MANAGE_SHELL_PHASE_R2;
void RECOVERY_SUMMARY_DETAILS_API_SPLIT_PHASE_R3;
void RECOVERY_NATIVE_POLISH_PHASE_R4;

export const RECOVERY_POLLING_POLICY_PHASE5 = 'RECOVERY_POLLING_POLICY_PHASE5';
export const RECOVERY_S3_QUERY_SNAPSHOT_TUNING = 'RECOVERY_S3_QUERY_SNAPSHOT_TUNING';

export function hasLiveRecoveryOperation(payload) {
  return isLiteRecoveryViewLive(payload);
}

function mergeOptional(...values) {
  const merged = Object.assign({}, ...values.filter((value) => value && typeof value === 'object'));
  return Object.keys(merged).length ? merged : null;
}

export default function RecoveryScreen() {
  const [copiedEvidence, setCopiedEvidence] = useState('');
  const [selectedBackup, setSelectedBackup] = useState(null);
  const recoveryManageOpen = useLiteUiStore((state) => state.recoveryManageOpen);
  const recoveryManageSection = useLiteUiStore((state) => state.activeRecoveryManageSection);
  const activeActionPanel = useLiteUiStore((state) => state.activeRecoveryDetailsPanel || '');
  const databaseDetailsOpen = useLiteUiStore((state) => state.recoveryDatabaseDetailsOpen);
  const evidenceOpen = useLiteUiStore((state) => state.recoveryEvidenceOpen);
  const restoreConfirmation = useLiteUiStore((state) => state.recoveryRestoreConfirmation || '');
  const setRecoveryManageOpen = useLiteUiStore((state) => state.setRecoveryManageOpen);
  const setRecoveryManageSection = useLiteUiStore((state) => state.setActiveRecoveryManageSection);
  const setActiveActionPanel = useLiteUiStore((state) => state.setActiveRecoveryDetailsPanel);
  const setDatabaseDetailsOpen = useLiteUiStore((state) => state.setRecoveryDatabaseDetailsOpen);
  const setEvidenceOpen = useLiteUiStore((state) => state.setRecoveryEvidenceOpen);
  const setRestoreConfirmation = useLiteUiStore((state) => state.setRecoveryRestoreConfirmation);
  const resetRecoveryTransientUi = useLiteUiStore((state) => state.resetRecoveryTransientUi);
  const pushToast = useLiteUiStore((state) => state.pushToast);
  const {
    panelRef: managePanelRef, desktopPanel: desktopManagePanel,
    panelStyle: managePanelStyle, announcement: managePanelAnnouncement,
    reset: resetManagePanel, startPanelInteraction, adjustPanelWithKeyboard,
  } = useDesktopManageGeometry({
    open: recoveryManageOpen, defaultWidth: 720, minWidth: 400, minHeight: 380,
  });
  const recoveryCompletionFeedback = useRef(createLiteFeedbackDeduper());
  const recoveryPollingIsLive = useCallback((payload) => hasLiveRecoveryOperation(payload), []);
  const detailsNeeded = recoveryManageOpen || Boolean(activeActionPanel) || databaseDetailsOpen || evidenceOpen || Boolean(restoreConfirmation);
  const {
    data: summaryData,
    loading,
    error,
    refresh: refreshSummary,
    cacheStatus,
    refreshing,
    backendReachable,
    savedStateOnly,
    backendDegraded: summaryBackendDegraded,
    degradedReason: summaryDegradedReason,
    lastUpdatedLabel,
    isExpired,
  } = useLiteResource(liteApi.recoverySummary, [], {
    pollingMode: 'slow',
    isLive: recoveryPollingIsLive,
    staleTime: 10_000,
    select: selectRecoverySummaryView,
    snapshotSelect: selectRecoverySummaryView,
  });
  const {
    data: detailsData,
    loading: detailsLoading,
    error: detailsError,
    refresh: refreshDetails,
    savedStateOnly: detailsSavedStateOnly,
  } = useLiteResource(liteApi.recoveryDetails, [], {
    enabled: detailsNeeded,
    pollingMode: 'slow',
    isLive: recoveryPollingIsLive,
    staleTime: 15_000,
    select: selectRecoveryScreenView,
    snapshotSelect: selectRecoveryScreenView,
  });
  const {
    data: recoveryLocationsData,
    refresh: reloadRecoveryLocations,
  } = useLiteResource(liteApi.recoveryLocations, [], {
    staleTime: 15_000,
    snapshotSelect: (payload) => payload || {},
  });

  const {
    data: databaseProtectionData,
  } = useLiteResource(liteApi.databaseRecovery, [], {
    pollingMode: 'slow',
    staleTime: 45_000,
  });
  const {
    data: appRecoveryProfiles,
  } = useLiteResource(liteApi.recoveryApps, [], {
    enabled: detailsNeeded,
    pollingMode: 'relaxed',
    staleTime: 30_000,
  });


  const data = summaryData || {};
  const details = detailsData || {};
  const runtimeRecovery = data?.runtime_recovery || {};
  const runtimeRecoveryState = String(runtimeRecovery?.state || 'unknown').toLowerCase();
  const runtimeRecoveredRecently = Boolean(
    runtimeRecovery?.stable
    && Array.isArray(runtimeRecovery?.recovered_services)
    && runtimeRecovery.recovered_services.length
  );
  const runtimeRecoveryLabel = runtimeRecovery?.stable
    ? runtimeRecoveredRecently ? 'Recovered recently' : 'Running normally'
    : ['repairing', 'converging'].includes(runtimeRecoveryState)
      ? 'Recovery in progress'
      : runtimeRecoveryState === 'unknown'
        ? 'Checking'
        : 'Something changed';
  const latestBackup = mergeOptional(
    details?.last_backup || details?.latest_backup,
    data?.last_backup || data?.latest_backup,
  );
  const history = details?.backup_history || details?.available_restore_points || [];
  const repository = { ...(details?.repository || {}), ...(data?.repository || {}) };
  const latestBackupVerified = latestBackup?.verification_status === 'verified';
  const latestPreview = mergeOptional(details?.latest_restore_preview, data?.latest_restore_preview);
  const latestPreviewReady = latestPreview?.status === 'ready';
  const backupLocations = recoveryLocationsData || details?.backup_locations || data?.backup_locations || {};
  const selectedRestorePoint = selectedBackup || latestBackup;
  const selectedRestorePreview = latestPreview && selectedRestorePoint?.backup_id === latestPreview?.backup_id ? latestPreview : null;
  const selectedBackupVerified = selectedRestorePoint?.verification_status === 'verified';
  const selectedPreviewReady = selectedRestorePreview?.status === 'ready';
  const selectedBackupLocation = selectedRestorePoint?.location || selectedRestorePreview?.location || null;
  const selectedBackupLocationReady = isRecoveryLocationReady(selectedBackupLocation);
  const lastRestore = mergeOptional(details?.last_restore, data?.last_restore);
  const checkpoint = mergeOptional(details?.pre_restore_checkpoint, data?.pre_restore_checkpoint);
  const serviceRestart = details?.last_restore?.service_restart || {};
  const healthValidation = details?.last_restore?.health_validation || {};
  const restoreSucceeded = ['succeeded', 'succeeded_with_warnings'].includes(String(lastRestore?.status || '').toLowerCase());
  const projectionStale = summaryBackendDegraded === true
    || summaryDegradedReason === 'projection_too_old'
    || data?.read_degraded === true
    || data?.degraded_reason === 'projection_too_old'
    || details?.read_degraded === true
    || details?.degraded_reason === 'projection_too_old';
  const recoveryFlow = useLiteRecoveryFlow({ recovery: data, latestBackup, latestPreview, lastRestore, backendReachable, savedStateOnly });
  const recoveryWriteBlocked = recoveryFlow.writeBlocked || projectionStale;
  const recoveryWriteBlockedReason = projectionStale
    ? 'Recovery information is older than expected. Refresh before making changes.'
    : recoveryFlow.blockedReason;

  const databaseProtection = {
    ...(details?.database_protection || {}),
    ...(data?.database_protection || {}),
    ...(databaseProtectionData || {}),
    latest_backup: mergeOptional(
      details?.database_protection?.latest_backup,
      data?.database_protection?.latest_backup,
      databaseProtectionData?.latest_backup,
    ),
    latest_restore_preview: mergeOptional(
      details?.database_protection?.latest_restore_preview,
      data?.database_protection?.latest_restore_preview,
      databaseProtectionData?.latest_restore_preview,
    ),
    last_restore: mergeOptional(
      details?.database_protection?.last_restore,
      data?.database_protection?.last_restore,
      databaseProtectionData?.last_restore,
    ),
    restore_history: mergeOptional(
      details?.database_protection?.restore_history,
      data?.database_protection?.restore_history,
      databaseProtectionData?.restore_history,
    ),
    projection_reconciliation: mergeOptional(
      details?.database_protection?.projection_reconciliation,
      data?.database_protection?.projection_reconciliation,
      databaseProtectionData?.projection_reconciliation,
    ),
  };
  const latestDatabaseBackup = databaseProtection?.latest_backup || null;
  const latestDatabasePreview = databaseProtection?.latest_restore_preview || null;
  const databaseMaintenance = databaseProtection?.maintenance || data?.maintenance || {};
  const databaseRestore = databaseProtection?.last_restore || null;
  const databaseRestoreGuard = databaseProtection?.restore_guard || {};
  const activeDatabaseRestore = databaseProtection?.active_restore || null;
  const databaseBackupVerified = latestDatabaseBackup?.verification_status === 'verified';
  const databasePreviewReady = latestDatabasePreview?.status === 'ready' && latestDatabasePreview?.restore_allowed !== false;
  const databaseWriteBlocked = recoveryWriteBlocked
    || databaseMaintenance?.active === true
    || databaseRestoreGuard?.unresolved === true;

  const serverRecoveryLive = hasLiveRecoveryOperation(data);
  const recoveryActions = useLiteRecoveryActions({
    writeBlocked: recoveryWriteBlocked,
    blockedReason: recoveryWriteBlockedReason,
    operationBusy: (recoveryFlow.isBusy && recoveryFlow.value !== 'restoreConfirmationRequired') || serverRecoveryLive,
    operationBusyReason: 'Pocket Lab is already completing a Recovery action.',
  });
  const flowBusyKey = {
    backup_now: 'backup',
    verify_backup: 'verify',
    preview_restore_recovery: 'preview',
    recovery_restore: 'restore',
  }[recoveryFlow.context.activeActionId] || '';
  const busy = recoveryActions.busyKey || (recoveryFlow.isBusy ? flowBusyKey : '');
  const actionError = recoveryActions.errorMessage || recoveryFlow.error || null;

  const appBackups = Array.isArray(appRecoveryProfiles?.apps)
    ? appRecoveryProfiles.apps
    : Array.isArray(details?.app_backups)
      ? details.app_backups
      : Array.isArray(details?.app_backup_profiles?.apps)
        ? details.app_backup_profiles.apps
        : [];
  const lifecycleProfiles = Array.isArray(details?.app_lifecycle_profiles?.apps) ? details.app_lifecycle_profiles.apps : [];
  const lifecycleByApp = new Map(lifecycleProfiles.map((item) => [item.app_id, item]));
  const backupTargets = Array.isArray(details?.backup_targets) ? details.backup_targets : [];
  const protectedItems = Array.isArray(details?.what_will_be_backed_up) ? details.what_will_be_backed_up : [];
  const excludedItems = Array.isArray(details?.what_will_not_be_backed_up) ? details.what_will_not_be_backed_up : [];

  const shortId = (value) => {
    const text = String(value || '');
    if (!text) return 'Not available';
    if (text.length <= 18) return text;
    return `${text.slice(0, 10)}…${text.slice(-6)}`;
  };

  const restoreSteps = [
    { key: 'backup', label: 'Backup', detail: latestBackup ? 'Safe copy saved' : 'Create backup', complete: Boolean(latestBackup) },
    { key: 'verified', label: 'Verified', detail: latestBackupVerified ? 'Evidence checked' : 'Verify backup', complete: latestBackupVerified },
    { key: 'preview', label: 'Preview', detail: latestPreviewReady ? (Number.isInteger(latestPreview?.change_count) ? String(latestPreview.change_count) + ' item(s)' : 'Impact not reported') : 'Preview changes', complete: latestPreviewReady },
    { key: 'checkpoint', label: 'Checkpoint', detail: checkpoint?.checkpoint_id ? 'Saved before restore' : 'Created on restore', complete: checkpoint?.status === 'created' },
    { key: 'restored', label: 'Restored', detail: restoreSucceeded ? (Number.isInteger(lastRestore?.restored_file_count) ? String(lastRestore.restored_file_count) + ' file(s)' : 'Result recorded') : 'Confirm restore', complete: restoreSucceeded },
  ];

  const evidenceItems = [
    { label: 'Backup ID', value: latestBackup?.backup_id },
    { label: 'Backup reference', value: latestBackup?.snapshot_id },
    { label: 'Verification fingerprint', value: latestBackup?.manifest_checksum },
    { label: 'Preview reference', value: latestPreview?.preview_id },
    { label: 'Safety checkpoint reference', value: checkpoint?.checkpoint_id || lastRestore?.checkpoint_id },
    { label: 'Restore reference', value: lastRestore?.restore_id },
  ].filter((item) => item.value);

  const actionPanelMeta = {
    verify: {
      title: 'Verify Backup',
      subtitle: latestBackupVerified ? 'Evidence checked and backup is ready.' : 'Pocket Lab is checking the backup evidence.',
      next: 'Preview Restore',
      logs: [
        'Verification runs through the Lite control API.',
        latestBackupVerified ? 'Manifest checksum passed.' : 'Manifest checksum will be checked.',
        latestBackupVerified ? 'Repository metadata check passed.' : 'Repository metadata will be checked.',
      ],
    },
    preview: {
      title: 'Preview Restore',
      subtitle: latestPreviewReady ? (Number.isInteger(latestPreview?.change_count) ? String(latestPreview.change_count) + ' item(s) checked without changing local state.' : 'Preview ready; impact not reported.') : 'Pocket Lab will inspect the restore point safely.',
      next: 'Restore Latest',
      logs: [
        'Preview checks the restore point without changing files.',
        latestPreviewReady ? (Number.isInteger(latestPreview?.change_count) ? String(latestPreview.change_count) + ' item(s) would be restored.' : 'Item count not reported.') : 'Restore changes will be counted first.',
        'Raw secrets remain excluded from this restore point.',
      ],
    },
    restore: {
      title: 'Restore Latest',
      subtitle: restoreSucceeded ? (Number.isInteger(lastRestore?.restored_file_count) ? String(lastRestore.restored_file_count) + ' file(s) restored.' : 'Restore result recorded; file count not reported.') : 'Restore creates a checkpoint before changing Lite state.',
      next: 'Evidence',
      logs: [
        checkpoint?.checkpoint_id ? `Checkpoint saved: ${shortId(checkpoint.checkpoint_id)}` : 'Checkpoint will be saved before restore.',
        restoreSucceeded ? `${lastRestore?.restored_file_count || 0} Lite state file(s) restored.` : 'Restore is waiting for confirmation.',
        serviceRestart?.status ? `Workspace services: ${serviceRestart.status}` : 'Workspace services will be checked after restore.',
        healthValidation?.status ? `Workspace health: ${healthValidation.status}` : 'Workspace health will be checked after restore.',
      ],
    },
  };
  const activePanel = actionPanelMeta[activeActionPanel] || null;

  const recoveryLive = Boolean(busy) || recoveryFlow.isBusy || serverRecoveryLive;
  useLiteServiceWorkerUpdateBlocker('recovery-workflow', Boolean(recoveryLive || restoreConfirmation));
  const premiumHero = recoveryPremiumHero({
    data, backup: latestBackup, preview: latestPreview, repository, database: databaseProtection,
    busy, saved: savedStateOnly, stale: projectionStale || isExpired, reachable: backendReachable,
    blocked: databaseWriteBlocked,
  });
  const overviewFacts = recoveryOverviewFacts({
    backup: latestBackup, preview: latestPreview, locations: backupLocations,
    saved: savedStateOnly, stale: projectionStale || isExpired, reachable: backendReachable,
  });
  const journeyStatuses = recoveryJourneyStatus({
    backup: latestBackup, preview: latestPreview, restore: lastRestore,
    busy: ['backup', 'verify', 'preview', 'restore'].includes(busy) ? busy : '',
    saved: savedStateOnly || projectionStale || isExpired || !backendReachable,
  });
  const premiumActivity = recoveryPremiumActivity({
    activity: data?.recent_activity, backup: latestBackup, restore: lastRestore,
    unavailable: !backendReachable && !savedStateOnly,
  });

  function openRecoveryManage(section = 'backup') {
    triggerLiteHaptic('accepted');
    void loadRecoveryManageSheet();
    void loadRecoveryActionDetails();
    if (section === 'history') void loadRecoveryHistory();
    setRecoveryManageSection(section);
    setRecoveryManageOpen(true);
  }

  function openActionPanel(action) {
    triggerLiteHaptic('accepted');
    setActiveActionPanel(action);
  }

  async function copyEvidence(value, label) {
    const copied = await copyTextToClipboard(value);
    if (copied) {
      setCopiedEvidence(label);
      pushToast({ id: `recovery:evidence-copied:${label}`, kind: 'success', title: 'Evidence copied', message: `${label} is ready to paste.` });
      window.setTimeout(() => setCopiedEvidence(''), 1600);
    }
  }

  async function backup() {
    const flowCheck = recoveryFlow.requestBackup();
    if (!flowCheck.ok) return;
    await recoveryActions.runAction({
      actionId: 'backup_now',
      busyKey: 'backup',
      execute: () => liteApi.backupNow({ include_app_data: true, reason: 'manual full restore point' }),
      onAccepted: recoveryFlow.backupAccepted,
      onDone: recoveryFlow.backupDone,
      onFailure: recoveryFlow.fail,
      acceptedHaptic: 'accepted',
    });
  }

  async function backUpDatabase() {
    await recoveryActions.runAction({
      actionId: 'database_backup',
      busyKey: 'database-backup',
      blocked: databaseWriteBlocked,
      blockedMessage: 'Database protection is temporarily blocking writes.',
      execute: () => liteApi.backupDatabase({ reason: 'manual Pocket Lab database backup' }),
      acceptedHaptic: 'accepted',
      failureHaptic: 'warning',
    });
  }

  async function discoverRecoveryLocation(candidateId) {
    if (!candidateId) return;
    await recoveryActions.runAction({
      actionId: 'discover_recovery_location',
      busyKey: `location-discover:${candidateId}`,
      blocked: recoveryWriteBlocked,
      blockedMessage: recoveryWriteBlockedReason,
      execute: () => liteApi.discoverRecoveryLocation(candidateId),
      successHaptic: 'success',
      failureHaptic: 'warning',
    });
    reloadRecoveryLocations?.();
  }

  async function selectRecoveryLocation(locationId) {
    if (!locationId) return;
    await recoveryActions.runAction({
      actionId: 'select_recovery_location',
      busyKey: `location-select:${locationId}`,
      blocked: recoveryWriteBlocked,
      blockedMessage: recoveryWriteBlockedReason,
      execute: () => liteApi.selectRecoveryLocation(locationId),
      acceptedHaptic: 'accepted',
      failureHaptic: 'warning',
    });
    reloadRecoveryLocations?.();
  }

  async function forgetRecoveryLocation(locationId) {
    if (!locationId) return;
    await recoveryActions.runAction({
      actionId: 'forget_recovery_location',
      busyKey: `location-forget:${locationId}`,
      blocked: recoveryWriteBlocked,
      blockedMessage: recoveryWriteBlockedReason,
      execute: () => liteApi.forgetRecoveryLocation(locationId),
      acceptedHaptic: 'accepted',
      failureHaptic: 'warning',
    });
    reloadRecoveryLocations?.();
  }

  async function verifyDatabaseBackup() {
    if (!latestDatabaseBackup?.backup_id) return;
    await recoveryActions.runAction({
      actionId: 'database_verify',
      busyKey: 'database-verify',
      blocked: databaseWriteBlocked,
      blockedMessage: 'Database protection is temporarily blocking verification.',
      execute: () => liteApi.verifyDatabaseBackup(latestDatabaseBackup.backup_id),
      successHaptic: 'success',
      failureHaptic: 'warning',
    });
  }

  async function previewDatabaseRestore() {
    if (!latestDatabaseBackup?.backup_id) return;
    await recoveryActions.runAction({
      actionId: 'database_preview_restore',
      busyKey: 'database-preview',
      blocked: databaseWriteBlocked,
      blockedMessage: 'Database protection is temporarily blocking restore preview.',
      execute: () => liteApi.previewDatabaseRestore(latestDatabaseBackup.backup_id),
      failureHaptic: 'warning',
    });
  }

  function requestDatabaseRestore() {
    if (!latestDatabaseBackup?.backup_id || !latestDatabasePreview?.preview_id || databaseWriteBlocked) return;
    setRestoreConfirmation('database');
  }

  async function confirmDatabaseRestore() {
    if (!latestDatabaseBackup?.backup_id || !latestDatabasePreview?.preview_id || databaseWriteBlocked) return;
    setRestoreConfirmation('');
    triggerLiteHaptic('confirm');
    await recoveryActions.runAction({
      actionId: 'database_restore',
      busyKey: 'database-restore',
      blocked: databaseWriteBlocked,
      blockedMessage: 'Database protection is temporarily blocking restore.',
      execute: () => liteApi.restoreDatabase(latestDatabaseBackup.backup_id, {
        backup_id: latestDatabaseBackup.backup_id,
        preview_id: latestDatabasePreview.preview_id,
        confirm: true,
      }),
      successHaptic: 'success',
      failureHaptic: 'warning',
    });
  }

  async function backUpApp(app) {
    if (!app?.app_id) return;
    await recoveryActions.runAction({
      actionId: 'app_backup',
      busyKey: `app-backup:${app.app_id}`,
      appId: app.app_id,
      execute: () => liteApi.backupApp(app.app_id, {
        mode: app.default_mode || 'config_only',
        reason: 'manual app backup',
      }),
      failureHaptic: 'warning',
    });
  }

  async function verifyLatestBackup(backupOverride = null) {
    const restorePoint = backupOverride || selectedRestorePoint;
    if (backupOverride) setSelectedBackup(backupOverride);
    if (!restorePoint?.backup_id) return;
    const flowCheck = recoveryFlow.requestVerify();
    if (!flowCheck.ok) return;
    await recoveryActions.runAction({
      actionId: 'verify_backup',
      busyKey: 'verify',
      execute: () => liteApi.verifyBackup(restorePoint.backup_id, { reason: 'manual verification' }),
      onAccepted: recoveryFlow.verifyAccepted,
      onDone: recoveryFlow.verified,
      onFailure: recoveryFlow.fail,
      successHaptic: 'success',
    });
  }

  async function previewLatestRestore(backupOverride = null) {
    const restorePoint = backupOverride || selectedRestorePoint;
    if (backupOverride) setSelectedBackup(backupOverride);
    if (!restorePoint?.backup_id) return;
    const flowCheck = recoveryFlow.requestPreview();
    if (!flowCheck.ok) return;
    await recoveryActions.runAction({
      actionId: 'preview_restore_recovery',
      busyKey: 'preview',
      execute: () => liteApi.previewRestore({
        backup_id: restorePoint.backup_id,
        reason: 'manual restore preview',
      }),
      onAccepted: recoveryFlow.previewAccepted,
      onDone: recoveryFlow.previewReady,
      onFailure: recoveryFlow.fail,
    });
  }

  function restoreLatestBackup(backupOverride = null) {
    const restorePoint = backupOverride || selectedRestorePoint;
    const restorePreview = latestPreview && restorePoint?.backup_id === latestPreview?.backup_id ? latestPreview : null;
    const restoreLocation = restorePoint?.location || restorePreview?.location || null;
    const restoreLocationReady = !restoreLocation
      || isRecoveryLocationReady(restoreLocation);
    if (backupOverride) setSelectedBackup(backupOverride);
    if (!restorePoint?.backup_id || !restorePreview?.preview_id || !restoreLocationReady) return;
    const flowCheck = recoveryFlow.requestRestore({
      verified: restorePoint?.verification_status === 'verified',
      previewReady: restorePreview?.status === 'ready',
      explicitBackup: Boolean(restorePoint?.backup_id && restorePoint.backup_id !== 'latest'),
    });
    if (!flowCheck.ok) return;
    setRestoreConfirmation('lite');
  }

  async function confirmRestoreLatestBackup() {
    if (!selectedRestorePoint?.backup_id || !selectedRestorePreview?.preview_id) return;
    setRestoreConfirmation('');
    recoveryFlow.confirmRestore();
    triggerLiteHaptic('confirm');
    await recoveryActions.runAction({
      actionId: 'recovery_restore',
      busyKey: 'restore',
      execute: () => liteApi.restoreBackup({
        backup_id: selectedRestorePoint.backup_id,
        preview_id: selectedRestorePreview.preview_id,
        confirm: true,
      }),
      onAccepted: recoveryFlow.restoreAccepted,
      onDone: recoveryFlow.complete,
      onFailure: recoveryFlow.fail,
      successHaptic: 'success',
    });
  }

  useEffect(() => () => {
    resetRecoveryTransientUi();
  }, [resetRecoveryTransientUi]);

  useEffect(() => {
    const actionId = recoveryFlow.context.lastCompletedActionId;
    const completedAt = recoveryFlow.context.lastCompletedAt;
    if (!actionId || !completedAt) return;
    const copy = {
      backup_now: { title: 'Backup completed', message: 'Pocket Lab recorded a new backup.' },
      verify_backup: { title: 'Backup verified', message: 'Pocket Lab confirmed the latest backup is ready.' },
      preview_restore_recovery: { title: 'Restore preview ready', message: 'Review the expected changes before restoring.' },
      recovery_restore: { title: 'Restore completed', message: 'Pocket Lab completed the protected restore checks.' },
    }[actionId];
    if (!copy) return;
    const id = `recovery:${actionId}:${completedAt}`;
    if (!recoveryCompletionFeedback.current.once(id, 'success')) return;
    pushToast({ id, kind: 'success', title: copy.title, message: copy.message });
  }, [pushToast, recoveryFlow.context.lastCompletedActionId, recoveryFlow.context.lastCompletedAt]);

  useEffect(() => {
    const actionId = recoveryFlow.context.lastFailedActionId;
    const failedAt = recoveryFlow.context.lastFailedAt;
    if (!actionId || !failedAt) return;
    const id = `recovery:${actionId}:failed:${failedAt}`;
    if (!recoveryCompletionFeedback.current.once(id, 'warning')) return;
    pushToast({
      id,
      kind: 'warning',
      title: actionId === 'recovery_restore' ? 'Restore needs attention' : 'Recovery action needs attention',
      message: recoveryFlow.error || 'Pocket Lab recorded a Recovery result that needs review.',
    });
  }, [pushToast, recoveryFlow.context.lastFailedActionId, recoveryFlow.context.lastFailedAt, recoveryFlow.error]);

  useEffect(() => {
    if (!restoreConfirmation) return;
    const liteConfirmationInvalid = restoreConfirmation === 'lite' && (
      recoveryFlow.writeBlocked
      || recoveryFlow.value !== 'restoreConfirmationRequired'
      || !selectedBackupVerified
      || !selectedPreviewReady
      || !selectedBackupLocationReady
      || !selectedRestorePoint?.backup_id
      || !selectedRestorePreview?.preview_id
    );
    const databaseConfirmationInvalid = restoreConfirmation === 'database' && (
      databaseWriteBlocked
      || !databaseBackupVerified
      || !databasePreviewReady
      || !latestDatabaseBackup?.backup_id
      || !latestDatabasePreview?.preview_id
    );
    if (!liteConfirmationInvalid && !databaseConfirmationInvalid) return;
    if (restoreConfirmation === 'lite') recoveryFlow.cancel();
    setRestoreConfirmation('');
  }, [
    databaseBackupVerified,
    databasePreviewReady,
    databaseWriteBlocked,
    latestBackup?.backup_id,
    latestBackupVerified,
    latestDatabaseBackup?.backup_id,
    latestDatabasePreview?.preview_id,
    latestPreview?.preview_id,
    latestPreviewReady,
    selectedBackupLocationReady,
    selectedBackupVerified,
    selectedPreviewReady,
    selectedRestorePoint?.backup_id,
    selectedRestorePreview?.preview_id,
    recoveryFlow,
    restoreConfirmation,
    setRestoreConfirmation,
  ]);

  function cancelRestoreConfirmation() {
    if (restoreConfirmation === 'lite') recoveryFlow.cancel();
    setRestoreConfirmation('');
  }

  const recoveryAnnouncement = actionError
    || (busy ? `Backup or restore in progress: ${busy.replace(/[-:]/g, ' ')}` : '')
    || (recoveryFlow.context.lastCompletedAt ? premiumActivity[0]?.title || 'Backup and restore status updated.' : '');


  return (
    <>
      <PageHeader
        eyebrow="Recovery"
        title="Recovery"
        description="Protect your workspace and review each step before restoring anything."
        actions={<LiteRefreshButton scope="recovery" refresh={refreshSummary} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      
      <div className="lite-recovery-premium-screen lite-render-containment lite-render-containment--recovery" data-recovery-premium="true">
        <div className="lite-recovery-native-announcer" role="status" aria-live="polite" aria-atomic="true">{recoveryAnnouncement}</div>
        <GlassCard className="lite-recovery-premium-protection lite-recovery-r1-hero" data-recovery-protection-state={premiumHero.state} data-recovery-r1-summary="true">
          <div className="lite-recovery-premium-brand">
            <ShieldCheck aria-hidden="true" />
            <div>
              <span className="lite-recovery-premium-eyebrow">Workspace protection</span>
              <span className="lite-recovery-premium-status" data-testid="parity-recovery-status" data-status={premiumHero.state}>{premiumHero.statusLabel}</span>
              <h2 data-testid="parity-recovery-summary">{premiumHero.headline}</h2>
              <p>{premiumHero.summary}</p>
              {premiumHero.time ? <p className="lite-recovery-premium-backup-date" data-testid="parity-latest-backup-id" data-backup-id={latestBackup?.backup_id || ''}>Latest backup: <time dateTime={premiumHero.time}>{formatLiteTime(premiumHero.time)}</time></p> : null}
            </div>
          </div>
          <ul className="lite-recovery-premium-indicators" aria-label="Recovery status" data-recovery-summary-facts="true">
            {overviewFacts.map((fact) => (
              <li key={fact.id} data-state={fact.state} data-recovery-fact={fact.id}>
                {fact.id === 'backup' ? <ArchiveRestore aria-hidden="true" />
                  : fact.id === 'destination' ? <Database aria-hidden="true" />
                    : <RotateCcw aria-hidden="true" />}
                <span>{fact.title}</span><strong>{fact.label}</strong>
                <small>{fact.id === 'backup' && latestBackup?.created_at && !savedStateOnly
                  ? formatLiteTime(latestBackup.created_at) : fact.detail}</small>
              </li>
            ))}
          </ul>
          <div className="lite-recovery-premium-actions">
            <LiteButton onClick={backup} disabled={premiumHero.disabled || recoveryWriteBlocked || Boolean(busy)} haptic>{busy ? 'Recovery working…' : 'Back Up Now'}</LiteButton>
            <LiteButton tone="secondary" onClick={() => openRecoveryManage('backup')} ariaLabel="Manage Recovery">Manage Recovery</LiteButton>
          </div>
          {(recoveryWriteBlocked || premiumHero.disabled) && !busy ? (
            <p className="lite-recovery-premium-disabled-reason" role="status">
              {recoveryWriteBlockedReason || (premiumHero.state === 'blocked'
                ? 'A recovery safety guard or backup destination is unavailable.' : 'Backup actions are not currently available.')}
            </p>
          ) : null}
          <LiteFreshness saved={savedStateOnly} stale={projectionStale || isExpired} refreshing={refreshing} lastUpdatedLabel={lastUpdatedLabel} backendReachable={backendReachable} />
        </GlassCard>
        <div className="lite-recovery-premium-layout" data-recovery-overview-layout="responsive">
          <RecoveryJourney stages={journeyStatuses} saved={savedStateOnly || projectionStale || isExpired || !backendReachable} />
          <RecoveryPremiumTimeline items={premiumActivity} unavailable={!backendReachable && !savedStateOnly} saved={savedStateOnly || projectionStale || isExpired} onViewActivity={() => openRecoveryManage('history')} />
        </div>
        {recoveryLive ? <LiteMotionReveal motionKey={busy || recoveryFlow.value} ariaLive="polite">
          <LiteFlowStatusPanel title="Recovery in progress" label={recoveryFlow.label} steps={recoveryFlow.steps} note={recoveryFlow.writeBlocked ? recoveryFlow.blockedReason : 'Only backend-reported progress is authoritative.'} />
        </LiteMotionReveal> : null}
        {loading ? <LoadingCard label="Loading recovery…" /> : null}
        {projectionStale ? <StateSurface tone="degraded" title="Recovery information needs a refresh" description="Saved information does not confirm live restore readiness." data-testid="recovery-projection-stale" /> : null}
        {error ? <StateSurface tone="degraded" title="Backup information is temporarily unavailable" description={error} /> : null}
        {actionError ? <StateSurface tone="degraded" title="Backup or restore needs attention" description={actionError} /> : null}
      </div>

      <LiteSheet
        open={recoveryManageOpen}
        onClose={() => setRecoveryManageOpen(false)}
        title="Manage backups and recovery"
        eyebrow="Manage"
        description="Create and verify backups, preview restores, and review protection history in one focused workspace."
        variant="manage"
        className={`lite-recovery-manage-sheet ${desktopManagePanel ? 'is-movable' : ''}`.trim()}
        bodyClassName="lite-recovery-manage-scroll"
        surfaceRef={managePanelRef}
        surfaceStyle={managePanelStyle}
        surfaceProps={{ 'data-recovery-manage-layout': desktopManagePanel ? 'desktop-movable' : 'mobile-sheet' }}
        headerActions={desktopManagePanel ? (
          <div className="lite-recovery-desktop-panel-tools" role="group" aria-label="Desktop Recovery panel controls">
            <button type="button" aria-label="Move Recovery panel" title="Drag or use arrow keys to move; Home resets" aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight"
              onPointerDown={(event) => startPanelInteraction('move', event)} onKeyDown={(event) => adjustPanelWithKeyboard('move', event)}><Move size={16} aria-hidden="true" /></button>
            <button type="button" aria-label="Reset Recovery panel position and size" onClick={resetManagePanel}><RotateCcw size={16} aria-hidden="true" /> Reset</button>
            <button type="button" aria-label="Resize Recovery panel" title="Drag or use arrow keys to resize; Home resets" aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight"
              onPointerDown={(event) => startPanelInteraction('resize', event)} onKeyDown={(event) => adjustPanelWithKeyboard('resize', event)}><Maximize2 size={16} aria-hidden="true" /></button>
            <span className="sr-only" role="status" aria-live="polite">{managePanelAnnouncement}</span>
          </div>
        ) : null}
      >
        <React.Suspense fallback={<div className="lite-recovery-details-loading">Opening recovery tools…</div>}>
          <RecoveryManageSheetLazy
            section={recoveryManageSection}
            onSectionChange={setRecoveryManageSection}
            latestBackup={selectedRestorePoint}
            latestPreview={selectedRestorePreview}
            lastRestore={lastRestore}
            checkpoint={checkpoint}
            repository={repository}
            history={history}
            savedStateOnly={savedStateOnly || detailsSavedStateOnly}
            latestBackupVerified={selectedBackupVerified}
            latestPreviewReady={selectedPreviewReady}
            restoreSucceeded={restoreSucceeded}
            databaseProtection={databaseProtection}
            latestDatabaseBackup={latestDatabaseBackup}
            databaseBackupVerified={databaseBackupVerified}
            databasePreviewReady={databasePreviewReady}
            databaseMaintenance={databaseMaintenance}
            databaseWriteBlocked={databaseWriteBlocked}
            appBackups={appBackups}
            lifecycleByApp={lifecycleByApp}
            backupTargets={backupTargets}
            backupLocations={backupLocations}
            protectedItems={protectedItems}
            excludedItems={excludedItems}
            busy={busy}
            onBackup={backup}
            onVerify={verifyLatestBackup}
            onPreview={previewLatestRestore}
            onRestore={restoreLatestBackup}
            onDatabaseBackup={backUpDatabase}
            onOpenDatabaseDetails={() => setDatabaseDetailsOpen(true)}
            onBackUpApp={backUpApp}
            onOpenActionDetails={openActionPanel}
            onOpenEvidence={() => setEvidenceOpen(true)}
            selectedBackupId={selectedRestorePoint?.backup_id || ''}
            onSelectBackup={setSelectedBackup}
            onDiscoverLocation={discoverRecoveryLocation}
            onSelectLocation={selectRecoveryLocation}
            onForgetLocation={forgetRecoveryLocation}
            detailsLoading={detailsLoading && !detailsData}
            detailsError={detailsError}
            onRetryDetails={refreshDetails}
          />
        </React.Suspense>
      </LiteSheet>

      <LiteSheet
        open={Boolean(activePanel)}
        onClose={() => setActiveActionPanel('')}
        title={activePanel?.title || 'Recovery details'}
        eyebrow="Details"
        description={activePanel?.subtitle || 'Verified backup and restore details with recorded outcomes.'}
        variant="security"
        className="lite-recovery-action-details-sheet"
        bodyClassName="lite-recovery-action-details-scroll"
      >
        {activePanel ? (
          <React.Suspense fallback={<div className="lite-recovery-details-loading">Loading recovery details…</div>}>
            <RecoveryActionDetailsLazy
              actionKey={activeActionPanel}
              panel={activePanel}
              restoreSteps={restoreSteps}
              latestBackup={latestBackup}
              latestPreview={latestPreview}
              checkpoint={checkpoint}
              lastRestore={lastRestore}
              repository={repository}
              serviceRestart={serviceRestart}
              healthValidation={healthValidation}
              history={history}
              savedStateOnly={savedStateOnly || detailsSavedStateOnly}
              evidenceItems={evidenceItems}
              onOpenEvidence={() => setEvidenceOpen(true)}
            />
          </React.Suspense>
        ) : null}
      </LiteSheet>

      <LiteSheet
        open={databaseDetailsOpen}
        onClose={() => setDatabaseDetailsOpen(false)}
        title="Pocket Lab data protection"
        eyebrow="Recovery Details"
        description="Verified backup, restore preview, safety guard, and protected diagnostics."
        variant="security"
        className="lite-recovery-database-manage-sheet"
        bodyClassName="lite-recovery-database-manage-scroll"
      >
        <React.Suspense fallback={<div className="lite-recovery-details-loading">Loading database protection…</div>}>
          <RecoveryDatabaseDetailsLazy
            databaseProtection={databaseProtection}
            latestBackup={latestDatabaseBackup}
            latestPreview={latestDatabasePreview}
            lastRestore={databaseRestore}
            maintenance={databaseMaintenance}
            restoreGuard={databaseRestoreGuard}
            activeRestore={activeDatabaseRestore}
            writeBlocked={databaseWriteBlocked}
            busy={busy}
            onBackup={backUpDatabase}
            onVerify={verifyDatabaseBackup}
            onPreview={previewDatabaseRestore}
            onRestore={requestDatabaseRestore}
          />
        </React.Suspense>
      </LiteSheet>

      <LiteSheet
        open={Boolean(restoreConfirmation)}
        onClose={cancelRestoreConfirmation}
        title={restoreConfirmation === 'database' ? 'Restore Pocket Lab database' : 'Restore backup'}
        eyebrow="Confirm Restore"
        description="Review the protected action before local state changes."
        variant="security"
        className="lite-recovery-confirm-sheet"
        bodyClassName="lite-recovery-confirm-scroll"
      >
        <React.Suspense fallback={<div className="lite-recovery-details-loading">Loading restore confirmation…</div>}>
          <RecoveryConfirmSheetLazy
            kind={restoreConfirmation || 'lite'}
            backup={restoreConfirmation === 'database' ? latestDatabaseBackup : selectedRestorePoint}
            location={restoreConfirmation === 'database' ? null : selectedBackupLocation}
            preview={restoreConfirmation === 'database' ? latestDatabasePreview : selectedRestorePreview}
            busy={busy === 'restore' || busy === 'database-restore'}
            onCancel={cancelRestoreConfirmation}
            onConfirm={restoreConfirmation === 'database' ? confirmDatabaseRestore : confirmRestoreLatestBackup}
          />
        </React.Suspense>
      </LiteSheet>

      <LiteSheet
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        title="Recovery record"
        eyebrow="Troubleshooting record"
        description="Protected reference values for support and recovery review."
        variant="security"
        className="lite-recovery-evidence-sheet"
        bodyClassName="lite-recovery-evidence-list"
      >
        {evidenceItems.length ? evidenceItems.map((item) => (
          <div key={item.label} className="lite-recovery-evidence-item">
            <span>{item.label}</span>
            <strong>{shortId(item.value)}</strong>
            <button type="button" onClick={() => copyEvidence(item.value, item.label)}>
              <Copy className="h-4 w-4" />
              {copiedEvidence === item.label ? 'Copied' : 'Copy'}
            </button>
          </div>
        )) : <p>No recovery evidence is available yet.</p>}
      </LiteSheet>

    </>
  );
}
