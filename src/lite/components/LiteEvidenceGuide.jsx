import React from 'react';
import './liteEvidenceGuide.css';

/**
 * Read-only P2 guidance. Facts and authority remain server-derived.
 * No inferred confidence, completion, permission or synthetic progress.
 */
export function LiteEvidenceGuide({ title, description = '', facts = [], caution = '', saved = false, children, className = '' }) {
  const visible = (Array.isArray(facts) ? facts : []).filter((fact) => fact?.label && fact?.value !== undefined && fact?.value !== null && fact?.value !== '').slice(0, 5);
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
      {caution ? <p className="lite-p2-evidence-caution">{caution}</p> : null}
      {children ? <div className="lite-p2-evidence-extra">{children}</div> : null}
    </section>
  );
}
export default LiteEvidenceGuide;
