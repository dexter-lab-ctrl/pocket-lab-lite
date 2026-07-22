import React from 'react';
import { formatLiteTime } from '../../lib/liteApi.js';
import LiteProgressiveDetails from '../components/LiteProgressiveDetails.jsx';
import { LiteButton } from '../LiteUi.jsx';

const RECOVERY_PROGRESSIVE_DETAILS_MILESTONE_2 = true;
const RECOVERY_HISTORY_MOUNTS_ONLY_WHEN_OPENED = true;
const RECOVERY_BACKEND_ONLY_TROUBLESHOOTING = true;
void RECOVERY_PROGRESSIVE_DETAILS_MILESTONE_2;
void RECOVERY_HISTORY_MOUNTS_ONLY_WHEN_OPENED;
void RECOVERY_BACKEND_ONLY_TROUBLESHOOTING;

function shortId(value) {
  const text = String(value || '');
  if (!text) return '';
  if (text.length <= 18) return text;
  return `${text.slice(0, 10)}…${text.slice(-6)}`;
}

function safeStatus(value, fallback = 'ready') {
  return String(value || fallback).toLowerCase().replace(/[^a-z0-9_-]/g, '_');
}

function panelTitle(panel, actionKey) {
  if (panel?.title) return panel.title;
  if (actionKey === 'verify') return 'Verify Backup';
  if (actionKey === 'preview') return 'Preview Restore';
  if (actionKey === 'restore') return 'Restore Latest';
  if (actionKey === 'evidence') return 'Recovery details';
  return 'Recovery details';
}

function buildHistoryItems({ history, latestBackup, latestPreview, checkpoint, lastRestore }) {
  const items = [];
  if (lastRestore?.restore_id) {
    items.push({
      id: lastRestore.restore_id,
      title: lastRestore.summary || `Restore ${lastRestore.status || 'recorded'}`,
      meta: lastRestore.completed_at ? formatLiteTime(lastRestore.completed_at) : shortId(lastRestore.restore_id),
    });
  }
  if (checkpoint?.checkpoint_id) {
    items.push({
      id: checkpoint.checkpoint_id,
      title: checkpoint.summary || 'Checkpoint saved before restore',
      meta: checkpoint.created_at ? formatLiteTime(checkpoint.created_at) : shortId(checkpoint.checkpoint_id),
    });
  }
  if (latestPreview?.preview_id) {
    items.push({
      id: latestPreview.preview_id,
      title: latestPreview.summary || 'Restore preview prepared',
      meta: latestPreview.created_at ? formatLiteTime(latestPreview.created_at) : shortId(latestPreview.preview_id),
    });
  }
  if (latestBackup?.backup_id) {
    items.push({
      id: latestBackup.backup_id,
      title: latestBackup.summary || 'Backup restore point saved',
      meta: latestBackup.created_at ? formatLiteTime(latestBackup.created_at) : shortId(latestBackup.backup_id),
    });
  }
  return items.concat((Array.isArray(history) ? history : []).map((backup) => ({
    id: backup.backup_id || backup.id || backup.snapshot_id,
    title: backup.verification_status === 'verified' ? 'Backup verified and ready' : backup.summary || 'Backup created',
    meta: backup.created_at ? formatLiteTime(backup.created_at) : shortId(backup.backup_id || backup.snapshot_id),
  }))).filter((item) => item.id).slice(0, 12);
}

function technicalRows({ actionKey, latestBackup, latestPreview, checkpoint, lastRestore, repository, serviceRestart, healthValidation }) {
  return [
    { label: 'Action', value: panelTitle(null, actionKey) },
    { label: 'Status', value: lastRestore?.status || latestPreview?.status || latestBackup?.verification_status || repository?.status || 'checking' },
    { label: 'Backend owner', value: 'FastAPI and worker' },
    { label: 'Backup ID', value: shortId(latestBackup?.backup_id) },
    { label: 'Preview ID', value: shortId(latestPreview?.preview_id) },
    { label: 'Checkpoint ID', value: shortId(checkpoint?.checkpoint_id || lastRestore?.checkpoint_id) },
    { label: 'Restore ID', value: shortId(lastRestore?.restore_id) },
    { label: 'Service restart', value: serviceRestart?.status },
    { label: 'Health check', value: healthValidation?.status },
    { label: 'Last checked', value: latestBackup?.created_at ? formatLiteTime(latestBackup.created_at) : '' },
  ].filter((row) => row.value);
}

export default function RecoveryActionDetailsLazy({
  actionKey = '',
  panel = null,
  restoreSteps = [],
  latestBackup = null,
  latestPreview = null,
  checkpoint = null,
  lastRestore = null,
  repository = {},
  serviceRestart = {},
  healthValidation = {},
  history = [],
  savedStateOnly = false,
  evidenceItems = [],
  onOpenEvidence,
}) {
  const title = panelTitle(panel, actionKey);
  const status = safeStatus(lastRestore?.status || latestPreview?.status || latestBackup?.verification_status || repository?.status, 'ready');
  const statusLabel = actionKey === 'restore' && lastRestore?.status
    ? String(lastRestore.status)
    : actionKey === 'preview' && latestPreview?.status
      ? String(latestPreview.status)
      : actionKey === 'verify' && latestBackup?.verification_status
        ? String(latestBackup.verification_status)
        : 'Protected';
  const historyItems = buildHistoryItems({ history, latestBackup, latestPreview, checkpoint, lastRestore });
  const logs = Array.isArray(panel?.logs) ? panel.logs : [];
  const restoreSummary = lastRestore?.summary || (lastRestore?.restored_file_count ? `${lastRestore.restored_file_count} Lite state file(s) restored.` : 'Restore stays protected until confirmed.');

  const whatChanged = [];
  if (actionKey === 'verify' && latestBackup?.verification_status === 'verified') whatChanged.push('Backup verification is ready.');
  if (actionKey === 'preview' && latestPreview?.preview_id) whatChanged.push(`${latestPreview.change_count || 0} item(s) were checked without changing local state.`);
  if (actionKey === 'restore' && lastRestore?.restore_id) whatChanged.push(restoreSummary);
  if (!whatChanged.length) whatChanged.push('No local state was changed by opening these details.');

  return (
    <div className="lite-recovery-action-details-shell lite-recovery-details-lazy" data-recovery-progressive-details="true">
      <LiteProgressiveDetails
        title={title}
        status={status}
        statusLabel={statusLabel}
        summary={panel?.subtitle || 'Pocket Lab coordinates each recovery step and records a sanitized result.'}
        what_happened={logs.length ? logs : ['Pocket Lab checked the recovery state through the Lite API.']}
        what_changed={whatChanged}
        what_did_not_happen={[
          'The browser did not run recovery commands.',
          'The browser did not read backup files.',
          'Sanitized troubleshooting records are available for review.',
        ]}
        saved_for_troubleshooting={{
          saved: Boolean(latestBackup?.backup_id || latestPreview?.preview_id || checkpoint?.checkpoint_id || lastRestore?.restore_id),
          summary: 'A backend troubleshooting record is kept when recovery work runs. The normal UI shows only safe details.',
        }}
        next_step={panel?.next || ''}
        technicalDetails={technicalRows({ actionKey, latestBackup, latestPreview, checkpoint, lastRestore, repository, serviceRestart, healthValidation })}
        history={{
          title: 'Recovery history',
          domain: 'recoveryHistory',
          datasetKey: `recovery-action:${actionKey || 'unknown'}`,
          summary: historyItems.length ? `${historyItems.length} safe recovery record${historyItems.length === 1 ? '' : 's'} available.` : 'Recovery history is loaded only when opened.',
          items: historyItems,
          enabled: true,
          savedState: savedStateOnly,
          emptyMessage: 'History will appear here after more backup and restore runs.',
        }}
      >
        <section className="lite-progressive-detail-section lite-recovery-readiness-section">
          <strong>Recovery path</strong>
          <div className="lite-recovery-flip-readiness">
            {restoreSteps.map((step) => (
              <div key={step.key} className={step.complete ? 'is-complete' : ''}>
                <span>{step.complete ? '✓' : '•'}</span>
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </div>
            ))}
          </div>
        </section>
        {actionKey === 'evidence' ? (
          <section className="lite-progressive-detail-section lite-app-action-detail-section is-next-step">
            <strong>Protected records</strong>
            <p>{evidenceItems.length ? `${evidenceItems.length} safe reference value(s) are available.` : 'No protected recovery references are available yet.'}</p>
            <LiteButton disabled={!evidenceItems.length} tone="secondary" onClick={onOpenEvidence}>
              Open recovery references
            </LiteButton>
          </section>
        ) : null}
      </LiteProgressiveDetails>
    </div>
  );
}
