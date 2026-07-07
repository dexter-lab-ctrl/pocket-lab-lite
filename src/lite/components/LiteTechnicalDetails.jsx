import React, { useMemo, useState } from 'react';

const TECHNICAL_DETAILS_COLLAPSED_BY_DEFAULT = true;
const TECHNICAL_DETAILS_SANITIZED_GUARD = 'sanitized technical details only; protected values stay hidden';
void TECHNICAL_DETAILS_COLLAPSED_BY_DEFAULT;
void TECHNICAL_DETAILS_SANITIZED_GUARD;

const SENSITIVE_DETAIL_PATTERN = /(token|password|api[_-]?key|invite|bootstrap|secret|credential|nats:\/\/|command payload|raw log|raw evidence|\/data\/data|private path|backend secret)/i;

function toSafeText(value) {
  if (value === null || value === undefined) return '';
  const text = String(value).trim();
  if (!text || SENSITIVE_DETAIL_PATTERN.test(text)) return '';
  return text;
}

function normalizeTechnicalRows(rows) {
  const values = Array.isArray(rows) ? rows : [];
  return values
    .map((row) => {
      if (row && typeof row === 'object') {
        const label = toSafeText(row.label || row.key || row.name || 'Detail');
        const value = toSafeText(row.value || row.summary || row.id || '');
        if (!label || !value) return null;
        return { label, value };
      }
      const value = toSafeText(row);
      if (!value) return null;
      return { label: 'Detail', value };
    })
    .filter(Boolean)
    .slice(0, 12);
}

export default function LiteTechnicalDetails({
  rows = [],
  title = 'Technical details',
  summary = 'Technical details are sanitized and collapsed by default.',
  defaultOpen = false,
}) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  const safeRows = useMemo(() => normalizeTechnicalRows(rows), [rows]);
  const safeSummary = toSafeText(summary) || 'Technical details are sanitized and collapsed by default.';

  if (!safeRows.length) return null;

  return (
    <section className="lite-technical-details" data-collapsed-by-default={!defaultOpen}>
      <button
        type="button"
        className="lite-progressive-disclosure-toggle"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{title}</span>
        <small>{open ? 'Hide' : 'Show'}</small>
      </button>
      <p className="lite-progressive-disclosure-summary">{safeSummary}</p>
      {open ? (
        <dl className="lite-technical-details-list">
          {safeRows.map((row) => (
            <div key={`${row.label}:${row.value}`} className="lite-technical-details-row">
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
}
