import React, { useCallback, useState } from 'react';
import {
  Activity,
  ArchiveRestore,
  Copy,
  Database,
  RotateCcw,
  ShieldCheck,
} from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { useLiteRecoveryFlow } from '../hooks/useLiteRecoveryFlow.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { triggerLiteHaptic } from '../lib/liteNativeFeedback.js';
import { LiteSheet } from './LiteOverlay.jsx';
import { selectRecoveryScreenView, selectRecoverySummaryView, isLiteRecoveryViewLive } from '../lib/liteViewModels.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  copyTextToClipboard,
  backendBadgeStatus,
  backendLabel,
  PageHeader,
  LiteButton,
  LiteRefreshButton,
  ResultNotice,
  LoadingCard,
  LiteFlowStatusPanel,
} from './LiteUi.jsx';

const RECOVERY_LAYOUT_SIMPLIFICATION_PHASE_R1 = true;
const RECOVERY_SHARED_MANAGE_SHELL_PHASE_R2 = true;
const RECOVERY_SUMMARY_DETAILS_API_SPLIT_PHASE_R3 = true;
const RECOVERY_NATIVE_POLISH_PHASE_R4 = true;
const RecoveryManageSheetLazy = React.lazy(() => import('./recovery/RecoveryManageSheetLazy.jsx'));
const RecoveryActionDetailsLazy = React.lazy(() => import('./recovery/RecoveryActionDetailsLazy.jsx'));
const RecoveryDatabaseDetailsLazy = React.lazy(() => import('./recovery/RecoveryDatabaseDetailsLazy.jsx'));
const RecoveryConfirmSheetLazy = React.lazy(() => import('./recovery/RecoveryConfirmSheetLazy.jsx'));
void RECOVERY_LAYOUT_SIMPLIFICATION_PHASE_R1;
void RECOVERY_SHARED_MANAGE_SHELL_PHASE_R2;
void RECOVERY_SUMMARY_DETAILS_API_SPLIT_PHASE_R3;
void RECOVERY_NATIVE_POLISH_PHASE_R4;

export const RECOVERY_POLLING_POLICY_PHASE5 = 'RECOVERY_POLLING_POLICY_PHASE5';
export const RECOVERY_S3_QUERY_SNAPSHOT_TUNING = 'RECOVERY_S3_QUERY_SNAPSHOT_TUNING';

export function hasLiveRecoveryOperation(payload) {
  return isLiteRecoveryViewLive(payload);
}

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (!value) return 'Size unavailable';
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(value >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
  return `${Math.max(1, Math.round(value / 1024))} KB`;
}

function mergeOptional(...values) {
  const merged = Object.assign({}, ...values.filter((value) => value && typeof value === 'object'));
  return Object.keys(merged).length ? merged : null;
}

export default function RecoveryScreen() {
  const [backupResult, setBackupResult] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);
  const [previewResult, setPreviewResult] = useState(null);
  const [restoreResult, setRestoreResult] = useState(null);
  const [databaseResult, setDatabaseResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState('');
  const [recoveryManageOpen, setRecoveryManageOpen] = useState(false);
  const [recoveryManageSection, setRecoveryManageSection] = useState('backup');
  const [activeActionPanel, setActiveActionPanel] = useState('');
  const [databaseDetailsOpen, setDatabaseDetailsOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [copiedEvidence, setCopiedEvidence] = useState('');
  const [restoreConfirmation, setRestoreConfirmation] = useState('');

  const recoveryPollingIsLive = useCallback((payload) => (
    Boolean(busy) || hasLiveRecoveryOperation(payload)
  ), [busy]);
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
  } = useLiteResource(liteApi.recoverySummary, [], {
    pollingMode: 'slow',
    isLive: recoveryPollingIsLive,
    staleTime: 30_000,
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
    staleTime: 45_000,
    select: selectRecoveryScreenView,
    snapshotSelect: selectRecoveryScreenView,
  });

  const data = summaryData || {};
  const details = detailsData || {};
  const latestBackup = mergeOptional(
    details?.last_backup || details?.latest_backup,
    data?.last_backup || data?.latest_backup,
  );
  const history = details?.backup_history || details?.available_restore_points || [];
  const repository = { ...(details?.repository || {}), ...(data?.repository || {}) };
  const latestBackupVerified = latestBackup?.verification_status === 'verified';
  const latestPreview = mergeOptional(details?.latest_restore_preview, data?.latest_restore_preview);
  const latestPreviewReady = latestPreview?.status === 'ready';
  const lastRestore = mergeOptional(details?.last_restore, data?.last_restore);
  const checkpoint = mergeOptional(details?.pre_restore_checkpoint, data?.pre_restore_checkpoint);
  const serviceRestart = details?.last_restore?.service_restart || {};
  const healthValidation = details?.last_restore?.health_validation || {};
  const restoreSucceeded = ['succeeded', 'succeeded_with_warnings'].includes(String(lastRestore?.status || '').toLowerCase());
  const recoveryFlow = useLiteRecoveryFlow({ recovery: data, latestBackup, latestPreview, backendReachable, savedStateOnly });

  const databaseProtection = {
    ...(details?.database_protection || {}),
    ...(data?.database_protection || {}),
    latest_backup: mergeOptional(details?.database_protection?.latest_backup, data?.database_protection?.latest_backup),
    latest_restore_preview: mergeOptional(details?.database_protection?.latest_restore_preview, data?.database_protection?.latest_restore_preview),
    last_restore: mergeOptional(details?.database_protection?.last_restore, data?.database_protection?.last_restore),
  };
  const latestDatabaseBackup = databaseProtection?.latest_backup || null;
  const latestDatabasePreview = databaseProtection?.latest_restore_preview || null;
  const databaseMaintenance = databaseProtection?.maintenance || data?.maintenance || {};
  const databaseRestore = databaseProtection?.last_restore || null;
  const databaseRestoreGuard = databaseProtection?.restore_guard || {};
  const activeDatabaseRestore = databaseProtection?.active_restore || null;
  const databaseBackupVerified = latestDatabaseBackup?.verification_status === 'verified';
  const databasePreviewReady = latestDatabasePreview?.status === 'ready' && latestDatabasePreview?.restore_allowed !== false;
  const databaseWriteBlocked = recoveryFlow.writeBlocked
    || databaseMaintenance?.active === true
    || databaseRestoreGuard?.unresolved === true;

  const appBackups = Array.isArray(details?.app_backups)
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
    { key: 'preview', label: 'Preview', detail: latestPreviewReady ? `${latestPreview?.change_count || 0} item(s)` : 'Preview changes', complete: latestPreviewReady },
    { key: 'checkpoint', label: 'Checkpoint', detail: checkpoint?.checkpoint_id ? 'Saved before restore' : 'Created on restore', complete: checkpoint?.status === 'created' },
    { key: 'restored', label: 'Restored', detail: restoreSucceeded ? `${lastRestore?.restored_file_count || 0} file(s)` : 'Confirm restore', complete: restoreSucceeded },
  ];

  const evidenceItems = [
    { label: 'Backup ID', value: latestBackup?.backup_id },
    { label: 'Snapshot ID', value: latestBackup?.snapshot_id },
    { label: 'Manifest checksum', value: latestBackup?.manifest_checksum },
    { label: 'Preview ID', value: latestPreview?.preview_id },
    { label: 'Checkpoint ID', value: checkpoint?.checkpoint_id || lastRestore?.checkpoint_id },
    { label: 'Restore ID', value: lastRestore?.restore_id },
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
      subtitle: latestPreviewReady ? `${latestPreview?.change_count || 0} item(s) checked without changing local state.` : 'Pocket Lab will inspect the restore point safely.',
      next: 'Restore Latest',
      logs: [
        'Preview runs through the worker and does not restore files.',
        latestPreviewReady ? `${latestPreview?.change_count || 0} item(s) would be restored.` : 'Restore changes will be counted first.',
        'Raw secrets remain excluded from this restore point.',
      ],
    },
    restore: {
      title: 'Restore Latest',
      subtitle: restoreSucceeded ? `${lastRestore?.restored_file_count || 0} file(s) restored after checkpoint creation.` : 'Restore creates a checkpoint before changing Lite state.',
      next: 'Evidence',
      logs: [
        checkpoint?.checkpoint_id ? `Checkpoint saved: ${shortId(checkpoint.checkpoint_id)}` : 'Checkpoint will be saved before restore.',
        restoreSucceeded ? `${lastRestore?.restored_file_count || 0} Lite state file(s) restored.` : 'Restore is waiting for confirmation.',
        serviceRestart?.status ? `Service restart: ${serviceRestart.status}` : 'Service restart will be checked after restore.',
        healthValidation?.status ? `Lite API health: ${healthValidation.status}` : 'Lite API health will be checked after restore.',
      ],
    },
  };
  const activePanel = actionPanelMeta[activeActionPanel] || null;

  const recoveryLive = Boolean(busy) || hasLiveRecoveryOperation(data);
  const recoveryReady = !databaseWriteBlocked && (repository?.ready || latestBackupVerified || databaseBackupVerified);
  const recoveryStatus = databaseWriteBlocked ? 'review' : recoveryReady ? 'healthy' : backendBadgeStatus(data?.status);
  const recoveryTitle = databaseWriteBlocked
    ? 'Recovery needs attention'
    : latestBackupVerified
      ? 'Recovery ready'
      : latestBackup
        ? 'Verify your latest backup'
        : 'Create your first safe copy';
  const recoverySummary = databaseWriteBlocked
    ? recoveryFlow.blockedReason || 'Recovery actions are temporarily protected.'
    : latestBackupVerified
      ? 'Your latest backup is verified and ready for a restore preview.'
      : data?.summary || 'Create a safety copy before making important changes.';
  const latestActivity = [
    latestBackup ? {
      key: 'backup',
      icon: ArchiveRestore,
      title: latestBackupVerified ? 'Backup verified' : 'Backup saved',
      detail: latestBackup.created_at ? formatLiteTime(latestBackup.created_at) : 'Time unavailable',
    } : null,
    lastRestore?.restore_id ? {
      key: 'restore',
      icon: RotateCcw,
      title: lastRestore.summary || 'Restore recorded',
      detail: lastRestore.completed_at ? formatLiteTime(lastRestore.completed_at) : lastRestore.status || 'Recorded',
    } : null,
  ].filter(Boolean);

  function openRecoveryManage(section = 'backup') {
    setRecoveryManageSection(section);
    setRecoveryManageOpen(true);
  }

  function openActionPanel(action) {
    setActiveActionPanel(action);
  }

  const refreshRecovery = useCallback(async () => {
    const refreshes = [refreshSummary()];
    if (detailsNeeded) refreshes.push(refreshDetails());
    await Promise.allSettled(refreshes);
  }, [detailsNeeded, refreshDetails, refreshSummary]);

  async function copyEvidence(value, label) {
    const copied = await copyTextToClipboard(value);
    if (copied) {
      setCopiedEvidence(label);
      window.setTimeout(() => setCopiedEvidence(''), 1600);
    }
  }

  async function backup() {
    const flowCheck = recoveryFlow.requestBackup();
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    setBusy('backup');
    setBackupResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.backupNow({ include_app_data: false, reason: 'manual backup' });
      recoveryFlow.backupAccepted(payload);
      recoveryFlow.backupDone(payload);
      setBackupResult(payload);
      triggerLiteHaptic('accepted');
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function backUpDatabase() {
    if (databaseWriteBlocked) return;
    setBusy('database-backup');
    setDatabaseResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.backupDatabase({ reason: 'manual Pocket Lab database backup' });
      setDatabaseResult(payload);
      triggerLiteHaptic('accepted');
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function verifyDatabaseBackup() {
    if (!latestDatabaseBackup?.backup_id || databaseWriteBlocked) return;
    setBusy('database-verify');
    setDatabaseResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.verifyDatabaseBackup(latestDatabaseBackup.backup_id);
      setDatabaseResult(payload);
      triggerLiteHaptic('success');
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function previewDatabaseRestore() {
    if (!latestDatabaseBackup?.backup_id || databaseWriteBlocked) return;
    setBusy('database-preview');
    setDatabaseResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.previewDatabaseRestore(latestDatabaseBackup.backup_id);
      setDatabaseResult(payload);
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  function requestDatabaseRestore() {
    if (!latestDatabaseBackup?.backup_id || !latestDatabasePreview?.preview_id || databaseWriteBlocked) return;
    setRestoreConfirmation('database');
  }

  async function confirmDatabaseRestore() {
    if (!latestDatabaseBackup?.backup_id || !latestDatabasePreview?.preview_id || databaseWriteBlocked) return;
    setRestoreConfirmation('');
    triggerLiteHaptic('confirm');
    setBusy('database-restore');
    setDatabaseResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.restoreDatabase(latestDatabaseBackup.backup_id, {
        backup_id: latestDatabaseBackup.backup_id,
        preview_id: latestDatabasePreview.preview_id,
        confirm: true,
      });
      setDatabaseResult(payload);
      triggerLiteHaptic('success');
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
      triggerLiteHaptic('warning');
    } finally {
      setBusy('');
    }
  }

  async function backUpApp(app) {
    if (!app?.app_id) return;
    setBusy(`app-backup:${app.app_id}`);
    setBackupResult(null);
    setActionError(null);
    try {
      setBackupResult(await liteApi.backupApp(app.app_id, { mode: app.default_mode || 'config_only', reason: 'manual app backup' }));
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function previewAppRestore(app) {
    if (!app?.app_id) return;
    setBusy(`app-preview:${app.app_id}`);
    setPreviewResult(null);
    setActionError(null);
    try {
      setPreviewResult(await liteApi.previewAppRestore(app.app_id, { reason: 'manual app restore preview' }));
      refreshRecovery();
    } catch (err) {
      const payload = err?.payload || {};
      if (err.status === 501 && payload?.status === 'not_implemented') setPreviewResult(payload);
      else setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function verifyLatestBackup() {
    if (!latestBackup?.backup_id) return;
    const flowCheck = recoveryFlow.requestVerify();
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    setBusy('verify');
    setVerifyResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.verifyBackup(latestBackup.backup_id, { reason: 'manual verification' });
      recoveryFlow.verifyAccepted(payload);
      recoveryFlow.verified(payload);
      setVerifyResult(payload);
      triggerLiteHaptic('success');
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function previewLatestRestore() {
    if (!latestBackup?.backup_id) return;
    const flowCheck = recoveryFlow.requestPreview();
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    setBusy('preview');
    setPreviewResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.previewRestore({ backup_id: latestBackup.backup_id, reason: 'manual restore preview' });
      recoveryFlow.previewAccepted(payload);
      recoveryFlow.previewReady(payload);
      setPreviewResult(payload);
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  function restoreLatestBackup() {
    if (!latestBackup?.backup_id || !latestPreview?.preview_id) return;
    const flowCheck = recoveryFlow.requestRestore({ verified: latestBackupVerified, previewReady: latestPreviewReady, explicitBackup: Boolean(latestBackup?.backup_id && latestBackup.backup_id !== 'latest') });
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    setRestoreConfirmation('lite');
  }

  async function confirmRestoreLatestBackup() {
    if (!latestBackup?.backup_id || !latestPreview?.preview_id) return;
    setRestoreConfirmation('');
    recoveryFlow.confirmRestore();
    triggerLiteHaptic('confirm');
    setBusy('restore');
    setRestoreResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.restoreBackup({
        backup_id: latestBackup.backup_id,
        preview_id: latestPreview.preview_id,
        confirm: true,
      });
      recoveryFlow.restoreAccepted(payload);
      recoveryFlow.complete(payload);
      setRestoreResult(payload);
      triggerLiteHaptic('success');
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
      triggerLiteHaptic('warning');
    } finally {
      setBusy('');
    }
  }

  function cancelRestoreConfirmation() {
    if (restoreConfirmation === 'lite') recoveryFlow.cancel();
    setRestoreConfirmation('');
  }

  const resultNotice = databaseResult || restoreResult || previewResult || verifyResult || backupResult;

  return (
    <>
      <PageHeader
        eyebrow="Recovery"
        title="Backup & Restore"
        description="Keep a verified safety copy ready without exposing recovery internals on the main screen."
        actions={<LiteRefreshButton scope="recovery" refresh={refreshSummary} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <div className="lite-recovery-native-announcer" role="status" aria-live="polite" aria-atomic="true">
        {actionError || (busy ? `Recovery action in progress: ${busy.replace(/[-:]/g, ' ')}` : resultNotice?.summary || '')}
      </div>

      <section className="lite-recovery-r1-hero" data-recovery-r1-summary="true">
        <div className="lite-recovery-r1-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {backendLabel(data?.status, {
              ready: 'Recovery Ready',
              review: 'Needs Attention',
              danger: 'Needs Attention',
              checking: 'Checking recovery',
            })}
          </div>
          <h2>{recoveryTitle}</h2>
          <p>{recoverySummary}</p>
          <div className="lite-recovery-r1-status-strip" aria-label="Recovery status">
            <span className={latestBackupVerified ? 'is-ready' : ''}><ArchiveRestore className="h-4 w-4" />{latestBackupVerified ? 'Backup verified' : latestBackup ? 'Backup saved' : 'Backup needed'}</span>
            <span className={latestPreviewReady ? 'is-ready' : ''}><RotateCcw className="h-4 w-4" />{latestPreviewReady ? 'Restore ready' : 'Preview needed'}</span>
            <span className={databaseBackupVerified && !databaseWriteBlocked ? 'is-ready' : ''}><Database className="h-4 w-4" />{databaseWriteBlocked ? 'Database protected' : databaseBackupVerified ? 'Database healthy' : 'Database backup needed'}</span>
          </div>
          <div className="lite-recovery-r1-actions">
            <LiteButton onClick={backup} disabled={busy === 'backup' || recoveryFlow.writeBlocked}>
              {busy === 'backup' ? 'Starting backup…' : recoveryFlow.writeBlocked ? 'Reconnect to continue' : 'Back Up Now'}
            </LiteButton>
            <LiteButton tone="secondary" onClick={() => openRecoveryManage('backup')} ariaLabel="Manage Recovery">
              Manage
            </LiteButton>
          </div>
        </div>

        <div className="lite-recovery-r1-latest-card">
          <div><Database className="h-6 w-6" /><StatusBadge status={recoveryStatus}>{recoveryReady ? 'Protected' : 'Review'}</StatusBadge></div>
          <span>Latest backup</span>
          <strong>{latestBackup?.created_at ? formatLiteTime(latestBackup.created_at) : 'No backup yet'}</strong>
          <small>{latestBackup ? `${latestBackupVerified ? 'Verified' : 'Needs verification'} · ${formatSize(latestBackup.size_bytes)}` : 'Create a safe restore point to get started.'}</small>
        </div>
      </section>

      {recoveryLive ? (
        <LiteFlowStatusPanel
          title="Recovery activity"
          label={recoveryFlow.label}
          steps={recoveryFlow.steps}
          note={recoveryFlow.writeBlocked ? recoveryFlow.blockedReason : 'Pocket Lab is completing the active recovery action.'}
          className="mt-4"
        />
      ) : null}

      {loading ? <LoadingCard label="Loading recovery…" /> : null}
      {error ? <StateSurface tone="degraded" title="Recovery needs a moment" description={error} className="mb-5" /> : null}
      {actionError ? <StateSurface tone="degraded" title="Recovery action needs attention" description={actionError} className="mb-5" /> : null}

      <div className="lite-recovery-r1-summary-grid">
        <GlassCard className="lite-recovery-r1-summary-card">
          <div className="lite-recovery-r1-card-head">
            <div><ShieldCheck className="h-5 w-5" /><span><strong>Protection</strong><small>Recovery readiness at a glance</small></span></div>
            <StatusBadge status={recoveryStatus}>{recoveryReady ? 'Ready' : 'Review'}</StatusBadge>
          </div>
          <div className="lite-recovery-r1-summary-rows">
            <div><span>Backup</span><strong>{latestBackupVerified ? 'Verified' : latestBackup ? 'Needs verification' : 'Not created'}</strong></div>
            <div><span>Restore</span><strong>{latestPreviewReady ? 'Ready for confirmation' : 'Preview required'}</strong></div>
            <div><span>Database</span><strong>{databaseWriteBlocked ? 'Protected for safety' : databaseBackupVerified ? 'Healthy' : 'Backup recommended'}</strong></div>
          </div>
          <LiteButton tone="secondary" onClick={() => openRecoveryManage('protection')}>View protection</LiteButton>
        </GlassCard>

        <GlassCard className="lite-recovery-r1-summary-card">
          <div className="lite-recovery-r1-card-head">
            <div><Activity className="h-5 w-5" /><span><strong>Recent activity</strong><small>Latest backup and restore events</small></span></div>
            <StatusBadge status={latestActivity.length ? 'healthy' : 'unknown'}>{latestActivity.length ? 'Updated' : 'Quiet'}</StatusBadge>
          </div>
          <div className="lite-recovery-r1-activity-list">
            {latestActivity.length ? latestActivity.map((item) => {
              const Icon = item.icon;
              return <div key={item.key}><Icon className="h-4 w-4" /><span><strong>{item.title}</strong><small>{item.detail}</small></span></div>;
            }) : <p>No recovery activity yet. Create a backup to begin.</p>}
          </div>
          <LiteButton tone="secondary" onClick={() => openRecoveryManage('history')}>View activity</LiteButton>
        </GlassCard>
      </div>

      <LiteSheet
        open={recoveryManageOpen}
        onClose={() => setRecoveryManageOpen(false)}
        title="Manage Recovery"
        eyebrow="Manage"
        description="Backup, restore, protection, and history in one focused workspace."
        variant="manage"
        className="lite-recovery-manage-sheet"
        bodyClassName="lite-recovery-manage-scroll"
      >
        <React.Suspense fallback={<div className="lite-recovery-details-loading">Loading Recovery Manage…</div>}>
          <RecoveryManageSheetLazy
            section={recoveryManageSection}
            onSectionChange={setRecoveryManageSection}
            latestBackup={latestBackup}
            latestPreview={latestPreview}
            lastRestore={lastRestore}
            checkpoint={checkpoint}
            repository={repository}
            history={history}
            savedStateOnly={savedStateOnly || detailsSavedStateOnly}
            latestBackupVerified={latestBackupVerified}
            latestPreviewReady={latestPreviewReady}
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
            onPreviewAppRestore={previewAppRestore}
            onOpenActionDetails={openActionPanel}
            onOpenEvidence={() => setEvidenceOpen(true)}
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
        eyebrow="Action Details"
        description={activePanel?.subtitle || 'Safe recovery details from the backend-owned workflow.'}
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
        title="Database protection"
        eyebrow="Recovery Details"
        description="Verified backup, preview, restore guard, and sanitized diagnostics."
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
            backup={restoreConfirmation === 'database' ? latestDatabaseBackup : latestBackup}
            preview={restoreConfirmation === 'database' ? latestDatabasePreview : latestPreview}
            busy={busy === 'restore' || busy === 'database-restore'}
            onCancel={cancelRestoreConfirmation}
            onConfirm={restoreConfirmation === 'database' ? confirmDatabaseRestore : confirmRestoreLatestBackup}
          />
        </React.Suspense>
      </LiteSheet>

      <LiteSheet
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        title="Recovery details"
        eyebrow="Evidence"
        description="Safe reference values for troubleshooting."
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

      <ResultNotice result={resultNotice} error={actionError} />
    </>
  );
}
