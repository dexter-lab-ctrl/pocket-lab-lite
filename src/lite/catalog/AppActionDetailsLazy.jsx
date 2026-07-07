import React from 'react';
import { X } from 'lucide-react';
import { formatLiteTime } from '../../lib/liteApi.js';
import { LiteSharedElementCue } from '../LiteMotion.jsx';
import LiteProgressiveDetails from '../components/LiteProgressiveDetails.jsx';

const APP_ACTION_DETAILS_PANEL_SOURCE_MARKER = 'AppActionDetailsPanel';
const APP_ACTION_DETAILS_USES_PROGRESSIVE_FOUNDATION = true;
const APP_ACTION_DETAILS_HISTORY_IS_LAZY = true;
const APP_ACTION_DETAILS_BACKEND_EVIDENCE_BOUNDARY = 'normal App Catalog details do not fetch backend evidence endpoints';
const APP_ACTION_DETAILS_VISIBLE_SUMMARY_MARKERS = ['Last result', 'Saved for troubleshooting'];
void APP_ACTION_DETAILS_PANEL_SOURCE_MARKER;
void APP_ACTION_DETAILS_USES_PROGRESSIVE_FOUNDATION;
void APP_ACTION_DETAILS_HISTORY_IS_LAZY;
void APP_ACTION_DETAILS_BACKEND_EVIDENCE_BOUNDARY;
void APP_ACTION_DETAILS_VISIBLE_SUMMARY_MARKERS;

function normalizedActionStatus(value) {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function getActionDisplayState(status, enabled = true) {
  if (!enabled) return { status: 'review', label: 'Not ready' };
  const normalized = normalizedActionStatus(status);
  if (['queued', 'pending', 'accepted'].includes(normalized)) return { status: 'working', label: 'Getting ready' };
  if (['running', 'working', 'executing', 'in_progress'].includes(normalized)) return { status: 'working', label: 'Working' };
  if (['succeeded', 'success', 'completed', 'complete', 'done', 'verified', 'ready', 'protected', 'imported'].includes(normalized)) return { status: 'ready', label: 'Done' };
  if (['failed', 'error', 'blocked', 'needs_attention', 'review', 'not_ready'].includes(normalized)) return { status: 'review', label: 'Needs attention' };
  if (normalized === 'connected') return { status: 'ready', label: 'Connected' };
  return { status: 'checking', label: 'Ready' };
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
    if (item === 'Pocket Lab queued or ran an app backup through the backend worker path.') {
      return 'Pocket Lab asked the backend worker to save PhotoPrism app records.';
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
      ? 'A safe backend troubleshooting record was saved.'
      : 'No backend troubleshooting record was saved because this action did not run.';
  }
  return saved?.summary || (saved?.saved ? 'A backend record was saved for troubleshooting.' : 'No backend record was saved because this action did not run.');
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

function actionDetailsTone(details = {}, saved = {}) {
  const raw = `${details.status || ''} ${details.summary || ''} ${details.last_result || ''}`.toLowerCase();
  const hasAttention = Array.isArray(details.what_needs_attention) && details.what_needs_attention.some(Boolean);
  if (hasAttention || ['review', 'needs_attention', 'failed', 'error'].some((term) => raw.includes(term)) || raw.includes('something changed') || raw.includes('not ready')) {
    return 'review';
  }
  if (saved?.saved || raw.includes('completed') || raw.includes('protected') || raw.includes('ready')) return 'ready';
  return 'neutral';
}

function compactTechnicalRows(actionId, details = {}, saved = {}, technical = []) {
  const rows = [
    { label: 'Action id', value: actionId },
    { label: 'Status', value: details.status || 'ready' },
    { label: 'Backend owner', value: details.execution_owner || saved.execution_owner || 'FastAPI and backend worker' },
    details.operation_id ? { label: 'Operation id', value: details.operation_id } : null,
    details.sanitized_reference_id ? { label: 'Sanitized reference', value: details.sanitized_reference_id } : null,
    details.first_ran_at ? { label: 'First run', value: formatLiteTime(details.first_ran_at) } : null,
    details.last_ran_at ? { label: 'Last run', value: formatLiteTime(details.last_ran_at) } : null,
    saved?.receipt_id ? { label: 'Backend record', value: saved.receipt_id } : null,
  ].filter(Boolean);

  technical.forEach((item) => rows.push({ label: 'Detail', value: item }));
  return rows;
}

function compactHistoryItems(details = {}, runLabels, saved = {}) {
  const history = Array.isArray(details.run_history) ? details.run_history : [];
  if (history.length) return history;
  return [];
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

export default function AppActionDetailsLazy({ details, actionId = '', onClose }) {
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
    : { saved: false, backend_only: true, summary: 'No backend record was saved because this action did not run.' };
  const detailsTone = actionDetailsTone(details, saved);
  const runLabels = actionDetailRunHistoryLabels(actionId);
  const display = getActionDisplayState(details.status || 'ready');

  return (
    <section className={`lite-app-action-details-panel is-${detailsTone}`} role="region" aria-label={`${details.title || 'Action'} details`}>
      <div className="lite-app-action-details-head">
        {actionId !== 'check_app' && actionId !== 'repair_app' ? <LiteSharedElementCue kind="row-to-details" active label={details.title || 'Action details'} /> : null}
        <div>
          <span>Details</span>
          <h3>{details.title || 'Action details'}</h3>
          <p>{details.summary || 'Action details are available.'}</p>
        </div>
        <button type="button" className="lite-app-action-details-close" onClick={onClose} aria-label="Close action details">
          <X className="h-4 w-4" />
        </button>
      </div>

      <LiteProgressiveDetails
        title={details.title || 'Action details'}
        status={detailsTone}
        statusLabel={details.last_result || display.label}
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
          summary: historySummary(details, runLabels, saved),
          items: compactHistoryItems(details, runLabels, saved),
          enabled: true,
          emptyMessage: 'History will appear here after more runs.',
        }}
      />
    </section>
  );
}
