import React from 'react';
import { CheckCircle2, Ban, Clock3, History, GitBranch, CircleAlert } from 'lucide-react';
import { LiteButton, StateSurface, StatusBadge } from '../LiteUi.jsx';
import { rulesActivationView, rulesDecisionView } from './rulesPremiumView.js';
import { formatLiteTime } from '../../lib/liteApi.js';

export function RulesDecisionTimeline({ decisions = [], onExplain, saved = false }) {
  if (!decisions.length) return <StateSurface tone="neutral" title="No protected decisions yet" description="The server will report protected decisions after a real Rules evaluation." />;
  return <div className="lite-rules-timeline-wrap">
    {saved ? <p>Saved history — decision freshness is not confirmed.</p> : null}
    <ol className="lite-rules-premium-timeline" aria-label="Protected decision history">
      {decisions.map((record, index) => {
        const decision = rulesDecisionView(record); if (!decision) return null;
        const Icon = decision.allowed ? CheckCircle2 : decision.blocked ? Ban : Clock3;
        return <li key={decision.id || index} className="lite-rules-timeline-entry"><Icon size={19} aria-hidden="true" /><div><strong>{decision.action}</strong><StatusBadge status={decision.tone}>{decision.status}</StatusBadge><p>{decision.reason}</p>{decision.actor ? <span>Requested by: {decision.actor}</span> : null}{decision.target ? <span>Target: {decision.target}</span> : null}{decision.occurredAt ? <time dateTime={decision.occurredAt}>{formatLiteTime(decision.occurredAt)}</time> : <span>Time not reported</span>}{onExplain ? <LiteButton tone="secondary" onClick={() => onExplain(record)}>Explain this</LiteButton> : null}</div></li>;
      })}
    </ol>
  </div>;
}
export function RulesActivationTimeline({ operation, backendReachable = true }) {
  if (!operation) return null;
  const progress = rulesActivationView(operation);
  const terminalLabel = { rolling_back: 'Rolling back', rolled_back: 'Rolled back', failed: 'Failed', not_completed: 'Not completed', uncertain: 'Uncertain' };
  return <section className="lite-rules-activation-premium" aria-label="Rules activation timeline" data-rules-activation-state={progress.state}>
    <header><History size={19} aria-hidden="true" /><h2>Rules activation</h2><StatusBadge status={progress.state === 'active' && backendReachable ? 'healthy' : 'review'}>{progress.state === 'active' && backendReachable ? 'Succeeded' : terminalLabel[progress.state] || progress.state}</StatusBadge></header>
    <p>{backendReachable ? 'Stages reflect the latest server-reported operation state.' : 'Live confirmation is unavailable. The previous known-good Rules remain the safe reference until server verification.'}</p>
    <ol className="lite-rules-premium-timeline">{progress.steps.map((step) => <li key={step.id} className={'is-' + step.state}><CheckCircle2 size={18} aria-hidden="true" /><div><strong>{step.label}</strong><span>{step.state === 'reported' ? 'Previously reported stage' : step.state === 'current' ? 'Current reported stage' : step.state === 'completed' && backendReachable ? 'Server-reported activation success' : 'Not confirmed'}</span></div></li>)}
      {progress.recovery ? <li className="is-recovery"><CircleAlert size={18} aria-hidden="true" /><div><strong>{terminalLabel[progress.state] || 'Recovery'}</strong><span>Recovery is server-owned. Completion is not assumed.</span></div></li> : null}
    </ol>
  </section>;
}
export function RulesRevisionTimeline({ health, revisions = [] }) {
  const active = health?.db_active_revision;
  const known = health?.known_good_revision;
  return <section className="lite-rules-revision-premium"><header><GitBranch size={19} aria-hidden="true" /><h3>Revision and recovery</h3></header>
    <p>{revisions.length ? 'Recorded revision facts from the server. Order does not establish an unreported activation history.' : 'Only current revision facts are available; no historical transitions are inferred.'}</p>
    <dl><div><dt>Active revision</dt><dd>{active || 'Unavailable'}</dd></div><div><dt>Known-good revision</dt><dd>{known || 'Unavailable'}</dd></div><div><dt>Consistency</dt><dd>{health?.consistency_state || 'Unconfirmed'}</dd></div></dl>
    {revisions.length ? <ol className="lite-rules-premium-timeline">{revisions.map((revision) => <li key={revision.revision_id}><GitBranch size={18} aria-hidden="true" /><div><strong>{revision.change_summary || 'Recorded Rules revision'}</strong><p>{revision.lifecycle_status || revision.validation_status || 'Status unavailable'}</p>{revision.created_at ? <time>{formatLiteTime(revision.created_at)}</time> : null}</div></li>)}</ol> : null}
  </section>;
}
