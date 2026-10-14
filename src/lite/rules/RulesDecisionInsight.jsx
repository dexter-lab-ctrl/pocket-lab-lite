import React from 'react';
import { UserRoundCheck, Target, Scale, ArrowRightCircle, FlaskConical } from 'lucide-react';
import { GlassCard, StatusBadge, StateSurface } from '../LiteUi.jsx';
import { LiteTechnicalFacts } from '../LiteUx.jsx';
import { rulesDecisionView } from './rulesPremiumView.js';

export default function RulesDecisionInsight({ decision, simulated = false }) {
  const view = rulesDecisionView(decision, { simulated });
  if (!view) return <StateSurface tone="neutral" title="Decision unavailable" description="Pocket Lab has not returned a decision to explain." />;
  const rows = [
    { title: 'Who requested it?', value: view.actor || 'Actor information unavailable', Icon: UserRoundCheck },
    { title: 'What would change?', value: view.action + (view.target ? ' · ' + view.target : ''), Icon: Target },
    { title: 'Why this decision?', value: view.reason, Icon: Scale },
    { title: 'What can happen next?', value: view.next, Icon: ArrowRightCircle },
  ];
  return <section className="lite-rules-insight" aria-label="Decision Insight">
    <div className="lite-rules-insight-top"><span className="lite-rules-eyebrow">Decision Insight</span><h2>Why did Pocket Lab decide this?</h2><div><StatusBadge status={view.tone}>{view.status}</StatusBadge><strong>{view.action}</strong></div></div>
    {view.isSimulation ? <StateSurface tone="neutral" title="Simulation only" description="This is a simulation. No real permission or system change is granted." /> : null}
    <GlassCard className="lite-rules-insight-reason"><h3>Reported explanation</h3><p>{view.reason}</p></GlassCard>
    <ol className="lite-rules-insight-breakdown">{rows.map(({ title, value, Icon }) => <li key={title}><Icon size={19} aria-hidden="true" /><div><h3>{title}</h3><p>{value}</p></div></li>)}</ol>
    <p className="lite-rules-insight-boundary">{view.execution ? 'Separately reported execution: ' + view.execution + '.' : 'Authorization does not establish that execution started or completed.'}</p>
    <LiteTechnicalFacts title="Show technical details" facts={[
      { id: 'revision', label: 'Evaluated Rules revision', value: view.revision || 'Unavailable' },
      { id: 'reason', label: 'Reason code', value: view.reasonCode || 'Unavailable' },
      { id: 'timestamp', label: 'Decision time', value: view.occurredAt || 'Not reported' },
      { id: 'constraints', label: 'Reported constraints', value: view.constraints.join(' · ') || 'Not reported' },
      { id: 'correlation', label: 'Safe correlation reference', value: view.correlation || 'Not reported' },
    ]} />
  </section>;
}
