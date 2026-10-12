import React, { useState } from 'react';
import './liteEvidenceGuide.css';

/**
 * Read-only P2 guidance. Facts and authority remain server-derived.
 * No inferred confidence, completion, permission or synthetic progress.
 */
export function LiteEvidenceGuide({ title, description = '', facts = [], caution = '', saved = false, children, className = '' }) {
  const [expanded, setExpanded] = useState(false);
  const all = (Array.isArray(facts) ? facts : []).filter((fact) => fact?.label && fact?.value !== undefined && fact?.value !== null && fact?.value !== '');
  const visible = expanded ? all : all.slice(0, 5);
  if (!visible.length && !caution && !children) return null;
  return (
    <section className={`lite-p2-evidence-guide ${className}`.trim()} aria-label={title} data-lite-p2-evidence="true" data-lite-information={saved ? 'saved' : 'current'}>
      <div className="lite-p2-evidence-header">
        <div><span>Understanding this status</span><h2>{title}</h2>{description ? <p>{description}</p> : null}</div>
        {saved ? <small>Saved information — check current status before making changes.</small> : null}
      </div>
      {visible.length ? <dl className="lite-p2-evidence-facts">{visible.map((fact) => (
        <div key={fact.id || fact.label}><dt>{fact.label}</dt><dd>{String(fact.value)}</dd>{fact.detail ? <small>{fact.detail}</small> : null}</div>
      ))}</dl> : null}
      {all.length > 5 ? <button type="button" className="lite-p2-evidence-more" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Show fewer facts' : `Show all ${all.length} facts`}</button> : null}
      <p className="lite-p2-evidence-source">{saved ? 'Saved projection — current operation and permission cannot be confirmed.' : 'Reported by Pocket Lab. This explanation does not grant permission or confirm an action was completed.'}</p>
      {caution ? <p className="lite-p2-evidence-caution">{caution}</p> : null}
      {children ? <div className="lite-p2-evidence-extra">{children}</div> : null}
    </section>
  );
}
export default LiteEvidenceGuide;
