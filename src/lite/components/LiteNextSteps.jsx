import React, { useState } from 'react';
import './liteNextSteps.css';

/**
 * P1 read-only operational guidance. Callers must supply already projected,
 * sanitized facts. No polling, authority inference, or commands live here.
 */
export function LiteNextSteps({ title = 'What to do next', description = '', items = [], saved = false, className = '', initialCount = 4 }) {
  const [expanded, setExpanded] = useState(false);
  const all = (Array.isArray(items) ? items : []).filter((item) => item && item.label);
  const visible = expanded ? all : all.slice(0, Math.max(1, initialCount));
  if (!visible.length) return null;
  return (
    <section className={`lite-p1-next-steps ${className}`.trim()} aria-label={title} data-lite-p1-guidance="true" data-lite-information={saved ? 'saved' : 'current'}>
      <div className="lite-p1-next-steps-heading">
        <div><span>Next steps</span><h2>{title}</h2>{description ? <p>{description}</p> : null}</div>
        {saved ? <small>Saved information — verify current status before acting</small> : null}
      </div>
      <ol className="lite-p1-next-steps-list">
        {visible.map((item) => (
          <li key={item.id || item.label}>
            <div className="lite-p1-next-steps-copy">
              <strong>{item.label}</strong>{item.description ? <p>{item.description}</p> : null}
            </div>
            {item.onClick && !saved ? (
              <button type="button" onClick={item.onClick} disabled={Boolean(item.disabled)} title={item.disabledReason || undefined} aria-label={item.actionLabel || `Review ${item.label}`}>
                {item.actionLabel || 'Review'}
              </button>
            ) : null}
          </li>
        ))}
      </ol>
      {all.length > initialCount ? <button type="button" className="lite-p1-next-steps-more" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Show fewer' : `Show all ${all.length} items`}</button> : null}
    </section>
  );
}

export default LiteNextSteps;
