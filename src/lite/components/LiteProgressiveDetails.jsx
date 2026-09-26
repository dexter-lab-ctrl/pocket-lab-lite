import React, { useEffect, useMemo, useState } from 'react';
import LiteTechnicalDetails from './LiteTechnicalDetails.jsx';
import LiteHistorySection from './LiteHistorySection.jsx';

const PROGRESSIVE_DETAILS_SUMMARY_FIRST = true;
const PROGRESSIVE_DETAILS_INITIAL_SECTION_COUNT = 1;
const PROGRESSIVE_DETAILS_SECTION_BATCH_SIZE = 1;
const PROGRESSIVE_DETAILS_NO_BACKEND_EVIDENCE_FETCH = true;
const PROGRESSIVE_DETAILS_NO_HIDDEN_HEAVY_PANELS = true;
const PROGRESSIVE_DETAILS_ATTENTION_CLASS_MARKER = 'lite-app-action-detail-section--attention';
void PROGRESSIVE_DETAILS_SUMMARY_FIRST;
void PROGRESSIVE_DETAILS_INITIAL_SECTION_COUNT;
void PROGRESSIVE_DETAILS_SECTION_BATCH_SIZE;
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
  const detailSections = useMemo(() => {
    const sections = [];
    const addListSection = (key, sectionTitle, items, tone = '') => {
      const safeItems = toList(items);
      if (!safeItems.length) return;
      sections.push(<DetailListSection key={key} title={sectionTitle} items={safeItems} tone={tone} />);
    };

    addListSection('what-happened', 'What happened', what_happened);
    addListSection('what-changed', 'What changed', what_changed);
    addListSection('what-needs-attention', 'What needs attention', what_needs_attention, 'attention');
    addListSection('what-did-not-happen', 'What did not happen', what_did_not_happen);
    addListSection('what-would-happen', 'What would happen after confirmation', what_would_happen_after_confirmation);
    addListSection('what-will-not-happen', 'What will not happen by default', what_will_not_happen_by_default);
    sections.push(
      <section key="saved" className="lite-progressive-detail-section lite-app-action-detail-section lite-app-action-detail-section--saved is-saved">
        <strong>Saved for troubleshooting</strong>
        <p>{savedSummary}</p>
      </section>,
    );
    if (next_step) {
      sections.push(
        <section key="next-step" className="lite-progressive-detail-section lite-app-action-detail-section is-next-step">
          <strong>Next step</strong>
          <p>{next_step}</p>
        </section>,
      );
    }
    React.Children.toArray(children).forEach((child) => sections.push(child));
    return sections;
  }, [
    children,
    next_step,
    savedSummary,
    what_changed,
    what_did_not_happen,
    what_happened,
    what_needs_attention,
    what_will_not_happen_by_default,
    what_would_happen_after_confirmation,
  ]);
  const initialSectionCount = Math.min(PROGRESSIVE_DETAILS_INITIAL_SECTION_COUNT, detailSections.length);
  const [visibleSectionCount, setVisibleSectionCount] = useState(initialSectionCount);

  useEffect(() => {
    setVisibleSectionCount(initialSectionCount);
    if (detailSections.length <= initialSectionCount) return undefined;

    let active = true;
    let frame = null;
    let nextCount = initialSectionCount;
    const revealNextBatch = () => {
      frame = window.requestAnimationFrame(() => {
        if (!active) return;
        nextCount = Math.min(detailSections.length, nextCount + PROGRESSIVE_DETAILS_SECTION_BATCH_SIZE);
        setVisibleSectionCount(nextCount);
        if (nextCount < detailSections.length) revealNextBatch();
      });
    };
    revealNextBatch();
    return () => {
      active = false;
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, [detailSections.length, initialSectionCount]);

  return (
    <article className={`lite-progressive-details is-${status || 'neutral'}`}>
      <div className="lite-progressive-details-summary">
        <span>Details</span>
        <h3>{title}</h3>
        <p>{summary}</p>
        {statusLabel ? <strong className="lite-progressive-details-status">{statusLabel}</strong> : null}
      </div>

      <div className="lite-progressive-details-grid">
        {detailSections.slice(0, visibleSectionCount)}
      </div>

      <LiteTechnicalDetails rows={technicalDetails} />
      <LiteHistorySection {...historyProps} />
    </article>
  );
}
