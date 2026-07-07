import React from 'react';
import { X } from 'lucide-react';
import LiteProgressiveDetails from '../components/LiteProgressiveDetails.jsx';

const SECURITY_PROGRESSIVE_DETAILS_MILESTONE_2 = true;
const SECURITY_FINDING_DETAILS_ARE_LAZY = true;
const SECURITY_FINDING_HISTORY_MOUNTS_ONLY_WHEN_OPENED = true;
const SECURITY_BACKEND_ONLY_EVIDENCE_BOUNDARY = 'normal Security finding details do not fetch backend evidence endpoints';
void SECURITY_PROGRESSIVE_DETAILS_MILESTONE_2;
void SECURITY_FINDING_DETAILS_ARE_LAZY;
void SECURITY_FINDING_HISTORY_MOUNTS_ONLY_WHEN_OPENED;
void SECURITY_BACKEND_ONLY_EVIDENCE_BOUNDARY;

function safeText(value, fallback = 'Not available') {
  const text = String(value || '').trim();
  if (!text) return fallback;
  return text
    .replace(/(token|password|secret|api[_-]?key|authorization|private[_-]?key)\s*[:=]\s*[^\s,;]+/gi, '$1=[hidden]')
    .replace(/\/data\/data\/com\.termux\/files\/[^\s,;]+/gi, '[private Android path hidden]')
    .slice(0, 240);
}

function shortId(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  if (text.length <= 20) return text;
  return `${text.slice(0, 10)}…${text.slice(-6)}`;
}

function severityLabel(value) {
  const severity = String(value || 'review').toLowerCase();
  if (severity === 'critical') return 'Critical';
  if (severity === 'high') return 'High';
  if (severity === 'medium') return 'Medium';
  if (severity === 'low') return 'Low';
  if (severity === 'info' || severity === 'informational') return 'Info';
  return 'Review';
}

function statusTone(value) {
  const severity = String(value || '').toLowerCase();
  if (['critical', 'high'].includes(severity)) return 'danger';
  if (['medium', 'review', 'warning'].includes(severity)) return 'review';
  if (['low', 'info', 'informational'].includes(severity)) return 'ready';
  return 'neutral';
}

function sourceLabel(finding = {}) {
  const raw = `${finding?.source || ''} ${finding?.tool || ''} ${finding?.scanner || ''} ${finding?.category || ''}`.toLowerCase();
  if (raw.includes('lynis') || raw.includes('host_hardening')) return 'Lynis';
  if (raw.includes('trivy') || raw.includes('dependency') || raw.includes('misconfiguration') || raw.includes('secret')) return 'Trivy';
  if (raw.includes('pocket')) return 'Pocket Lab';
  return 'Security check';
}

function componentLabel(finding = {}) {
  const category = String(finding?.category || '').toLowerCase();
  if (category === 'protected_runtime_secret') return 'Backend runtime file';
  if (category === 'host_hardening') return 'Host readiness';
  if (category === 'missing_tool') return safeText(finding?.tool || finding?.source, 'Security tool');
  if (category === 'dependency_vulnerability') return safeText(finding?.component || finding?.package || finding?.target, 'Local dependency');
  if (category === 'misconfiguration') return safeText(finding?.resource || finding?.target || finding?.component, 'Configuration');
  return safeText(finding?.component || finding?.target || finding?.resource, 'Pocket Lab runtime');
}

function evidenceRefLabel(finding = {}, context = {}) {
  const candidates = [
    finding?.evidence_ref,
    finding?.evidence,
    finding?.evidence_file,
    ...(Array.isArray(finding?.evidence_refs) ? finding.evidence_refs : []),
    ...(Array.isArray(context?.evidenceRefs) ? context.evidenceRefs : []),
  ].filter(Boolean);
  const value = String(candidates[0] || '').trim();
  if (!value) return 'Saved evidence reference unavailable.';
  return safeText(value.split('/').slice(-2).join('/'), 'Saved evidence reference unavailable.');
}

function findingTitle(finding = {}) {
  return safeText(finding?.title || finding?.summary || finding?.name, 'Security review item');
}

function recommendationText(finding = {}) {
  return safeText(finding?.recommendation || finding?.remediation || finding?.summary, 'Review this item and keep Pocket Lab protected.');
}

function historyItems(finding = {}) {
  const source = [finding?.history, finding?.runs, finding?.events].find((items) => Array.isArray(items) && items.length);
  return (Array.isArray(source) ? source : []).slice(0, 12);
}

function technicalRows(finding = {}, context = {}) {
  return [
    { label: 'Finding id', value: shortId(finding?.id || finding?.finding_id) },
    { label: 'Severity', value: severityLabel(finding?.severity) },
    { label: 'Source', value: sourceLabel(finding) },
    { label: 'Affected component', value: componentLabel(finding) },
    { label: 'Run id', value: shortId(context?.lastRun?.run_id || context?.evidence?.run?.run_id) },
    { label: 'Evidence reference', value: evidenceRefLabel(finding, context) },
    { label: 'Backend owner', value: 'FastAPI and worker' },
    { label: 'Sanitization', value: 'Technical details are sanitized before display.' },
  ].filter((row) => row.value);
}

export default function SecurityFindingDetailsLazy({ finding, context = {}, onClose }) {
  if (!finding) return null;
  const title = findingTitle(finding);
  const severity = severityLabel(finding?.severity);
  const tone = statusTone(finding?.severity || finding?.status);
  const history = historyItems(finding);
  const recommendation = recommendationText(finding);

  return (
    <section className={`lite-security-finding-details-panel is-${tone}`} role="region" aria-label={`${title} details`} data-security-progressive-details="true">
      <div className="lite-security-finding-details-head">
        <div>
          <span>Finding details</span>
          <h3>{title}</h3>
          <p>{recommendation}</p>
        </div>
        <button type="button" className="lite-finding-detail-close" onClick={onClose} aria-label="Close finding details">
          <X className="h-4 w-4" />
        </button>
      </div>

      <LiteProgressiveDetails
        title={title}
        status={tone}
        statusLabel={`Severity: ${severity}`}
        summary={recommendation}
        what_happened={[
          `Pocket Lab summarized a ${sourceLabel(finding)} finding from the latest safety check.`,
          `Affected component: ${componentLabel(finding)}.`,
        ]}
        what_changed={['Nothing was changed by opening these details.']}
        what_needs_attention={[recommendation]}
        what_did_not_happen={[
          'The browser did not run security tools.',
          'No repair or system change was started.',
          'Raw scanner output was not loaded into this view.',
          'Secrets, private paths, and backend command payloads stay hidden.',
        ]}
        saved_for_troubleshooting={{
          saved: Boolean(finding?.id || context?.lastRun?.run_id),
          backend_only: true,
          summary: 'A backend troubleshooting record stays protected. This view shows only safe finding details.',
        }}
        next_step={recommendation}
        technicalDetails={technicalRows(finding, context)}
        history={{
          title: 'Finding history',
          summary: history.length ? `${history.length} safe finding record${history.length === 1 ? '' : 's'} available.` : 'History will appear here after more safety checks.',
          items: history,
          enabled: true,
          emptyMessage: 'History will appear here after more safety checks.',
        }}
      />
    </section>
  );
}
