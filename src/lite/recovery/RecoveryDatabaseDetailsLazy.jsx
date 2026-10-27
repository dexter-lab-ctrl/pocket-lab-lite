import React from 'react';
import { formatLiteTime } from '../../lib/liteApi.js';
import { friendlyLiteText } from '../../lib/liteUxPresentation.js';
import { LiteButton, StatusBadge } from '../LiteUi.jsx';

const RESTORE_PHASE_LABELS = {
  created: 'Preparing restore',
  checkpointing: 'Creating checkpoint',
  checkpoint_ready: 'Checkpoint saved',
  staging: 'Preparing backup',
  staged: 'Backup staged',
  validating_staged: 'Checking backup',
  ready_to_promote: 'Ready to restore',
  promoting: 'Restoring Pocket Lab',
  validating_active: 'Checking restored data',
  committed: 'Restore committed',
  rollback_started: 'Rolling back safely',
  rollback_validating: 'Checking recovered state',
  rolled_back: 'Rolled back — restore not committed',
  rollback_failed: 'Rollback failed — attention required',
};

function restorePhaseLabel(phase = '') {
  return RESTORE_PHASE_LABELS[String(phase || '').toLowerCase()] || 'State not reported';
}

function backupLabel(backup) {
  if (!backup) return 'No verified database backup yet.';
  const state = backup.verification_status === 'verified' ? 'Verified' : 'Not verified';
  const when = backup.created_at ? formatLiteTime(backup.created_at) : 'Time unavailable';
  return `${state} · ${when}`;
}

function DatabaseRestoreTimeline({ restoreState, currentPhase }) {
  // A phase is marked confirmed only when a backend stage record exists.
  const observed = Array.isArray(restoreState?.stage_history) ? restoreState.stage_history
    : Array.isArray(restoreState?.timeline) ? restoreState.timeline : [];
  const stages = observed
    .map((entry, index) => {
      const phase = String(typeof entry === 'string' ? entry : entry?.phase || entry?.stage || '').toLowerCase();
      return Object.hasOwn(RESTORE_PHASE_LABELS, phase) ? {
        id: String(typeof entry === 'string' ? index : entry?.id || index),
        label: restorePhaseLabel(phase), phase,
        state: String(typeof entry === 'string' ? 'recorded' : entry?.status || 'recorded').toLowerCase(),
      } : null;
    }).filter(Boolean);
  if (currentPhase && Object.hasOwn(RESTORE_PHASE_LABELS, currentPhase)
    && !stages.some((stage) => stage.phase === currentPhase)) {
    stages.push({ id: 'current', label: restorePhaseLabel(currentPhase), phase: currentPhase, state: 'current' });
  }
  return (
    <section className="lite-recovery-database-stage-section" aria-label="Database recovery progress">
      <span>Recovery stages</span>
      <h3>Backend-reported progress</h3>
      {stages.length ? (
        <ol className="lite-recovery-database-stage-timeline">
          {stages.map((stage) => (
            <li key={stage.id} data-recovery-database-stage={stage.phase}
              data-state={stage.state} aria-current={stage.phase === currentPhase ? 'step' : undefined}>
              <strong>{stage.label}</strong>
              <small>{stage.state === 'current' ? 'Current reported stage'
                : stage.state === 'completed' || stage.state === 'succeeded' ? 'Confirmed by backend'
                  : 'Reported: ' + stage.state.replace(/_/g, ' ')}</small>
            </li>
          ))}
        </ol>
      ) : <p>No restore stage has been reported. A backup record is not a running restore.</p>}
      <p>There is no estimated percentage. Rollback is a recovery outcome, not a successful restore.</p>
    </section>
  );
}

export default function RecoveryDatabaseDetailsLazy({
  databaseProtection = {},
  latestBackup = null,
  latestPreview = null,
  lastRestore = null,
  maintenance = {},
  restoreGuard = {},
  activeRestore = null,
  writeBlocked = false,
  busy = '',
  onBackup,
  onVerify,
  onPreview,
  onRestore,
}) {
  const history = Array.isArray(databaseProtection.backup_history)
    ? databaseProtection.backup_history.slice(0, 10)
    : [];
  const verified = latestBackup?.verification_status === 'verified';
  const previewReady = Boolean(verified && latestBackup?.backup_id && latestPreview?.preview_id
    && latestPreview.backup_id === latestBackup.backup_id
    && latestPreview.status === 'ready' && latestPreview.restore_allowed !== false);
  const rollbackAvailable = Boolean(databaseProtection.rollback_available || lastRestore?.rollback_available);
  const restoreState = activeRestore || lastRestore || {};
  const reportedPhase = String(restoreGuard?.phase || restoreState?.phase || restoreState?.terminal_status || '').toLowerCase();
  const restorePhase = Object.hasOwn(RESTORE_PHASE_LABELS, reportedPhase) ? reportedPhase : '';
  const recoveryBlocked = restoreGuard?.rollback_failed === true || restorePhase === 'rollback_failed';
  const maintenanceStatusLabel = restorePhase
    ? restorePhaseLabel(restorePhase)
    : 'Maintenance in progress';

  return (
    <div className="lite-recovery-database-manage-content" data-recovery-s8-lazy-details="true">
      <section>
        <div className="lite-recovery-database-manage-heading">
          <div>
            <span>Overview</span>
            <h3>{recoveryBlocked ? 'Recovery needs attention' : maintenance?.active || activeRestore ? maintenanceStatusLabel : friendlyLiteText(databaseProtection.summary, 'Database protection is ready.')}</h3>
          </div>
          <StatusBadge status={recoveryBlocked ? 'danger' : maintenance?.active || activeRestore ? 'checking' : verified ? 'healthy' : 'review'}>
            {recoveryBlocked ? 'Blocked for safety' : maintenance?.active || activeRestore ? maintenanceStatusLabel : verified ? 'Backup verified' : 'Backup needed'}
          </StatusBadge>
        </div>
        <p>Pocket Lab coordinates recovery operations. Actions are paused while the device is offline or database maintenance is in progress.</p>
        <div className="lite-recovery-database-manage-actions">
          <LiteButton onClick={onBackup} disabled={writeBlocked || busy === 'database-backup'}>
            {busy === 'database-backup' ? 'Starting backup…' : 'Back Up Pocket Lab'}
          </LiteButton>
          <LiteButton tone="secondary" onClick={onVerify} disabled={!latestBackup || writeBlocked || busy === 'database-verify'}>
            {busy === 'database-verify' ? 'Checking…' : 'Verify backup'}
          </LiteButton>
          <LiteButton tone="secondary" onClick={onPreview} disabled={!verified || writeBlocked || busy === 'database-preview'}>
            {busy === 'database-preview' ? 'Preparing…' : 'Preview restore'}
          </LiteButton>
          <LiteButton tone="danger" onClick={onRestore} disabled={!verified || !previewReady || writeBlocked || busy === 'database-restore'}>
            {busy === 'database-restore' ? 'Entering maintenance…' : 'Restore Pocket Lab'}
          </LiteButton>
        </div>
      </section>

      <section>
        <span>Database backups</span>
        <h3>Verified restore points</h3>
        {history.length ? (
          <div className="lite-recovery-database-history">
            {history.map((backup) => (
              <article key={backup.backup_id}>
                <strong>{backupLabel(backup)}</strong>
                <small>{backup.size_bytes ? `${Math.max(1, Math.round(backup.size_bytes / 1024))} KB` : 'Size unavailable'}</small>
              </article>
            ))}
          </div>
        ) : <p>No database backup history yet.</p>}
      </section>

      <section>
        <span>Verification</span>
        <h3>{verified ? 'Backup verified' : 'Verification required'}</h3>
        <p>{friendlyLiteText(latestBackup?.summary, 'A backup is marked ready only after integrity and migration checks pass.')}</p>
      </section>

      <section>
        <span>Restore preview</span>
        <h3>{previewReady ? 'Preview ready' : 'Preview needed'}</h3>
        <p>{friendlyLiteText(latestPreview?.summary, 'Preview restore checks the selected backup without replacing the live data.')}</p>
      </section>

      <DatabaseRestoreTimeline restoreState={restoreState} currentPhase={restorePhase} />

      <section>
        <span>Restore</span>
        <h3>{restorePhase ? restorePhaseLabel(restorePhase) : lastRestore?.status === 'completed' ? 'Backend reports restore completed' : 'Confirmation required'}</h3>
        <p>{friendlyLiteText(restoreState?.summary, 'Restore checkpoints current state, validates the backup, and rolls back automatically on failure.')}</p>
        <strong>{rollbackAvailable ? 'Rollback available' : 'Rollback is created during restore'}</strong>
      </section>

      <section>
        <span>Maintenance</span>
        <h3>{recoveryBlocked ? 'Writers blocked for safety' : maintenance?.active || activeRestore ? maintenanceStatusLabel : 'Ready'}</h3>
        <p>{friendlyLiteText(restoreGuard?.summary || maintenance?.summary, 'Recovery actions remain paused while protected data maintenance is safely completed.')}</p>
      </section>

      <section>
        <span>History</span>
        <h3>Latest database recovery</h3>
        <p>{lastRestore?.started_at ? `${lastRestore.state || lastRestore.status || 'Recorded'} · ${formatLiteTime(lastRestore.started_at)}` : 'No database restore has been recorded.'}</p>
      </section>

      <section className="lite-recovery-database-technical">
        <span>Technical details</span>
        <h3>Sanitized diagnostics</h3>
        <dl>
          <div><dt>Journal mode</dt><dd>{databaseProtection?.wal?.journal_mode || 'Checking'}</dd></div>
          <div><dt>Last passive maintenance</dt><dd>{databaseProtection?.wal?.last_passive_checkpoint_at ? formatLiteTime(databaseProtection.wal.last_passive_checkpoint_at) : 'Not run yet'}</dd></div>
          <div><dt>Schema version</dt><dd>{latestBackup?.schema_version || 'Not available'}</dd></div>
          <div><dt>Restore transaction</dt><dd>{restorePhase ? restorePhaseLabel(restorePhase) : 'Ready'}</dd></div>
          <div><dt>Restart allowed</dt><dd>{restoreGuard?.unresolved ? (restoreGuard?.api_worker_restart_allowed ? 'Yes' : 'No') : 'Yes'}</dd></div>
          <div><dt>Evidence-file policy</dt><dd>Never deleted automatically</dd></div>
        </dl>
      </section>
    </div>
  );
}
