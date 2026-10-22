import React, { useId, useState } from 'react';
import { MousePointerClick, ScanSearch, Scale, ClipboardCheck } from 'lucide-react';
import { GlassCard } from '../LiteUi.jsx';

const STAGES = [
  { id: 'request', label: 'Request', short: 'Who', Icon: MousePointerClick, detail: 'Someone requests an important change. Pocket Lab receives the authenticated actor, requested action and target.' },
  { id: 'evaluate', label: 'Evaluate', short: 'Check', Icon: ScanSearch, detail: 'Pocket Lab evaluates the applicable Rules, permissions, target and protections on the server.' },
  { id: 'decision', label: 'Decision', short: 'Decide', Icon: Scale, detail: 'The server decides whether the requested change is allowed, blocked or needs additional confirmation or review.' },
  { id: 'outcome', label: 'Outcome', short: 'Record', Icon: ClipboardCheck, detail: 'Pocket Lab records the decision. Authorization is not proof that the requested operation finished.' },
];
export const RULES_JOURNEY_STAGES = STAGES.map(({ id, label, short, detail }) => ({ id, label, short, detail }));

export default function RulesProtectionJourney({ mode = 'understand', decision = null }) {
  const [selected, setSelected] = useState(null);
  const detailId = useId();
  const inspection = mode === 'inspect' && decision;
  const selectedStage = STAGES.find((stage) => stage.id === selected);
  const liveExplanation = inspection && selected === 'decision' ? decision.status
    : inspection && selected === 'request' ? decision.action
    : inspection && selected === 'outcome' ? 'The policy decision is recorded. Execution outcome is only shown when separately reported.'
    : null;
  return <GlassCard className="lite-rules-premium-journey" data-rules-journey-mode={inspection ? 'inspect' : 'understand'}>
    <header><span className="lite-rules-eyebrow">Protection Journey</span><h2>How Pocket Lab protects a change</h2><p>{inspection ? 'Verified decision facts only; other stages describe the Rules process, not a reconstructed trace.' : 'Illustrative guide — not a live authorization or execution trace.'}</p></header>
    <ol className="lite-rules-journey-track" aria-label="Protection Journey stages">
      {STAGES.map(({ id, label, short, Icon }, index) => <li key={id}>
        <button type="button" className={selected === id ? 'is-selected' : ''} aria-expanded={selected === id} aria-controls={detailId} aria-label={`${short} ${label}: ${STAGES[index].detail}`} onClick={() => setSelected((value) => value === id ? null : id)}>
          <Icon size={21} aria-hidden="true" /><strong>{short}</strong><span>{label}</span>
        </button>
        {index < STAGES.length - 1 ? <span className="lite-rules-journey-connector" aria-hidden="true" /> : null}
      </li>)}
    </ol>
    {selectedStage ? <div id={detailId} className="lite-rules-journey-explanation"><strong>{selectedStage.label}</strong><p>{selectedStage.detail}</p>{liveExplanation ? <p><strong>Reported:</strong> {liveExplanation}</p> : null}</div> : <p className="lite-rules-journey-hint">Select a stage to understand it. Stages never advance automatically.</p>}
  </GlassCard>;
}
