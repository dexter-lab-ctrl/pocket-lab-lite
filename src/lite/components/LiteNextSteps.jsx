import React, { useId, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import './liteNextSteps.css';

/**
 * P1 read-only operational guidance. Callers must supply already projected,
 * sanitized facts. No polling, authority inference, or commands live here.
 */
export function LiteNextSteps({ title = 'What to do next', description = '', items = [], saved = false, className = '', initialCount = 4, disclosureChevron = false }) {
  const [expanded, setExpanded] = useState(false);
  const listId = useId();
  const all = (Array.isArray(items) ? items : []).filter((item) => item && item.label);
  const visible = expanded || saved ? all : all.slice(0, Math.max(1, initialCount));
  if (!visible.length) return null;
  return (
    <section className={`lite-p1-next-steps ${className}`.trim()} aria-label={title} data-lite-p1-guidance="true" data-lite-information={saved ? 'saved' : 'current'}>
      <div className="lite-p1-next-steps-heading">
        <div><span>Next steps</span><h2>{title}</h2>{description ? <p>{description}</p> : null}</div>
        {saved ? <small>Saved information — verify current status before acting</small> : null}
      </div>
      <ol id={listId} className="lite-p1-next-steps-list">
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
      {!saved && all.length > initialCount ? <button type="button" className="lite-p1-next-steps-more"
        aria-expanded={expanded} aria-controls={listId} onClick={() => setExpanded((current) => !current)}>
        <span>{expanded ? 'Show fewer' : `Show all ${all.length} items`}</span>
        {disclosureChevron ? <ChevronDown size={17} className="lite-shared-disclosure-chevron" aria-hidden="true" /> : null}
      </button> : null}
    </section>
  );
}

export default LiteNextSteps;
