import React from 'react';
import { CheckCircle2, CircleAlert, Clock3, Info, ShieldCheck } from 'lucide-react';
import { LiteButton, StateSurface } from './LiteUi.jsx';
import {
  actionOutcomePresentation,
  confirmationPresentation,
  liteFreshnessPresentation,
  normalizeTechnicalFacts,
  normalizeTimelineItems,
} from '../lib/liteUxPresentation.js';

export function LiteFreshness({ saved = false, stale = false, refreshing = false, lastUpdatedLabel = '', backendReachable = true, className = '' }) {
  // The live refresh message belongs to the control. Use the settled copy for
  // the hidden placeholder so its reserved height cannot change mid-refresh.
  const presentation = liteFreshnessPresentation({ saved, stale, refreshing: false, lastUpdatedLabel, backendReachable });
  return (
    <div
      className={`lite-ux-freshness is-${presentation.state} ${refreshing ? 'is-refreshing-placeholder' : ''} ${className}`.trim()}
      role={refreshing ? undefined : 'status'}
      aria-live={refreshing ? undefined : 'polite'}
      aria-hidden={refreshing ? 'true' : undefined}
    >
      <Clock3 className="h-4 w-4" aria-hidden="true" />
      <span><strong>{presentation.label}</strong>{presentation.detail ? <small>{presentation.detail}</small> : null}</span>
    </div>
  );
}

export function LiteSectionHeader({ eyebrow = '', title, description = '', action = null, className = '' }) {
  return (
    <div className={`lite-ux-section-header ${className}`.trim()}>
      <div>
        {eyebrow ? <span>{eyebrow}</span> : null}
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action?.label ? <LiteButton tone={action.tone || 'secondary'} onClick={action.onClick} disabled={Boolean(action.disabled)}>{action.label}</LiteButton> : null}
    </div>
  );
}

export function LiteEmptyState({ title, description, action = null, tone = 'neutral', className = '' }) {
  const Icon = tone === 'attention' || tone === 'degraded' ? CircleAlert : Info;
  return (
    <StateSurface
      tone={tone === 'degraded' ? 'degraded' : 'neutral'}
      className={`lite-ux-empty-state ${className}`.trim()}
      title={title}
      description={description}
      icon={Icon}
      action={action?.label ? <LiteButton tone={action.tone || 'secondary'} onClick={action.onClick} disabled={Boolean(action.disabled)}>{action.label}</LiteButton> : null}
    />
  );
}

export function LiteTechnicalFacts({ title = 'Technical details', description = 'Safe operational facts from Pocket Lab.', facts = [], className = '' }) {
  const rows = normalizeTechnicalFacts(facts);
  if (!rows.length) return null;
  return (
    <details className={`lite-ux-technical-facts ${className}`.trim()}>
      <summary>{title}</summary>
      <div className="lite-ux-technical-facts-body">
        <p>{description}</p>
        <dl>
          {rows.map((item) => (
            <div key={item.id} className={`is-${item.tone}`}>
              <dt>{item.label}</dt>
              <dd><strong>{item.value}</strong>{item.note ? <small>{item.note}</small> : null}</dd>
            </div>
          ))}
        </dl>
      </div>
    </details>
  );
}

export function LiteHistoryTimeline({ items = [], emptyTitle = 'No history yet', emptyDescription = 'Recent activity will appear here.', className = '' }) {
  const history = normalizeTimelineItems(items);
  if (!history.length) return <LiteEmptyState title={emptyTitle} description={emptyDescription} className={className} />;
  return (
    <ol className={`lite-ux-history-timeline ${className}`.trim()}>
      {history.map((item) => (
        <li key={item.id} className={`is-${String(item.state || 'neutral').toLowerCase()}`}>
          <span className="lite-ux-history-marker" aria-hidden="true" />
          <div>
            <strong>{item.title}</strong>
            {item.summary ? <p>{item.summary}</p> : null}
            {item.time ? <time>{item.time}</time> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function LiteActionOutcome({ result, className = '' }) {
  if (!result) return null;
  const outcome = actionOutcomePresentation(result);
  return (
    <section className={`lite-ux-action-outcome ${className}`.trim()} aria-live="polite">
      <div className="lite-ux-action-outcome-head"><CheckCircle2 className="h-5 w-5" aria-hidden="true" /><div><strong>{outcome.title}</strong><p>{outcome.summary}</p></div></div>
      {outcome.whatChanged ? <div><span>What changed</span><p>{outcome.whatChanged}</p></div> : null}
      {outcome.whatDidNotHappen ? <div><span>What did not happen</span><p>{outcome.whatDidNotHappen}</p></div> : null}
      {outcome.protectedSummary ? <div><span>What stayed protected</span><p>{outcome.protectedSummary}</p></div> : null}
      {outcome.nextAction ? <div><span>Next step</span><p>{outcome.nextAction}</p></div> : null}
    </section>
  );
}

export function LiteConsequenceSummary({ value, className = '' }) {
  const info = confirmationPresentation(value || {});
  return (
    <section className={`lite-ux-consequence-summary ${className}`.trim()}>
      <div className="lite-ux-consequence-head"><ShieldCheck className="h-5 w-5" aria-hidden="true" /><div><strong>{info.title}</strong><p>{info.summary}</p></div></div>
      {info.will.length ? <div><span>This will</span><ul>{info.will.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
      {info.willNot.length ? <div><span>This will not</span><ul>{info.willNot.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
      {info.reversible ? <p><strong>Can it be undone?</strong> {info.reversible}</p> : null}
      {info.availability ? <p><strong>Availability</strong> {info.availability}</p> : null}
    </section>
  );
}

export const LITE_UX_MATURITY_PRIMITIVES_READY = true;
