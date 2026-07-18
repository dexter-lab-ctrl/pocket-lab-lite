import React, { useCallback, useMemo, useState } from 'react';
import {
  Activity,
  Copy,
  Database,
  Download,
  EyeOff,
  FileCheck,
  Fingerprint,
  LayoutGrid,
  Lock,
  Menu,
  Network,
  RefreshCw,
  Server,
  ShieldCheck,
  Trash2,
  WifiOff,
} from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { useLiteRecoveryFlow } from '../hooks/useLiteRecoveryFlow.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { LiteSheet } from './LiteOverlay.jsx';
import { selectRecoveryScreenView, isLiteRecoveryViewLive } from '../lib/liteViewModels.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  DEVICE_ROLE_OPTIONS,
  NAV_ITEMS,
  roleLabel,
  deviceConnectionLabel,
  canRestartDeviceAgent,
  canRemoveDevice,
  normalizeDeviceName,
  findDeviceNameConflict,
  deviceDuplicateMessage,
  deviceStatusLabel,
  copyTextToClipboard,
  serviceTone,
  normalizeBackendState,
  backendBadgeStatus,
  backendLabel,
  backendHeroTitle,
  securityFindingTone,
  securityFindingLabel,
  clampSecurityProgress,
  parseSecurityTimestamp,
  formatSecurityRemainingSeconds,
  liveSecurityProgress,
  securityProgressStage,
  scanInProgressValue,
  triggerHapticFeedback,
  shortRunId,
  formatSecurityDuration,
  securityTrendLabel,
  securityTrendView,
  securityDeltaTone,
  isSecurityTimeoutFinding,
  securityDeltaBadge,
  securityDeltaTitle,
  securityDeltaDescription,
  securityDeltaAction,
  securityDeltaSummary,
  securityExecutionStateTone,
  securityExecutionStepGlyph,
  securityToolStatusLabel,
  securityExecutionStateFromBackend,
  securityExecutionStepLabel,
  normalizeSecurityExecutionSteps,
  securityExecutionTimeline,
  PageHeader,
  LiteButton,
  LiteRefreshButton,
  ResultNotice,
  LoadingCard,
  LiteFlowStatusPanel,
  friendlyOverallLabel,
  deviceLinkState,
  restartProgressTitle,
  restartStepStateLabel,
  safeRestartSteps
} from './LiteUi.jsx';


const RECOVERY_RENDER_REDUCTION_MILESTONE_1 = true;
const RECOVERY_PROGRESSIVE_DETAILS_MILESTONE_2 = true;
const RecoveryActionDetailsLazy = React.lazy(() => import('./recovery/RecoveryActionDetailsLazy.jsx'));
const RecoveryBackupHistory = React.lazy(() => import('./recovery/RecoveryBackupHistory.jsx'));
const RecoveryDatabaseDetailsLazy = React.lazy(() => import('./recovery/RecoveryDatabaseDetailsLazy.jsx'));
void RECOVERY_RENDER_REDUCTION_MILESTONE_1;
void RECOVERY_PROGRESSIVE_DETAILS_MILESTONE_2;


export const RECOVERY_POLLING_POLICY_PHASE5 = 'RECOVERY_POLLING_POLICY_PHASE5';
export const RECOVERY_S3_QUERY_SNAPSHOT_TUNING = 'RECOVERY_S3_QUERY_SNAPSHOT_TUNING';

export function hasLiveRecoveryOperation(payload) {
  return isLiteRecoveryViewLive(payload);
}

export default function RecoveryScreen() {
  const [backupResult, setBackupResult] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);
  const [previewResult, setPreviewResult] = useState(null);
  const [restoreResult, setRestoreResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState('');
  const recoveryPollingIsLive = useCallback((payload) => (
    Boolean(busy) || hasLiveRecoveryOperation(payload)
  ), [busy]);
  const { data, loading, error, refresh, cacheStatus, refreshing, backendReachable, savedStateOnly } = useLiteResource(liteApi.recovery, [], {
    pollingMode: 'slow',
    isLive: recoveryPollingIsLive,
    staleTime: 30_000,
    select: selectRecoveryScreenView,
    snapshotSelect: selectRecoveryScreenView,
  });
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [copiedEvidence, setCopiedEvidence] = useState('');
  const [activeActionPanel, setActiveActionPanel] = useState('');
  const [highlightedAction, setHighlightedAction] = useState('');
  const [databaseResult, setDatabaseResult] = useState(null);
  const [databaseManageOpen, setDatabaseManageOpen] = useState(false);

  const latestBackup = data?.last_backup || data?.latest_backup || null;
  const history = data?.backup_history || data?.available_restore_points || [];
  const repository = data?.repository || {};
  const latestBackupVerified = latestBackup?.verification_status === 'verified';
  const latestPreview = data?.latest_restore_preview || null;
  const latestPreviewReady = latestPreview?.status === 'ready';
  const lastRestore = data?.last_restore || null;
  const checkpoint = data?.pre_restore_checkpoint || null;
  const serviceRestart = lastRestore?.service_restart || {};
  const healthValidation = lastRestore?.health_validation || {};
  const restoreSucceeded = ['succeeded', 'succeeded_with_warnings'].includes(String(lastRestore?.status || '').toLowerCase());
  const recoveryFlow = useLiteRecoveryFlow({ recovery: data, latestBackup, latestPreview, backendReachable, savedStateOnly });
  const databaseProtection = data?.database_protection || {};
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

  const appBackups = Array.isArray(data?.app_backups)
    ? data.app_backups
    : Array.isArray(data?.app_backup_profiles?.apps)
      ? data.app_backup_profiles.apps
      : [];
  const lifecycleProfiles = Array.isArray(data?.app_lifecycle_profiles?.apps) ? data.app_lifecycle_profiles.apps : [];
  const lifecycleByApp = new Map(lifecycleProfiles.map((item) => [item.app_id, item]));
  const backupTargets = Array.isArray(data?.backup_targets) ? data.backup_targets : [];

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

  const confidencePills = [
    { label: repository?.encrypted ? 'Encrypted backup' : 'Local backup', state: repository?.ready ? 'ready' : 'waiting' },
    { label: latestBackupVerified ? 'Verified' : 'Needs verification', state: latestBackupVerified ? 'ready' : 'waiting' },
    { label: latestPreviewReady ? 'Preview ready' : 'Preview needed', state: latestPreviewReady ? 'ready' : 'waiting' },
    { label: healthValidation?.status === 'passed' ? 'Health passed' : 'Health pending', state: healthValidation?.status === 'passed' ? 'ready' : 'waiting' },
  ];

  const previewStats = [
    { label: 'Will restore', value: latestPreview?.change_count ?? lastRestore?.restored_file_count ?? '—' },
    { label: 'Skipped', value: lastRestore?.skipped_change_count ?? 0 },
    { label: 'Secrets', value: 'Excluded' },
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
        latestBackupVerified ? 'Restic snapshot lookup passed.' : 'Restic snapshot lookup will be checked.',
        latestBackupVerified ? 'Repository metadata check passed.' : 'Repository metadata will be checked.',
      ],
    },
    preview: {
      title: 'Preview Restore',
      subtitle: latestPreviewReady ? `${latestPreview?.change_count || 0} item(s) checked without changing local state.` : 'Pocket Lab will inspect the restore point safely.',
      next: 'Restore Latest',
      logs: [
        'Preview runs through the worker and does not restore files.',
        latestPreviewReady ? `${latestPreview?.change_count || 0} item(s) would be restored.` : 'Restore changes will be counted before restore is enabled.',
        latestPreviewReady ? `${latestPreview?.restic_item_count || 0} restic item(s) inspected.` : 'Encrypted repository contents will be inspected.',
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
    evidence: {
      title: 'Evidence',
      subtitle: evidenceItems.length ? 'Recovery IDs are ready to copy or inspect.' : 'Evidence will appear after backup activity.',
      next: 'Verify Backup',
      logs: evidenceItems.length
        ? evidenceItems.slice(0, 6).map((item) => `${item.label}: ${shortId(item.value)}`)
        : ['No evidence IDs are available yet. Create a backup first.'],
    },
  };

  const activePanel = actionPanelMeta[activeActionPanel] || null;

  function openActionPanel(action) {
    setActiveActionPanel(action);
    setHighlightedAction('');
  }

  function closeActionPanel() {
    setActiveActionPanel('');
  }

  const refreshRecovery = useCallback(() => refresh(), [refresh]);

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

  async function restoreDatabase() {
    if (!latestDatabaseBackup?.backup_id || !latestDatabasePreview?.preview_id || databaseWriteBlocked) return;
    const confirmed = window.confirm('Restore Pocket Lab to this verified database backup? Pocket Lab will enter maintenance and keep a rollback copy.');
    if (!confirmed) return;
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
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
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
      if (err.status === 501 && payload?.status === 'not_implemented') {
        setPreviewResult(payload);
      } else {
        setActionError(err.message);
      }
    } finally {
      setBusy('');
    }
  }

  async function verifyLatestBackup() {
    if (!latestBackup?.backup_id) return;
    const flowCheck = recoveryFlow.requestVerify();
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    openActionPanel('verify');
    setBusy('verify');
    setVerifyResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.verifyBackup(latestBackup.backup_id, { reason: 'manual verification' });
      recoveryFlow.verifyAccepted(payload);
      recoveryFlow.verified(payload);
      setVerifyResult(payload);
      setHighlightedAction('preview');
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
    openActionPanel('preview');
    setBusy('preview');
    setPreviewResult(null);
    setActionError(null);
    try {
      const payload = await liteApi.previewRestore({ backup_id: latestBackup.backup_id, reason: 'manual restore preview' });
      recoveryFlow.previewAccepted(payload);
      recoveryFlow.previewReady(payload);
      setPreviewResult(payload);
      setHighlightedAction('restore');
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function restoreLatestBackup() {
    if (!latestBackup?.backup_id || !latestPreview?.preview_id) return;
    const flowCheck = recoveryFlow.requestRestore({ verified: latestBackupVerified, previewReady: latestPreviewReady, explicitBackup: Boolean(latestBackup?.backup_id && latestBackup.backup_id !== 'latest') });
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    openActionPanel('restore');
    const confirmed = window.confirm('Restore will change local Lite state. Pocket Lab will create a checkpoint first. Continue?');
    if (!confirmed) { recoveryFlow.cancel(); return; }
    recoveryFlow.confirmRestore();
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
      setHighlightedAction('evidence');
      refreshRecovery();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Recovery"
        title="Backup & Restore"
        description="Create a safety copy before changes. Restore stays protected until backup checks and preview are ready."
        actions={<LiteRefreshButton scope="recovery" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <section className="lite-recovery-hero lite-recovery-hero-premium">
        <div className="lite-recovery-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {backendLabel(data?.status, {
              ready: 'Recovery Ready',
              review: 'Needs Attention',
              danger: 'Needs Attention',
              checking: 'Checking recovery',
            })}
          </div>
          <h2>{latestBackup ? 'You have a safe restore point.' : 'Create your first safe copy.'}</h2>
          <p>
            Pocket Lab backs up local Lite state into an encrypted restic repository and saves a clear evidence receipt.
          </p>
          <div className="lite-recovery-confidence-strip" aria-label="Recovery confidence">
            {confidencePills.map((pill) => (
              <span key={pill.label} className={`lite-recovery-confidence-pill lite-recovery-confidence-${pill.state}`}>
                {pill.label}
              </span>
            ))}
          </div>
          <div className="lite-recovery-actions">
            <LiteButton onClick={backup} disabled={busy === 'backup' || recoveryFlow.writeBlocked}>
              {busy === 'backup' ? 'Starting backup...' : recoveryFlow.writeBlocked ? 'Reconnect to continue' : 'Backup Now'}
            </LiteButton>
            <LiteRefreshButton scope="recovery" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />
          </div>
          <LiteFlowStatusPanel title="Backup & Restore" label={recoveryFlow.label} steps={recoveryFlow.steps} note={recoveryFlow.writeBlocked ? recoveryFlow.blockedReason : 'Backup, verify, preview, and restore stay backend-owned.'} className="mt-4" />
        </div>

        <div className="lite-recovery-status-card lite-recovery-confidence-card">
          <div className="lite-recovery-icon">
            <Database className="h-7 w-7" />
          </div>
          <span>Last backup</span>
          <strong>{latestBackup?.created_at ? formatLiteTime(latestBackup.created_at) : 'None yet'}</strong>
          <StatusBadge status={backendBadgeStatus(data?.status)}>
            {latestBackup ? 'Safe restore point' : backendLabel(data?.status, {
              ready: 'Recovery Ready',
              review: 'Needs Attention',
              danger: 'Needs Attention',
              checking: 'Checking',
            })}
          </StatusBadge>
          <div className="lite-recovery-confidence-meter" aria-hidden="true">
            <span style={{ width: `${restoreSteps.filter((step) => step.complete).length * 20}%` }} />
          </div>
        </div>
      </section>

      <section className="lite-recovery-database-section" aria-label="Database protection">
        <GlassCard className="lite-recovery-card lite-recovery-database-card">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon">
              <Database className="h-5 w-5" />
            </div>
            <StatusBadge status={databaseMaintenance?.active ? 'checking' : databaseBackupVerified ? 'healthy' : 'review'}>
              {databaseMaintenance?.active ? 'Maintenance in progress' : databaseBackupVerified ? 'Database backup verified' : 'Database backup needed'}
            </StatusBadge>
          </div>
          <div className="lite-recovery-database-copy">
            <span>Database protection</span>
            <h2>{databaseRestoreGuard?.rollback_failed ? 'Recovery needs attention' : databaseMaintenance?.active || activeDatabaseRestore ? 'Pocket Lab is recovering safely' : databaseProtection?.summary || 'Protect Pocket Lab state'}</h2>
            <p>Creates a consistent SQLite online backup, validates integrity and migrations, and keeps rollback available for confirmed restore.</p>
          </div>
          <div className="lite-recovery-database-facts">
            <div><span>Latest backup</span><strong>{latestDatabaseBackup?.created_at ? formatLiteTime(latestDatabaseBackup.created_at) : 'None yet'}</strong></div>
            <div><span>Verification</span><strong>{databaseBackupVerified ? 'Verified' : 'Not verified'}</strong></div>
            <div><span>Backup size</span><strong>{latestDatabaseBackup?.size_bytes ? `${Math.max(1, Math.round(latestDatabaseBackup.size_bytes / 1024))} KB` : 'Not available'}</strong></div>
            <div><span>Restore preview</span><strong>{databasePreviewReady ? 'Ready' : 'Not ready'}</strong></div>
            <div><span>Rollback</span><strong>{databaseProtection?.rollback_available || databaseRestore?.rollback_available ? 'Available' : 'Created during restore'}</strong></div>
            <div><span>Maintenance</span><strong>{databaseRestoreGuard?.rollback_failed ? 'Blocked for safety' : databaseMaintenance?.active || activeDatabaseRestore ? 'In progress' : 'Ready'}</strong></div>
          </div>
          <div className="lite-recovery-database-actions">
            <LiteButton onClick={backUpDatabase} disabled={databaseWriteBlocked || busy === 'database-backup'}>
              {busy === 'database-backup' ? 'Starting backup…' : 'Back Up Pocket Lab'}
            </LiteButton>
            <LiteButton tone="secondary" onClick={() => setDatabaseManageOpen(true)}>
              Manage
            </LiteButton>
          </div>
        </GlassCard>
      </section>

      <LiteSheet
        open={databaseManageOpen}
        onClose={() => setDatabaseManageOpen(false)}
        title="Database protection"
        eyebrow="Manage"
        description="Back up, verify, preview, and restore Pocket Lab through the backend-owned recovery flow."
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
            onRestore={restoreDatabase}
          />
        </React.Suspense>
      </LiteSheet>

      <section className="lite-recovery-app-profiles lite-recovery-backup-targets" aria-label="Backup targets">
        <div className="lite-recovery-section-heading">
          <div>
            <span>Backup targets</span>
            <h2>Save to storage device</h2>
            <p>Joined Storage Node devices can become app backup targets when they are online and ready.</p>
          </div>
        </div>
        {backupTargets.length ? (
          <div className="lite-recovery-target-grid">
            {backupTargets.map((target) => (
              <div className="lite-recovery-target-card" key={target.device_id || target.name}>
                <strong>{target.name || 'Storage Phone'}</strong>
                <em>{target.ready ? 'Backup Target · Ready' : target.reason || 'Backup target needs attention'}</em>
                <span>{target.ready ? 'Used for app backups' : 'Not used for app backups yet'}</span>
                {target.available_gb ? <span>{target.available_gb} GB available</span> : null}
              </div>
            ))}
          </div>
        ) : (
          <StateSurface tone="empty" title="No backup target yet" description="Join a storage device to save app backups elsewhere." />
        )}
      </section>

      <section className="lite-recovery-app-profiles" aria-label="App backups">
        <div className="lite-recovery-section-heading">
          <div>
            <span>App backups</span>
            <h2>Protect self-hosted apps</h2>
            <p>PhotoPrism app backups keep config and Pocket Lab metadata separate from large media files.</p>
          </div>
        </div>
        {appBackups.length ? (
          <div className="lite-recovery-app-grid">
            {appBackups.map((app) => {
              const lifecycle = lifecycleByApp.get(app.app_id) || app.lifecycle;
              return (
              <GlassCard key={app.app_id || app.name} className="lite-recovery-card lite-recovery-app-card">
                <div className="lite-recovery-card-head">
                  <div className="lite-recovery-mini-icon">
                    <FileCheck className="h-5 w-5" />
                  </div>
                  <StatusBadge status={backendBadgeStatus(app.status)}>{backendLabel(app.status, { ready: 'Backup ready', review: 'Needs attention', danger: 'Needs attention', checking: 'Checking' })}</StatusBadge>
                </div>
                <h3>{app.name || 'Self-hosted app'}</h3>
                <p>{app.summary || 'App backup profile is available.'}</p>
                {lifecycle ? (
                  <div className="lite-recovery-app-lifecycle">
                    <span>{lifecycle?.host_device?.label || 'Runs on Server Phone'}</span>
                    <span>{lifecycle?.storage?.mapping_count > 0 ? 'Media connected' : 'Media not connected'}</span>
                    <span>{lifecycle?.media?.last_indexed_at ? `Last indexed ${formatLiteTime(lifecycle.media.last_indexed_at)}` : lifecycle?.media?.summary || 'Last indexed not available yet'}</span>
                    <span>{lifecycle?.backup?.summary || 'Backup ready'}</span>
                  </div>
                ) : null}
                <div className="lite-recovery-app-facts">
                  <span><strong>Config protected</strong><em>{(app.included || []).slice(0, 3).join(' · ') || 'App metadata'}</em></span>
                  <span><strong>Media excluded</strong><em>{app?.media?.summary || 'Media can be large. Add media backup when a storage device is ready.'}</em></span>
                  <span><strong>Backup target</strong><em>{app?.backup_target?.label || 'No backup target yet'}</em></span>
                  <span><strong>Back up to storage device</strong><em>{app?.backup_target?.target_label ? `Saved to ${app.backup_target.target_label}` : app?.backup_target?.summary || 'Saved to Storage Phone after a backup target is ready.'}</em></span>
                </div>
                <div className="lite-recovery-app-tags">
                  {(app.excluded || []).slice(0, 4).map((item) => <span key={item}>{item}</span>)}
                </div>
                <div className="lite-recovery-app-actions">
                  <LiteButton onClick={() => backUpApp(app)} disabled={Boolean(busy)}>{busy === `app-backup:${app.app_id}` ? 'Starting backup...' : 'Back up app'}</LiteButton>
                  <LiteButton tone="secondary" onClick={() => previewAppRestore(app)} disabled={Boolean(busy)}>Preview restore</LiteButton>
                </div>
                <p className="lite-recovery-app-note">{app?.evidence?.summary || 'Evidence appears after an app backup.'}</p>
              </GlassCard>
              );
            })}
          </div>
        ) : (
          <StateSurface
            tone="empty"
            title="No app backups yet"
            description="Install an app from Apps to protect it here."
          />
        )}
      </section>

      <GlassCard className="lite-recovery-card lite-recovery-timeline-card">
        <div className="lite-recovery-card-head">
          <div>
            <h2>Restore readiness</h2>
            <p>Follow each safety step before restoring local state.</p>
          </div>
          <StatusBadge status={restoreSucceeded ? 'healthy' : latestPreviewReady ? 'degraded' : 'unknown'}>
            {restoreSucceeded ? 'Restored' : latestPreviewReady ? 'Ready to restore' : 'In progress'}
          </StatusBadge>
        </div>
        <div className="lite-recovery-timeline">
          {restoreSteps.map((step, index) => (
            <div key={step.key} className={`lite-recovery-step ${step.complete ? 'lite-recovery-step-complete' : ''}`}>
              <div className="lite-recovery-step-dot">{step.complete ? '✓' : index + 1}</div>
              <strong>{step.label}</strong>
              <span>{step.detail}</span>
            </div>
          ))}
        </div>
      </GlassCard>

      {loading ? <LoadingCard label="Loading recovery..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Recovery needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      {actionError ? (
        <StateSurface
          tone="degraded"
          title="Recovery action needs attention"
          description={actionError}
          className="mb-5"
        />
      ) : null}

      {databaseResult ? (
        <StateSurface
          tone={databaseResult.status === 'failed' || databaseResult.phase === 'rollback_failed' ? 'degraded' : 'healthy'}
          title={databaseResult.phase === 'rollback_failed' ? 'Recovery needs attention' : databaseResult.status === 'failed' ? 'Restore failed safely' : 'Database protection queued'}
          description={databaseResult.summary || 'Pocket Lab is running the database recovery action in the worker.'}
          className="mb-5"
        />
      ) : null}

      {verifyResult ? (
        <StateSurface
          tone="healthy"
          title="Backup verification queued"
          description={verifyResult.summary || 'Pocket Lab is checking the backup evidence and repository metadata.'}
          className="mb-5"
        />
      ) : null}

      {previewResult ? (
        <StateSurface
          tone="healthy"
          title="Restore preview queued"
          description={previewResult.summary || 'Pocket Lab is preparing a restore preview without changing local state.'}
          className="mb-5"
        />
      ) : null}

      {restoreResult ? (
        <StateSurface
          tone="healthy"
          title="Restore queued"
          description={restoreResult.summary || 'Pocket Lab will create a checkpoint before applying the restore.'}
          className="mb-5"
        />
      ) : null}

      <div className="lite-recovery-grid">
        <GlassCard className="lite-recovery-card lite-recovery-backup-card">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon">
              <Database className="h-5 w-5" />
            </div>
            <StatusBadge status={repository?.ready ? 'healthy' : backendBadgeStatus(data?.status)}>
              {repository?.ready ? 'Repository ready' : 'Needs Attention'}
            </StatusBadge>
          </div>

          <h2>Backup status</h2>
          <p>{data?.summary || 'Pocket Lab is checking whether backups are ready.'}</p>

          <div className="lite-recovery-facts">
            <div>
              <span>Stored in</span>
              <strong>{repository?.location || 'Local backup folder'}</strong>
            </div>
            <div>
              <span>Engine</span>
              <strong>{repository?.engine || 'restic'}</strong>
            </div>
            <div>
              <span>Last check</span>
              <strong>{data?.updated_at ? formatLiteTime(data.updated_at) : 'Not available yet'}</strong>
            </div>
            <div>
              <span>Last verification</span>
              <strong>{data?.last_verification_result || 'Not verified yet'}</strong>
            </div>
          </div>

          <div className="mt-5">
            <LiteButton onClick={backup} disabled={busy === 'backup'}>
              {busy === 'backup' ? 'Starting backup...' : 'Backup Now'}
            </LiteButton>
          </div>
        </GlassCard>

        <GlassCard className="lite-recovery-card">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-recovery-warning-badge">Evidence saved</span>
          </div>

          <h2>What is protected</h2>
          <p>Pocket Lab saves the Lite state needed to recover devices, app metadata, rules, and evidence.</p>

          <div className="lite-recovery-checklist">
            {(data?.what_will_be_backed_up || []).slice(0, 6).map((item) => (
              <div key={item}>
                <span className="lite-recovery-dot" />
                {item}
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <div className="lite-recovery-grid mt-4">
        <GlassCard className="lite-recovery-card">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon lite-recovery-mini-icon-warning">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <span className="lite-recovery-warning-badge">Secrets excluded</span>
          </div>
          <h2>What is not backed up</h2>
          <p>Raw secrets are not saved by default. A separate encrypted secret recovery bundle can be added later only with clear confirmation.</p>
          <div className="lite-recovery-checklist">
            {(data?.what_will_not_be_backed_up || []).slice(0, 6).map((item) => (
              <div key={item}>
                <span className="lite-recovery-dot lite-recovery-dot-warning" />
                {item}
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard className="lite-recovery-card lite-recovery-restore-card lite-recovery-restore-cockpit">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon lite-recovery-mini-icon-warning">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-recovery-warning-badge">Protected</span>
          </div>

          <h2>Restore Latest</h2>
          <p>
            Verify the backup, preview what would change, then restore only after clear confirmation.
          </p>

          <div className={`lite-recovery-flip-shell ${activePanel ? 'is-flipped' : ''}`}>
            <div className="lite-recovery-flip-inner">
              <div className="lite-recovery-flip-face lite-recovery-flip-front" data-active-panel={Boolean(activePanel)}>
                <div className="lite-recovery-restore-chips">
                  <span className={latestBackupVerified ? 'is-ready' : ''}>Verified</span>
                  <span className={latestPreviewReady ? 'is-ready' : ''}>Preview ready</span>
                  <span className={checkpoint?.checkpoint_id ? 'is-ready' : ''}>Checkpoint saved</span>
                  <span className={healthValidation?.status === 'passed' ? 'is-ready' : ''}>Health passed</span>
                </div>

                <div className="lite-recovery-preview-stats">
                  {previewStats.map((stat) => (
                    <div key={stat.label}>
                      <span>{stat.label}</span>
                      <strong>{stat.value}</strong>
                    </div>
                  ))}
                </div>

                <div className="lite-recovery-warning-note lite-recovery-safety-panel">
                  <strong>{latestBackupVerified ? 'Backup verified' : 'Verification required'}</strong>
                  <span>{latestPreview ? `Latest preview checks ${latestPreview.change_count || 0} item(s).` : 'Pocket Lab will check the backup and show what changes before restoring.'}</span>
                  {checkpoint?.checkpoint_id ? <span>Checkpoint: {shortId(checkpoint.checkpoint_id)}</span> : null}
                  {lastRestore?.status ? <span>Last restore: {lastRestore.status}</span> : null}
                  {serviceRestart?.status ? <span>Service restart: {serviceRestart.status}</span> : null}
                  {healthValidation?.status ? <span>Health: {healthValidation.status}</span> : null}
                </div>

                {lastRestore?.restore_id ? (
                  <div className="lite-recovery-last-restore-card">
                    <span>Last restore</span>
                    <strong>{lastRestore.status || 'Unknown'}</strong>
                    <p>{lastRestore.summary || `${lastRestore.restored_file_count || 0} file(s) restored.`}</p>
                  </div>
                ) : null}
              </div>

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
                    savedStateOnly={savedStateOnly}
                    evidenceItems={evidenceItems}
                    onClose={closeActionPanel}
                    onOpenEvidence={() => setEvidenceOpen(true)}
                  />
                </React.Suspense>
              ) : null}
            </div>
          </div>

          <div className="lite-recovery-action-buttons">
            <span className={highlightedAction === 'verify' ? 'lite-recovery-next-action' : ''}>
              <LiteButton disabled={!latestBackup || busy === 'verify'} tone="secondary" onClick={verifyLatestBackup}>
                {busy === 'verify' ? 'Verifying evidence...' : 'Verify Backup'}
              </LiteButton>
            </span>
            <span className={highlightedAction === 'preview' ? 'lite-recovery-next-action' : ''}>
              <LiteButton disabled={!latestBackup || busy === 'preview'} tone="secondary" onClick={previewLatestRestore}>
                {busy === 'preview' ? 'Preparing preview...' : 'Preview Restore'}
              </LiteButton>
            </span>
            <span className={highlightedAction === 'restore' ? 'lite-recovery-next-action' : ''}>
              <LiteButton disabled={!latestBackupVerified || !latestPreviewReady || busy === 'restore'} tone="danger" onClick={restoreLatestBackup}>
                {busy === 'restore' ? 'Creating checkpoint...' : 'Restore Latest'}
              </LiteButton>
            </span>
            <span className={highlightedAction === 'evidence' ? 'lite-recovery-next-action' : ''}>
              <LiteButton disabled={!evidenceItems.length} tone="secondary" onClick={() => openActionPanel('evidence')}>
                Evidence
              </LiteButton>
            </span>
          </div>
        </GlassCard>
      </div>

      <React.Suspense fallback={<div className="lite-recovery-history-loading">Loading backup history…</div>}>
        <RecoveryBackupHistory history={history} latestPreviewReady={latestPreviewReady} savedStateOnly={savedStateOnly} />
      </React.Suspense>

      {evidenceOpen ? (
        <div className="lite-recovery-evidence-backdrop" role="presentation" onClick={() => setEvidenceOpen(false)}>
          <aside className="lite-recovery-evidence-drawer" role="dialog" aria-label="Recovery evidence" onClick={(event) => event.stopPropagation()}>
            <div className="lite-recovery-evidence-head">
              <div>
                <span>Evidence</span>
                <h2>Recovery details</h2>
                <p>IDs are shortened here. Copy a value to inspect logs or evidence.</p>
              </div>
              <button type="button" onClick={() => setEvidenceOpen(false)} aria-label="Close evidence details">×</button>
            </div>
            <div className="lite-recovery-evidence-list">
              {evidenceItems.map((item) => (
                <div key={item.label} className="lite-recovery-evidence-item">
                  <span>{item.label}</span>
                  <strong>{shortId(item.value)}</strong>
                  <button type="button" onClick={() => copyEvidence(item.value, item.label)}>
                    <Copy className="h-4 w-4" />
                    {copiedEvidence === item.label ? 'Copied' : 'Copy'}
                  </button>
                </div>
              ))}
            </div>
          </aside>
        </div>
      ) : null}

      <ResultNotice result={backupResult} error={actionError} />
    </>
  );
}
