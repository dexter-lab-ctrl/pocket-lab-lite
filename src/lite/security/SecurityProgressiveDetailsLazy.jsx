import React from 'react';
import { X } from 'lucide-react';
import LiteProgressiveDetails from '../components/LiteProgressiveDetails.jsx';

const SECURITY_PHASE2_PROGRESSIVE_DETAILS = true;
const SECURITY_PHASE2_SUMMARY_FIRST = true;
const SECURITY_PHASE2_NO_RAW_SCANNER_OUTPUT = 'Security progressive details show sanitized summaries only';
const SECURITY_PHASE2_EVIDENCE_ON_DEMAND = 'Evidence summary opens only after user action';
void SECURITY_PHASE2_PROGRESSIVE_DETAILS;
void SECURITY_PHASE2_SUMMARY_FIRST;
void SECURITY_PHASE2_NO_RAW_SCANNER_OUTPUT;
void SECURITY_PHASE2_EVIDENCE_ON_DEMAND;

const SENSITIVE_TEXT_PATTERN = /(token|password|api[_-]?key|authorization|private[_-]?key|nats:\/\/|command payload|raw log|raw evidence|\/data\/data|\/storage\/emulated|restic password|backend secret)/i;

function safeText(value, fallback = '') {
  const text = String(value ?? '').trim();
  if (!text || SENSITIVE_TEXT_PATTERN.test(text)) return fallback;
  return text.slice(0, 220);
}

function safeList(values = [], fallback = []) {
  const source = Array.isArray(values) ? values : values ? [values] : fallback;
  return source.map((item) => safeText(item)).filter(Boolean).slice(0, 8);
}

function shortId(value) {
  const text = safeText(value);
  if (!text) return '';
  if (text.length <= 22) return text;
  return `${text.slice(0, 11)}…${text.slice(-6)}`;
}

function findingTitle(finding = {}) {
  return safeText(finding.title || finding.summary || finding.name || finding.id, 'Security review item');
}

function findingSummary(finding = {}) {
  return safeText(finding.recommendation || finding.summary || finding.description, 'Review this item and keep Pocket Lab protected.');
}

function sourceLabel(finding = {}) {
  const raw = `${finding.source || ''} ${finding.tool || ''} ${finding.category || ''}`.toLowerCase();
  if (raw.includes('lynis') || raw.includes('host')) return 'Lynis';
  if (raw.includes('trivy') || raw.includes('dependency') || raw.includes('secret')) return 'Trivy';
  return 'Security check';
}

function findingRows(findings = []) {
  return (Array.isArray(findings) ? findings : []).slice(0, 8).map((finding) => {
    const title = findingTitle(finding);
    const source = sourceLabel(finding);
    const severity = safeText(finding.severity || finding.status || 'review', 'review');
    return `${title} · ${severity} · ${source}`;
  });
}

function timelineRows(steps = []) {
  return (Array.isArray(steps) ? steps : []).slice(0, 8).map((step) => {
    const title = safeText(step.title || step.key, 'Security step');
    const state = safeText(step.state || step.status || 'waiting', 'waiting');
    return `${title} · ${state}`;
  });
}

function evidenceRows(evidenceRefs = []) {
  return (Array.isArray(evidenceRefs) ? evidenceRefs : [])
    .map((ref) => String(ref || '').split('/').slice(-1)[0])
    .map((ref) => safeText(ref))
    .filter(Boolean)
    .slice(0, 8);
}

function buildDetails({ type, model = {} }) {
  const {
    findingDelta = {},
    deltaStats = [],
    deltaPreview = [],
    allReviewFindings = [],
    executionSteps = [],
    executionLiveLabelAligned = '',
    latestEvidenceReceipt = null,
    evidenceReceipt = null,
    currentEvidenceRefs = [],
    toolNames = [],
    sbomSaved = false,
    evidenceFileCount = 0,
    safetyScore = 0,
    safetyLabel = '',
    lastRun = null,
    savedStateOnly = false,
  } = model;

  if (type === 'changes') {
    const statRows = (Array.isArray(deltaStats) ? deltaStats : []).map((item) => `${item.label}: ${item.value}`);
    const previewRows = findingRows(deltaPreview);
    return {
      title: 'What changed',
      status: Number(findingDelta?.new_count || 0) ? 'review' : 'ready',
      statusLabel: Number(findingDelta?.new_count || 0) ? 'New review items' : 'No urgent changes',
      summary: previewRows.length ? 'Pocket Lab found changes since the previous safety check.' : 'No recent changes need attention.',
      what_happened: ['Pocket Lab compared the latest safety summary with the previous saved check.', ...safeList(statRows)],
      what_changed: previewRows.length ? previewRows : ['No new findings were added to the main review list.'],
      what_needs_attention: Number(findingDelta?.new_count || 0) ? findingRows(findingDelta?.new) : [],
      what_did_not_happen: [
        'The browser did not run security tools.',
        'No repair or system change was started.',
        'Raw scanner output was not loaded into this view.',
      ],
      saved_for_troubleshooting: {
        saved: Boolean(lastRun?.run_id),
        backend_only: true,
        summary: savedStateOnly ? 'Showing saved state. Fresh details will refresh when Pocket Lab is reachable.' : 'Backend keeps the full safety record protected.',
      },
      next_step: Number(findingDelta?.new_count || 0) ? 'Review the new items, then rerun Safety Check after taking action.' : 'No action is needed right now.',
      technicalDetails: [
        { label: 'Latest run', value: shortId(lastRun?.run_id) || 'not available' },
        { label: 'New', value: Number(findingDelta?.new_count || 0) },
        { label: 'Resolved', value: Number(findingDelta?.resolved_count || 0) },
        { label: 'Still present', value: Number(findingDelta?.unchanged_count || 0) },
      ],
    };
  }

  if (type === 'attention') {
    const rows = findingRows(allReviewFindings);
    return {
      title: 'Needs attention',
      status: rows.length ? 'review' : 'ready',
      statusLabel: rows.length ? `${rows.length} safe item${rows.length === 1 ? '' : 's'}` : 'No urgent issues',
      summary: rows.length ? 'These are the current review items from the latest safety summary.' : 'No urgent issues were found in the latest summary.',
      what_happened: rows.length ? rows : ['Pocket Lab checked the latest safety summary and found no urgent items.'],
      what_changed: ['Nothing changed by opening this view.'],
      what_needs_attention: rows,
      what_did_not_happen: [
        'The browser did not scan files.',
        'No Lynis or Trivy command was run from this screen.',
        'No repair was started.',
        'Raw logs and private paths stay hidden.',
      ],
      saved_for_troubleshooting: {
        saved: Boolean(lastRun?.run_id),
        backend_only: true,
        summary: 'Full troubleshooting records stay backend-only. This view shows safe summaries.',
      },
      next_step: rows.length ? 'Open one finding at a time for the safest next step.' : 'Run Safety Check again later to keep evidence fresh.',
      technicalDetails: [
        { label: 'Latest run', value: shortId(lastRun?.run_id) || 'not available' },
        { label: 'Safety score', value: safetyScore },
        { label: 'Status', value: safetyLabel },
      ],
    };
  }

  if (type === 'checkPath') {
    const rows = timelineRows(executionSteps);
    return {
      title: 'Check path',
      status: rows.some((row) => row.toLowerCase().includes('failed')) ? 'review' : 'ready',
      statusLabel: executionLiveLabelAligned || 'Backend-owned check path',
      summary: 'This path shows the safe backend-owned handoff for the latest safety check.',
      what_happened: rows.length ? rows : ['The check path appears after a safety check starts.'],
      what_changed: ['Opening this view did not start a new check.'],
      what_did_not_happen: [
        'The frontend did not talk directly to NATS.',
        'The frontend did not run shell commands.',
        'The frontend did not run Lynis or Trivy.',
        'No backend command payload was shown.',
      ],
      saved_for_troubleshooting: {
        saved: Boolean(lastRun?.run_id),
        backend_only: true,
        summary: 'Backend events and evidence remain protected. This view shows only the safe step summary.',
      },
      next_step: rows.length ? 'Use this path to confirm request, worker, tool, and evidence progress.' : 'Run Safety Check to create a fresh check path.',
      technicalDetails: [
        { label: 'Latest run', value: shortId(lastRun?.run_id) || 'not available' },
        { label: 'Step count', value: rows.length },
        { label: 'Execution owner', value: 'FastAPI and worker' },
      ],
    };
  }

  return {
    title: 'Evidence summary',
    status: latestEvidenceReceipt || evidenceReceipt ? 'ready' : 'review',
    statusLabel: latestEvidenceReceipt?.status || evidenceReceipt?.status || 'Evidence summary',
    summary: latestEvidenceReceipt?.summary || 'Evidence appears after a completed safety check.',
    what_happened: [
      `Tools: ${(Array.isArray(toolNames) && toolNames.length ? toolNames : ['Lynis', 'Trivy']).join(' + ')}`,
      sbomSaved ? 'SBOM was saved.' : 'SBOM is pending or not available yet.',
      `${Number(evidenceFileCount || currentEvidenceRefs.length || 0)} evidence file${Number(evidenceFileCount || currentEvidenceRefs.length || 0) === 1 ? '' : 's'} summarized.`,
    ],
    what_changed: ['Opening the evidence summary did not change the device.'],
    what_did_not_happen: [
      'Raw evidence was not loaded into the normal UI.',
      'Raw scanner output was not shown.',
      'Secrets, tokens, private paths, and backend command payloads stay hidden.',
    ],
    saved_for_troubleshooting: {
      saved: Boolean(latestEvidenceReceipt || evidenceReceipt || currentEvidenceRefs.length),
      backend_only: true,
      summary: 'Sanitized evidence metadata is shown here. Full backend evidence remains protected.',
    },
    next_step: latestEvidenceReceipt || evidenceReceipt ? 'Use this summary for support or audit review without exposing secrets.' : 'Run Safety Check to create fresh evidence.',
    technicalDetails: [
      { label: 'Latest run', value: shortId(lastRun?.run_id || evidenceReceipt?.run_id) || 'not available' },
      { label: 'Evidence files', value: Number(evidenceFileCount || currentEvidenceRefs.length || 0) },
      { label: 'SBOM', value: sbomSaved ? 'Saved' : 'Not saved' },
      { label: 'Sanitization', value: 'Secrets hidden before display' },
    ],
    history: {
      title: 'Evidence files',
      summary: currentEvidenceRefs.length ? `${currentEvidenceRefs.length} sanitized evidence reference${currentEvidenceRefs.length === 1 ? '' : 's'} available.` : 'Evidence references will appear after a check completes.',
      items: evidenceRows(currentEvidenceRefs).map((title, index) => ({ id: `evidence-${index}`, title, meta: 'sanitized reference' })),
      enabled: true,
      emptyMessage: 'Evidence references will appear after a check completes.',
    },
  };
}

export default function SecurityProgressiveDetailsLazy({ type = 'evidence', model = {}, onClose }) {
  const details = buildDetails({ type, model });
  return (
    <section className="lite-security-phase2-details-panel" role="region" aria-label={`${details.title} details`} data-security-phase2-progressive-details="true">
      <div className="lite-security-phase2-details-head">
        <div>
          <span>Progressive details</span>
          <h2>{details.title}</h2>
          <p>Summary first. Technical details stay collapsed and sanitized.</p>
        </div>
        <button type="button" className="lite-finding-detail-close" onClick={onClose} aria-label="Close Security details">
          <X className="h-4 w-4" />
        </button>
      </div>
      <LiteProgressiveDetails {...details} />
    </section>
  );
}
