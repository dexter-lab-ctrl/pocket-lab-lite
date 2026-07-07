import React from 'react';
import LiteTechnicalDetails from './LiteTechnicalDetails.jsx';
import LiteHistorySection from './LiteHistorySection.jsx';

const PROGRESSIVE_DETAILS_SUMMARY_FIRST = true;
const PROGRESSIVE_DETAILS_NO_BACKEND_EVIDENCE_FETCH = true;
const PROGRESSIVE_DETAILS_NO_HIDDEN_HEAVY_PANELS = true;
const PROGRESSIVE_DETAILS_ATTENTION_CLASS_MARKER = 'lite-app-action-detail-section--attention';
void PROGRESSIVE_DETAILS_SUMMARY_FIRST;
void PROGRESSIVE_DETAILS_NO_BACKEND_EVIDENCE_FETCH;
void PROGRESSIVE_DETAILS_NO_HIDDEN_HEAVY_PANELS;
void PROGRESSIVE_DETAILS_ATTENTION_CLASS_MARKER;

function toList(value, fallback = []) {
  const source = Array.isArray(value) ? value : value ? [value] : fallback;
  return source
    .filter(Boolean)
    .map((item) => String(item).trim())
    .filter(Boolean)
    .slice(0, 8);
}

function safeSavedSummary(saved) {
  if (typeof saved === 'string') return saved;
  if (saved && typeof saved === 'object') {
    return saved.summary || (saved.saved ? 'A backend record was saved for troubleshooting.' : 'No backend troubleshooting record was saved.');
  }
  return 'Backend troubleshooting records stay protected.';
}

function DetailListSection({ title, items, tone = '' }) {
  const safeItems = toList(items);
  if (!safeItems.length) return null;
  return (
    <section className={`lite-progressive-detail-section lite-app-action-detail-section ${tone ? `is-${tone} lite-app-action-detail-section--${tone}` : ''}`.trim()}>
      <strong>{title}</strong>
      {safeItems.map((item) => <p key={item}>{item}</p>)}
    </section>
  );
}

export default function LiteProgressiveDetails({
  title = 'Details',
  status = 'ready',
  statusLabel = '',
  summary = 'Details are available.',
  what_happened = [],
  what_changed = [],
  what_did_not_happen = [],
  what_needs_attention = [],
  what_would_happen_after_confirmation = [],
  what_will_not_happen_by_default = [],
  saved_for_troubleshooting = null,
  next_step = '',
  technicalDetails = [],
  history = null,
  children,
}) {
  const savedSummary = safeSavedSummary(saved_for_troubleshooting);
  const historyProps = history && typeof history === 'object' ? history : {};

  return (
    <article className={`lite-progressive-details is-${status || 'neutral'}`}>
      <div className="lite-progressive-details-summary">
        <span>Details</span>
        <h3>{title}</h3>
        <p>{summary}</p>
        {statusLabel ? <strong className="lite-progressive-details-status">{statusLabel}</strong> : null}
      </div>

      <div className="lite-progressive-details-grid">
        <DetailListSection title="What happened" items={what_happened} />
        <DetailListSection title="What changed" items={what_changed} />
        {toList(what_needs_attention).length ? <DetailListSection title="What needs attention" items={what_needs_attention} tone="attention" /> : null}
        <DetailListSection title="What did not happen" items={what_did_not_happen} />
        <DetailListSection title="What would happen after confirmation" items={what_would_happen_after_confirmation} />
        <DetailListSection title="What will not happen by default" items={what_will_not_happen_by_default} />
        <section className="lite-progressive-detail-section lite-app-action-detail-section lite-app-action-detail-section--saved is-saved">
          <strong>Saved for troubleshooting</strong>
          <p>{savedSummary}</p>
        </section>
        {next_step ? (
          <section className="lite-progressive-detail-section lite-app-action-detail-section is-next-step">
            <strong>Next step</strong>
            <p>{next_step}</p>
          </section>
        ) : null}
        {children}
      </div>

      <LiteTechnicalDetails rows={technicalDetails} />
      <LiteHistorySection {...historyProps} />
    </article>
  );
}
