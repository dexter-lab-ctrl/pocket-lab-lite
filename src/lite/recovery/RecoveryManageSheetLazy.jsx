import React from 'react';
import {
  ArchiveRestore,
  CheckCircle2,
  Database,
  FileCheck,
  HardDrive,
  RotateCcw,
  ShieldCheck,
} from 'lucide-react';
import { formatLiteTime } from '../../lib/liteApi.js';
import { LiteButton, LoadingCard, StateSurface, StatusBadge } from '../LiteUi.jsx';

const RecoveryBackupHistory = React.lazy(() => import('./RecoveryBackupHistory.jsx'));

export const RECOVERY_MANAGE_SECTIONS = [
  { id: 'backup', label: 'Backup' },
  { id: 'restore', label: 'Restore' },
  { id: 'protection', label: 'Protection' },
  { id: 'history', label: 'History' },
];

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (!value) return 'Size unavailable';
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(value >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
  return `${Math.max(1, Math.round(value / 1024))} KB`;
}

function RecoveryActionRow({
  icon: Icon,
  title,
  description,
  status,
  statusTone = 'unknown',
  actionLabel,
  busyLabel,
  busy = false,
  disabled = false,
  tone = 'secondary',
  onAction,
  detailsLabel = 'Details',
  onDetails,
  children,
}) {
  return (
    <article className={`lite-recovery-manage-action-row ${busy ? 'is-active' : ''}`.trim()}>
      <div className="lite-recovery-manage-action-icon" aria-hidden="true">
        <Icon className="h-5 w-5" />
      </div>
      <div className="lite-recovery-manage-action-copy">
        <div className="lite-recovery-manage-action-title">
          <strong>{title}</strong>
          {status ? <StatusBadge status={statusTone}>{status}</StatusBadge> : null}
        </div>
        <p>{description}</p>
        {children}
      </div>
      <div className="lite-recovery-manage-action-buttons">
        {onDetails ? (
          <LiteButton tone="secondary" onClick={onDetails} ariaLabel={`${detailsLabel}: ${title}`}>
            {detailsLabel}
          </LiteButton>
        ) : null}
        {onAction ? (
          <LiteButton tone={tone} onClick={onAction} disabled={disabled || busy}>
            {busy ? busyLabel || 'Working…' : actionLabel}
          </LiteButton>
        ) : null}
      </div>
    </article>
  );
}

function SectionHeading({ eyebrow, title, description }) {
  return (
    <div className="lite-recovery-manage-section-heading">
      <span>{eyebrow}</span>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

export default function RecoveryManageSheetLazy({
  section = 'backup',
  onSectionChange,
  latestBackup = null,
  latestPreview = null,
  lastRestore = null,
  checkpoint = null,
  repository = {},
  history = [],
  savedStateOnly = false,
  latestBackupVerified = false,
  latestPreviewReady = false,
  restoreSucceeded = false,
  databaseProtection = {},
  latestDatabaseBackup = null,
  databaseBackupVerified = false,
  databasePreviewReady = false,
  databaseMaintenance = {},
  databaseWriteBlocked = false,
  appBackups = [],
  lifecycleByApp = new Map(),
  backupTargets = [],
  protectedItems = [],
  excludedItems = [],
  busy = '',
  onBackup,
  onVerify,
  onPreview,
  onRestore,
  onDatabaseBackup,
  onOpenDatabaseDetails,
  onBackUpApp,
  onPreviewAppRestore,
  onOpenActionDetails,
  onOpenEvidence,
  detailsLoading = false,
  detailsError = '',
  onRetryDetails,
}) {
  const activeSection = RECOVERY_MANAGE_SECTIONS.some((item) => item.id === section) ? section : 'backup';
  const recentHistory = (Array.isArray(history) ? history : []).slice(0, 3);
  const tabRefs = React.useRef([]);
  const onTabKeyDown = (event, index) => {
    const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
    if (!keys.includes(event.key)) return;
    event.preventDefault();
    const lastIndex = RECOVERY_MANAGE_SECTIONS.length - 1;
    const nextIndex = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? lastIndex
        : event.key === 'ArrowRight'
          ? (index + 1) % RECOVERY_MANAGE_SECTIONS.length
          : (index - 1 + RECOVERY_MANAGE_SECTIONS.length) % RECOVERY_MANAGE_SECTIONS.length;
    const next = RECOVERY_MANAGE_SECTIONS[nextIndex];
    onSectionChange(next.id);
    tabRefs.current[nextIndex]?.focus?.({ preventScroll: true });
  };

  return (
    <div className="lite-recovery-manage-content" data-recovery-r1-r2-manage="true">
      <div className="lite-recovery-manage-tabs" role="tablist" aria-label="Recovery management sections">
        {RECOVERY_MANAGE_SECTIONS.map((item, index) => (
          <button
            key={item.id}
            ref={(node) => { tabRefs.current[index] = node; }}
            id={`recovery-manage-tab-${item.id}`}
            type="button"
            role="tab"
            aria-selected={activeSection === item.id}
            aria-controls={`recovery-manage-panel-${item.id}`}
            tabIndex={activeSection === item.id ? 0 : -1}
            className={activeSection === item.id ? 'is-active' : ''}
            onClick={() => onSectionChange(item.id)}
            onKeyDown={(event) => onTabKeyDown(event, index)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {detailsLoading ? <LoadingCard label="Loading recovery workspace…" /> : null}
      {detailsError ? (
        <StateSurface tone="degraded" title="Recovery information is temporarily unavailable" description={detailsError}>
          {onRetryDetails ? <LiteButton tone="secondary" onClick={onRetryDetails}>Retry</LiteButton> : null}
        </StateSurface>
      ) : null}

      {activeSection === 'backup' ? (
        <section id="recovery-manage-panel-backup" className="lite-recovery-manage-section" role="tabpanel" aria-labelledby="recovery-manage-tab-backup" tabIndex={0}>
          <SectionHeading eyebrow="Backup" title="Create and manage restore points" description="Create verified restore points for Pocket Lab Lite, its database, and supported apps." />
          <div className="lite-recovery-manage-action-list">
            <RecoveryActionRow
              icon={ArchiveRestore}
              title="Back up Lite state"
              description={latestBackup?.created_at ? `Last saved ${formatLiteTime(latestBackup.created_at)}.` : 'Create the first encrypted Lite restore point.'}
              status={latestBackupVerified ? 'Verified' : latestBackup ? 'Saved' : 'Not created'}
              statusTone={latestBackupVerified ? 'healthy' : latestBackup ? 'review' : 'unknown'}
              actionLabel="Back Up Now"
              busyLabel="Starting backup…"
              busy={busy === 'backup'}
              disabled={Boolean(busy) || databaseWriteBlocked}
              onAction={onBackup}
            />
            <RecoveryActionRow
              icon={Database}
              title="Back Up Pocket Lab"
              description={latestDatabaseBackup?.created_at ? `${formatSize(latestDatabaseBackup.size_bytes)} · ${formatLiteTime(latestDatabaseBackup.created_at)}` : 'Create a consistent SQLite online backup.'}
              status={databaseMaintenance?.active ? 'Working' : databaseBackupVerified ? 'Verified' : 'Backup needed'}
              statusTone={databaseMaintenance?.active ? 'checking' : databaseBackupVerified ? 'healthy' : 'review'}
              actionLabel="Back Up"
              busyLabel="Starting backup…"
              busy={busy === 'database-backup'}
              disabled={Boolean(busy) || databaseWriteBlocked}
              onAction={onDatabaseBackup}
              onDetails={onOpenDatabaseDetails}
            />
          </div>

          {backupTargets.length ? (
            <div className="lite-recovery-manage-subsection">
              <strong>Backup targets</strong>
              <div className="lite-recovery-manage-compact-list">
                {backupTargets.slice(0, 4).map((target) => (
                  <div key={target.device_id || target.name}>
                    <HardDrive className="h-4 w-4" />
                    <span><strong>{target.name || 'Storage Phone'}</strong><small>{target.ready ? 'Ready for app backups' : target.reason || 'Needs attention'}</small></span>
                    <StatusBadge status={target.ready ? 'healthy' : 'review'}>{target.ready ? 'Ready' : 'Waiting'}</StatusBadge>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {appBackups.length ? (
            <div className="lite-recovery-manage-subsection">
              <strong>App backups</strong>
              <div className="lite-recovery-manage-app-list">
                {appBackups.map((app) => {
                  const lifecycle = lifecycleByApp.get(app.app_id) || app.lifecycle || {};
                  return (
                    <article key={app.app_id || app.name}>
                      <div>
                        <strong>{app.name || 'Self-hosted app'}</strong>
                        <span>{lifecycle?.backup?.summary || app.summary || 'App backup profile is ready.'}</span>
                      </div>
                      <div>
                        <LiteButton tone="secondary" onClick={() => onPreviewAppRestore(app)} disabled={Boolean(busy)}>Preview</LiteButton>
                        <LiteButton onClick={() => onBackUpApp(app)} disabled={Boolean(busy)}>
                          {busy === `app-backup:${app.app_id}` ? 'Starting…' : 'Back up'}
                        </LiteButton>
                      </div>
                    </article>
                  );
                })}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {activeSection === 'restore' ? (
        <section id="recovery-manage-panel-restore" className="lite-recovery-manage-section" role="tabpanel" aria-labelledby="recovery-manage-tab-restore" tabIndex={0}>
          <SectionHeading eyebrow="Restore" title="Review and restore safely" description="Verify the selected backup, review expected changes, and confirm before restoration begins." />
          <div className="lite-recovery-manage-action-list">
            <RecoveryActionRow
              icon={CheckCircle2}
              title="Verify backup"
              description={latestBackupVerified ? 'Evidence checks passed and the backup is ready.' : 'Confirm the latest backup passed integrity and readiness checks.'}
              status={latestBackupVerified ? 'Verified' : 'Required'}
              statusTone={latestBackupVerified ? 'healthy' : 'review'}
              actionLabel="Verify"
              busyLabel="Checking…"
              busy={busy === 'verify'}
              disabled={Boolean(busy) || !latestBackup || databaseWriteBlocked}
              onAction={onVerify}
              onDetails={() => onOpenActionDetails('verify')}
            />
            <RecoveryActionRow
              icon={FileCheck}
              title="Preview restore"
              description={latestPreviewReady ? `${latestPreview?.change_count || 0} item(s) checked without changing local state.` : 'Review expected changes before restoration is enabled.'}
              status={latestPreviewReady ? 'Ready' : 'Preview needed'}
              statusTone={latestPreviewReady ? 'healthy' : 'review'}
              actionLabel="Preview"
              busyLabel="Preparing…"
              busy={busy === 'preview'}
              disabled={Boolean(busy) || !latestBackup || databaseWriteBlocked}
              onAction={onPreview}
              onDetails={() => onOpenActionDetails('preview')}
            />
            <RecoveryActionRow
              icon={RotateCcw}
              title="Restore latest backup"
              description={restoreSucceeded ? lastRestore?.summary || 'The last restore completed.' : 'Creates a safety checkpoint and requires explicit confirmation.'}
              status={restoreSucceeded ? 'Completed' : latestPreviewReady && latestBackupVerified ? 'Ready' : 'Protected'}
              statusTone={restoreSucceeded ? 'healthy' : latestPreviewReady && latestBackupVerified ? 'review' : 'unknown'}
              actionLabel="Restore"
              busyLabel="Restoring…"
              busy={busy === 'restore'}
              disabled={Boolean(busy) || !latestBackupVerified || !latestPreviewReady || databaseWriteBlocked}
              tone="danger"
              onAction={onRestore}
              onDetails={() => onOpenActionDetails('restore')}
            >
              {busy === 'restore' ? <div className="lite-recovery-manage-inline-progress">Checkpoint and health checks are running…</div> : null}
            </RecoveryActionRow>
            <RecoveryActionRow
              icon={Database}
              title="Database restore"
              description={databasePreviewReady ? 'Verified database restore preview is ready.' : 'Open database protection to verify and preview a restore.'}
              status={databaseBackupVerified ? 'Protected' : 'Backup needed'}
              statusTone={databaseBackupVerified ? 'healthy' : 'review'}
              detailsLabel="Manage"
              onDetails={onOpenDatabaseDetails}
            />
          </div>
        </section>
      ) : null}

      {activeSection === 'protection' ? (
        <section id="recovery-manage-panel-protection" className="lite-recovery-manage-section" role="tabpanel" aria-labelledby="recovery-manage-tab-protection" tabIndex={0}>
          <SectionHeading eyebrow="Protection" title="Protection coverage" description="Review what is included, excluded, and available for recovery." />
          <div className="lite-recovery-protection-grid">
            <article>
              <ShieldCheck className="h-5 w-5" />
              <div><strong>Protected data</strong><p>Pocket Lab Lite state, app metadata, rules, and safe evidence references.</p></div>
              <StatusBadge status="healthy">Protected</StatusBadge>
              <ul>{protectedItems.slice(0, 6).map((item) => <li key={item}>{item}</li>)}</ul>
            </article>
            <article>
              <HardDrive className="h-5 w-5" />
              <div><strong>Excluded data</strong><p>Raw secrets, caches, temporary files, and large media stay outside the default backup.</p></div>
              <StatusBadge status="unknown">Excluded</StatusBadge>
              <ul>{excludedItems.slice(0, 6).map((item) => <li key={item}>{item}</li>)}</ul>
            </article>
            <article>
              <Database className="h-5 w-5" />
              <div><strong>Database protection</strong><p>{databaseProtection?.summary || 'SQLite backup, restore guard, and WAL protection are ready.'}</p></div>
              <StatusBadge status={databaseMaintenance?.active ? 'checking' : databaseBackupVerified ? 'healthy' : 'review'}>
                {databaseMaintenance?.active ? 'Working' : databaseBackupVerified ? 'Healthy' : 'Review'}
              </StatusBadge>
              <LiteButton tone="secondary" onClick={onOpenDatabaseDetails}>Protection details</LiteButton>
            </article>
          </div>
          <div className="lite-recovery-manage-evidence-callout">
            <div><FileCheck className="h-5 w-5" /><span><strong>Recovery evidence</strong><small>Sanitized records and receipts are available when needed.</small></span></div>
            <LiteButton tone="secondary" onClick={onOpenEvidence}>View evidence</LiteButton>
          </div>
        </section>
      ) : null}

      {activeSection === 'history' ? (
        <section id="recovery-manage-panel-history" className="lite-recovery-manage-section" role="tabpanel" aria-labelledby="recovery-manage-tab-history" tabIndex={0}>
          <SectionHeading eyebrow="History" title="Recovery activity" description="Review recent backups, restore previews, checkpoints, and completed recovery actions." />
          <div className="lite-recovery-recent-list">
            {latestBackup ? (
              <article><ArchiveRestore className="h-4 w-4" /><span><strong>{latestBackupVerified ? 'Backup verified' : 'Backup saved'}</strong><small>{latestBackup.created_at ? formatLiteTime(latestBackup.created_at) : 'Time unavailable'}</small></span></article>
            ) : null}
            {lastRestore?.restore_id ? (
              <article><RotateCcw className="h-4 w-4" /><span><strong>{lastRestore.summary || 'Restore recorded'}</strong><small>{lastRestore.completed_at ? formatLiteTime(lastRestore.completed_at) : lastRestore.status || 'Recorded'}</small></span></article>
            ) : null}
            {checkpoint?.checkpoint_id ? (
              <article><ShieldCheck className="h-4 w-4" /><span><strong>Restore checkpoint saved</strong><small>{checkpoint.created_at ? formatLiteTime(checkpoint.created_at) : 'Available for recovery'}</small></span></article>
            ) : null}
            {!latestBackup && !lastRestore?.restore_id && !recentHistory.length ? <p>No recovery activity yet.</p> : null}
          </div>
          <React.Suspense fallback={<div className="lite-recovery-history-loading">Loading backup history…</div>}>
            <RecoveryBackupHistory initialHistory={history} latestPreviewReady={latestPreviewReady} savedStateOnly={savedStateOnly} />
          </React.Suspense>
        </section>
      ) : null}
    </div>
  );
}
