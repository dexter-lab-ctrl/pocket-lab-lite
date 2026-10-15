import React, { useId, useState } from 'react';
import { DatabaseBackup, ShieldCheck, ScanEye, ArchiveRestore } from 'lucide-react';
import { GlassCard } from '../LiteUi.jsx';
import { RECOVERY_JOURNEY_STAGES } from './recoveryPremiumView.js';

const ICONS = [DatabaseBackup, ShieldCheck, ScanEye, ArchiveRestore];
const LABELS = { not_started: 'Not started', available: 'Available', needs_action: 'Needs action', in_progress: 'In progress', completed: 'Completed', failed: 'Failed', blocked: 'Blocked', unknown: 'Unknown' };
export default function RecoveryJourney({ stages = {}, saved = false }) {
  const [selected, setSelected] = useState(null);
  const region = useId();
  const choice = RECOVERY_JOURNEY_STAGES.find((stage) => stage.id === selected);
  return <GlassCard className="lite-recovery-premium-journey" data-recovery-journey-mode="understand">
    <header><span className="lite-recovery-premium-eyebrow">Your Recovery Journey</span><h2>Back up with confidence. Restore with care.</h2><p>Illustrative guide, not a live execution trace. Select a stage to learn more; selection never starts work.</p></header>
    <ol className="lite-recovery-premium-stage-grid" aria-label="Four Recovery stages">
      {RECOVERY_JOURNEY_STAGES.map((stage, index) => {
        const Icon = ICONS[index];
        const status = saved ? 'unknown' : LABELS[stages[stage.id]] ? stages[stage.id] : 'unknown';
        return <li key={stage.id} data-stage-status={status}>
          <button type="button" aria-expanded={selected === stage.id} aria-controls={region}
            className={selected === stage.id ? 'is-selected' : ''} onClick={() => setSelected((previous) => previous === stage.id ? null : stage.id)}>
            <Icon size={22} aria-hidden="true" /><strong>{stage.label}</strong><span>{LABELS[status]}</span>
          </button>
        </li>;
      })}
    </ol>
    <div id={region} className="lite-recovery-premium-journey-explanation">
      {choice ? <><strong>{choice.label} — how it works</strong><p>{choice.description}</p></> : <p>Select a stage to understand its purpose. Stage status comes from the reported recovery state, not your selection.</p>}
    </div>
  </GlassCard>;
}