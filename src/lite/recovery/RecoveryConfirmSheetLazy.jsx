import React from 'react';
import { AlertTriangle, ArchiveRestore, Database, ShieldCheck } from 'lucide-react';
import { formatLiteTime } from '../../lib/liteApi.js';
import { LiteButton, StatusBadge } from '../LiteUi.jsx';

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (!value) return 'Size unavailable';
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(value >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
  return `${Math.max(1, Math.round(value / 1024))} KB`;
}

export default function RecoveryConfirmSheetLazy({
  kind = 'lite',
  backup = null,
  preview = null,
  busy = false,
  onCancel,
  onConfirm,
}) {
  const databaseRestore = kind === 'database';
  const title = databaseRestore ? 'Restore Pocket Lab database?' : 'Restore this backup?';
  const backupLabel = backup?.created_at ? formatLiteTime(backup.created_at) : 'Selected verified backup';
  const sizeLabel = backup?.size_bytes ? formatSize(backup.size_bytes) : null;

  return (
    <div className="lite-recovery-native-confirm" data-recovery-native-confirm="true">
      <div className="lite-recovery-native-confirm-icon" aria-hidden="true">
        {databaseRestore ? <Database className="h-6 w-6" /> : <ArchiveRestore className="h-6 w-6" />}
      </div>
      <div className="lite-recovery-native-confirm-head">
        <div>
          <span>Confirmation required</span>
          <h3>{title}</h3>
        </div>
        <StatusBadge status="review">Protected action</StatusBadge>
      </div>

      <section className="lite-recovery-native-confirm-backup" aria-label="Selected backup">
        <strong>{backupLabel}</strong>
        <small>{[backup?.verification_status === 'verified' ? 'Verified' : 'Verification required', sizeLabel].filter(Boolean).join(' · ')}</small>
      </section>

      <section className="lite-recovery-native-confirm-section">
        <div><ShieldCheck className="h-5 w-5" /><strong>What will happen</strong></div>
        <ul>
          <li>A protected checkpoint is created before local state changes.</li>
          <li>{databaseRestore ? 'The verified SQLite backup is promoted and validated.' : `${Number(preview?.change_count || 0)} item(s) from the preview are eligible for restore.`}</li>
          <li>Pocket Lab checks health and keeps rollback evidence afterward.</li>
        </ul>
      </section>

      <section className="lite-recovery-native-confirm-section is-muted">
        <div><AlertTriangle className="h-5 w-5" /><strong>What will not happen</strong></div>
        <ul>
          <li>Secrets, tokens, and private keys are not exposed in the browser.</li>
          <li>Media and excluded runtime files are not silently replaced.</li>
        </ul>
      </section>

      <div className="lite-recovery-native-confirm-actions">
        <LiteButton tone="secondary" onClick={onCancel} disabled={busy}>Cancel</LiteButton>
        <LiteButton tone="danger" onClick={onConfirm} disabled={busy}>
          {busy ? 'Restoring…' : databaseRestore ? 'Restore Database' : 'Restore Backup'}
        </LiteButton>
      </div>
    </div>
  );
}
