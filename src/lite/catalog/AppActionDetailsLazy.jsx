import React from 'react';
import { formatLiteTime } from '../../lib/liteApi.js';
import LiteProgressiveDetails from '../components/LiteProgressiveDetails.jsx';

const APP_ACTION_DETAILS_USES_PROGRESSIVE_FOUNDATION = true;
const APP_ACTION_DETAILS_HISTORY_IS_LAZY = true;
const APP_ACTION_DETAILS_BACKEND_EVIDENCE_BOUNDARY = 'normal App Catalog details do not fetch backend evidence endpoints';
const APP_ACTION_DETAILS_VISIBLE_SUMMARY_MARKERS = ['Last result', 'Saved for troubleshooting'];
void APP_ACTION_DETAILS_USES_PROGRESSIVE_FOUNDATION;
void APP_ACTION_DETAILS_HISTORY_IS_LAZY;
void APP_ACTION_DETAILS_BACKEND_EVIDENCE_BOUNDARY;
void APP_ACTION_DETAILS_VISIBLE_SUMMARY_MARKERS;

function normalizedActionStatus(value) {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function getActionDisplayState(status, enabled = true) {
  const normalized = normalizedActionStatus(status);
  if (normalized === 'imported') return { status: 'ready', label: 'Imported' };
  if (normalized === 'installed') return { status: 'ready', label: 'Installed' };
  if (!enabled) return { status: 'review', label: 'Not ready' };
  if (['queued', 'pending', 'accepted'].includes(normalized)) return { status: 'working', label: 'Getting ready' };
  if (['running', 'working', 'executing', 'in_progress'].includes(normalized)) return { status: 'working', label: 'Working' };
  if (normalized === 'ready') return { status: 'checking', label: 'Ready to start' };
  if (normalized === 'protected') return { status: 'checking', label: 'Protected' };
  if (['succeeded', 'success', 'completed', 'complete', 'done', 'verified', 'imported'].includes(normalized)) return { status: 'ready', label: 'Done' };
  if (['failed', 'error', 'blocked', 'needs_attention', 'review', 'not_ready'].includes(normalized)) return { status: 'review', label: 'Needs attention' };
  return { status: 'checking', label: 'Not checked' };
}

function safeDetailList(items, fallback = []) {
  const values = Array.isArray(items) ? items : fallback;
  return values
    .filter(Boolean)
    .map((item) => String(item).trim())
    .filter((item) => item && item.toLowerCase() !== 'hidden')
    .slice(0, 6);
}

function actionDetailList(actionId, items, fallback = []) {
  const filtered = safeDetailList(items, fallback)
    .filter((item) => !(item.toLowerCase().includes('troubleshooting records') && item.toLowerCase().includes('backend-only')));
  if (actionId !== 'backup_app') return filtered;
  return filtered.map((item) => {
    if (item === 'Pocket Lab saved the approved PhotoPrism app records.') {
      return 'Pocket Lab saved the approved PhotoPrism app records.';
    }
    if (item === 'PhotoPrism settings, mappings, route records, and safe app records may be saved.') {
      return 'PhotoPrism settings, mappings, route records, and safe app records were prepared for backup.';
    }
    if (item === 'Photo files were not backed up by this app-record backup.') {
      return 'Your photo files were not copied by this app-record backup.';
    }
    if (item === 'Raw backup internals were not shown.') {
      return 'Private backup details stayed hidden.';
    }
    if (item === 'Raw secrets were not exposed.') {
      return 'Secrets stayed hidden.';
    }
    return item;
  });
}

function actionDetailSavedSummary(actionId, saved) {
  if (actionId === 'backup_app') {
    return saved?.saved
      ? 'A protected troubleshooting record was saved.'
      : 'No troubleshooting record was saved because this action did not run.';
  }
  return saved?.summary || (saved?.saved ? 'A protected troubleshooting record was saved.' : 'No troubleshooting record was saved because this action did not run.');
}

function actionDetailRunHistoryLabels(actionId) {
  if (actionId === 'backup_app') {
    return {
      title: 'Backup history',
      first: 'First backup',
      last: 'Latest backup',
      count: 'Backups saved',
    };
  }
  return {
    title: 'Run history',
    first: 'First run',
    last: 'Last run',
    count: 'Run count',
  };
}

function formatRunHistoryValue(value, hasEvidence) {
  if (value) return formatLiteTime(value);
  return hasEvidence ? 'Recorded' : 'Not run yet';
}

function actionDetailsTone(details = {}) {
  const status = normalizedActionStatus(details.status);
  const needsAttention = Array.isArray(details.what_needs_attention) && details.what_needs_attention.some(Boolean);
  if (needsAttention || ['failed','error','blocked','needs_attention','review','not_ready','partial','timed_out'].includes(status)) return 'review';
  if (['completed','succeeded','success','verified','done','imported','installed'].includes(status)) return 'ready';
  // Saved troubleshooting records and prose containing "ready" are not evidence of execution success.
  return 'neutral';
}

function technicalLabel(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function compactTechnicalRows(actionId, details = {}, saved = {}, technical = []) {
  const owner = 'Pocket Lab';
  const rows = [
    { label: 'Action', value: technicalLabel(actionId) },
    { label: 'Current state', value: technicalLabel(details.status || 'unknown') },
    { label: 'Run by', value: owner },
    details.operation_id ? { label: 'Operation reference', value: details.operation_id } : null,
    details.sanitized_reference_id ? { label: 'Troubleshooting reference', value: details.sanitized_reference_id } : null,
    details.first_ran_at ? { label: 'First recorded', value: formatLiteTime(details.first_ran_at) } : null,
    details.last_ran_at ? { label: 'Last recorded', value: formatLiteTime(details.last_ran_at) } : null,
    saved?.receipt_id ? { label: 'Troubleshooting record', value: saved.receipt_id } : null,
  ].filter(Boolean);
  const seen = new Set(rows.map((row) => `${row.label}:${row.value}`.toLowerCase()));

  technical.forEach((item) => {
    const text = String(item || '').trim();
    const separator = text.indexOf(':');
    const rawLabel = separator > 0 ? text.slice(0, separator).trim() : 'Runtime note';
    const value = separator > 0 ? text.slice(separator + 1).trim() : text;
    if (!value) return;
    if (['action', 'status', 'execution owner'].includes(rawLabel.toLowerCase())) return;
    const row = { label: technicalLabel(rawLabel), value };
    const key = `${row.label}:${row.value}`.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      rows.push(row);
    }
  });
  return rows.slice(0, 12);
}

function compactHistoryItems(details = {}, runLabels, saved = {}) {
  const history = Array.isArray(details.run_history) ? details.run_history.filter(Boolean) : [];
  if (history.length) return history;
  if (!details.has_run_evidence && !saved.saved) return [];
  return [{
    id: details.operation_id || details.sanitized_reference_id || `${details.status || 'recorded'}:${details.last_ran_at || 'saved'}`,
    title: details.last_result || details.summary || 'Completed action',
    meta: details.last_ran_at ? `Recorded ${formatLiteTime(details.last_ran_at)}` : 'Protected record saved',
  }];
}

function historySummary(details = {}, runLabels, saved = {}) {
  const hasEvidence = Boolean(details.has_run_evidence || saved.saved);
  const parts = [
    `${runLabels.first}: ${formatRunHistoryValue(details.first_ran_at, hasEvidence)}`,
    `${runLabels.last}: ${formatRunHistoryValue(details.last_ran_at, hasEvidence)}`,
  ];
  if (details.run_count) parts.push(`${runLabels.count}: ${details.run_count}`);
  return parts.join(' · ');
}

export default function AppActionDetailsLazy({ details, actionId = '' }) {
  if (!details) return null;
  const happened = actionDetailList(actionId, details.what_happened, [details.summary || 'Action details are available.']);
  const changed = actionDetailList(actionId, details.what_changed, ['Nothing changed.']);
  const needsAttention = actionDetailList(actionId, details.what_needs_attention);
  const didNotHappen = actionDetailList(actionId, details.what_did_not_happen, ['No unsafe action was started.']);
  const wouldHappen = actionDetailList(actionId, details.what_would_happen_after_confirmation);
  const willNotHappen = actionDetailList(actionId, details.what_will_not_happen_by_default);
  const technical = actionDetailList(actionId, details.technical_details);
  const saved = details.saved_for_troubleshooting && typeof details.saved_for_troubleshooting === 'object'
    ? details.saved_for_troubleshooting
    : { saved: false, backend_only: true, summary: 'No troubleshooting record was saved because this action did not run.' };
  const detailsTone = actionDetailsTone(details);
  const runLabels = actionDetailRunHistoryLabels(actionId);
  const display = getActionDisplayState(details.status || 'unknown');

  return (
    <section className={`lite-app-action-details-panel lite-app-premium-details is-${detailsTone}`} role="region" aria-label={`${details.title || 'Action'} details`}>

      <LiteProgressiveDetails
        title={details.title || 'Action details'}
        status={detailsTone}
        statusLabel={display.label}
        summary={details.summary || 'Action details are available.'}
        what_happened={happened}
        what_changed={changed}
        what_needs_attention={needsAttention}
        what_did_not_happen={didNotHappen}
        what_would_happen_after_confirmation={wouldHappen}
        what_will_not_happen_by_default={willNotHappen}
        saved_for_troubleshooting={{ ...saved, summary: actionDetailSavedSummary(actionId, saved) }}
        next_step={details.next_step || details.next_step_summary || ''}
        technicalDetails={compactTechnicalRows(actionId, details, saved, technical)}
        history={{
          title: runLabels.title,
          domain: 'appActionHistory',
          datasetKey: `app-action:${actionId || 'unknown'}`,
          summary: historySummary(details, runLabels, saved),
          items: compactHistoryItems(details, runLabels, saved),
          enabled: true,
          emptyMessage: details.has_run_evidence || saved.saved ? 'The latest protected result is shown above.' : 'No completed runs have been recorded yet.',
        }}
      />
    </section>
  );
}
