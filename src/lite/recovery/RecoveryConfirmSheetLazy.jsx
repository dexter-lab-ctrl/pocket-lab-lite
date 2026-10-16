import React from 'react';
import { ArchiveRestore, Database, ShieldCheck } from 'lucide-react';
import { formatLiteTime } from '../../lib/liteApi.js';
import { LiteButton, StatusBadge } from '../LiteUi.jsx';
import { LiteConsequenceSummary } from '../LiteUx.jsx';
import { recoveryRestoreImpact } from './recoveryPremiumView.js';

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (!value) return 'Size unavailable';
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(value >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
  return `${Math.max(1, Math.round(value / 1024))} KB`;
}

export default function RecoveryConfirmSheetLazy({
  kind = 'lite',
  backup = null,
  location = null,
  preview = null,
  busy = false,
  onCancel,
  onConfirm,
}) {
  const databaseRestore = kind === 'database';
  const title = databaseRestore ? 'Restore Pocket Lab data?' : 'Restore this backup?';
  const backupLabel = backup?.created_at ? formatLiteTime(backup.created_at) : 'Selected verified backup';
  const sizeLabel = backup?.size_bytes ? formatSize(backup.size_bytes) : null;
  const impact = recoveryRestoreImpact({ backup, preview, location });
  const includedComponents = impact.included;
  const excludedComponents = impact.excluded;

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
        {!databaseRestore ? <span>Recover from: {location?.display_name || backup?.location?.display_name || 'Pocket Lab protected backup'}</span> : null}
        {!databaseRestore ? <span>Restore to: This Server Phone</span> : null}
      </section>

      <section className="lite-recovery-impact" aria-label="Restore impact preview">
        <strong>What this restore may change</strong>
        <dl>
          <dt>Selected backup</dt><dd>{impact.backupId || 'Not reported'}</dd>
          <dt>Verification</dt><dd>{impact.verified ? 'Verified' : 'Not confirmed'}</dd>
          <dt>Created</dt><dd>{impact.createdAt ? formatLiteTime(impact.createdAt) : 'Not reported'}</dd>
          <dt>Matching preview</dt><dd>{impact.ready ? 'Ready' : 'Not ready or not confirmed'}</dd>
          <dt>Expected items</dt><dd>{impact.count === null ? 'Impact not reported' : impact.count}</dd>
          <dt>Backup location</dt><dd>{impact.location || 'Not reported'}</dd>
          <dt>Location status</dt><dd>{impact.location ? (impact.locationReady ? 'Available' : 'Unavailable') : 'Not reported'}</dd>
        </dl>
        <p>The backend decides what is safe to restore. An unavailable impact count never means zero.</p>
      </section>
      <div className="lite-safe-protected-confirmation" data-lite-confirmation-contract="server-owned">
        <LiteConsequenceSummary value={{
        title: 'Before Pocket Lab restores anything',
        summary: 'Pocket Lab will create a safety checkpoint first and check the workspace again afterward.',
        will: [
          'Create a protected checkpoint before local state changes.',
          databaseRestore ? 'Restore the verified Pocket Lab data backup and check it.' : impact.count === null ? 'Impact count not reported.' : String(impact.count) + ' item(s) from the preview are eligible for restore.',
          'Check workspace health after the restore and save a recovery record.',
        ],
        willNot: [
          'Expose secrets, tokens, or private keys in this screen.',
          'Change photos, media, Android shared storage, or anything excluded by the preview.',
        ],
        reversible: 'The pre-restore checkpoint is kept so recovery has a known safe point.',
        availability: 'Pocket Lab may briefly restart protected services while the restore is verified.',
        }} />
      </div>

      {includedComponents.length || excludedComponents.length ? (
        <section className="lite-recovery-native-confirm-section" aria-label="Restore scope">
          <div><ShieldCheck className="h-5 w-5" /><strong>Restore scope</strong></div>
          {includedComponents.length ? <p><strong>Included:</strong> {includedComponents.join(', ')}</p> : null}
          {excludedComponents.length ? <p><strong>Excluded and unchanged:</strong> {excludedComponents.join(', ')}</p> : null}
          <p>Photo/media files and Android shared storage will not be changed.</p>
        </section>
      ) : null}

      <div className="lite-recovery-native-confirm-actions">
        <LiteButton tone="secondary" onClick={onCancel} disabled={busy}>Cancel</LiteButton>
        <LiteButton tone="danger" onClick={onConfirm} disabled={busy}>
          {busy ? 'Restoring…' : databaseRestore ? 'Restore Database' : 'Restore Backup'}
        </LiteButton>
      </div>
    </div>
  );
}
