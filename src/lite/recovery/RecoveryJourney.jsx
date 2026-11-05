import React, { useId, useState } from 'react';
import { DatabaseBackup, ShieldCheck, ScanEye, ArchiveRestore, ChevronRight } from 'lucide-react';
import { GlassCard } from '../LiteUi.jsx';
import { LiteSheet } from '../LiteOverlay.jsx';
import { triggerLiteHaptic } from '../../lib/liteNativeFeedback.js';
import { useRecoveryMobileSheet } from './useRecoveryMobileSheet.js';
import { RECOVERY_JOURNEY_STAGES } from './recoveryPremiumView.js';

const ICONS = [DatabaseBackup, ShieldCheck, ScanEye, ArchiveRestore];
const LABELS = { not_started: 'Not started', available: 'Available', needs_action: 'Needs action', in_progress: 'In progress', completed: 'Completed', failed: 'Failed', blocked: 'Blocked', unknown: 'Unknown' };

// Read-only readiness; navigating a stage never invokes the API or completes an operation.
export default function RecoveryJourney({ stages = {}, saved = false }) {
  const [selected, setSelected] = useState(null);
  const region = useId();
  const mobile = useRecoveryMobileSheet();
  const choice = RECOVERY_JOURNEY_STAGES.find((stage) => stage.id === selected);
  const stateFor = (stage) => saved ? 'unknown' : LABELS[stages[stage.id]] ? stages[stage.id] : 'unknown';
  const onClose = () => { triggerLiteHaptic('accepted'); setSelected(null); };
  return <>
    <GlassCard className="lite-recovery-readiness" data-recovery-readiness="compact">
      <header className="lite-recovery-readiness-head">
        <div><h2>Recovery Readiness</h2><p>Back Up → Verify → Preview → Restore</p></div>
      </header>
      <ol className="lite-recovery-readiness-steps" aria-label="Four Recovery stages">
        {RECOVERY_JOURNEY_STAGES.map((stage, index) => {
          const Icon = ICONS[index];
          const status = stateFor(stage);
          return <li key={stage.id} data-stage-status={status}>
            <button type="button" aria-expanded={selected === stage.id} aria-controls={region}
              onClick={() => { triggerLiteHaptic('accepted'); setSelected(stage.id); }}>
              <Icon size={18} aria-hidden="true" /><strong>{stage.label}</strong><span>{LABELS[status]}</span><ChevronRight size={15} aria-hidden="true" />
            </button>
          </li>;
        })}
      </ol>
      <p className="lite-recovery-readiness-note">Status reflects reported Recovery facts, not a live execution trace.</p>
    </GlassCard>
    <LiteSheet open={Boolean(choice)} onClose={onClose} title={choice ? choice.label + ' readiness' : 'Recovery readiness'}
      eyebrow="Recovery Readiness" description="A guide to safe recovery. Selecting a stage never starts an action."
      variant="security" className="lite-recovery-readiness-sheet" mobileSnap={mobile}>
      <section id={region} className="lite-recovery-readiness-explanation" aria-label="Recovery stage explanation">
        {choice ? <><strong>{choice.label} — how it works</strong><p>{choice.description}</p><p>Reported status: {LABELS[stateFor(choice)]}</p>
          {saved ? <p>Saved information cannot authorize recovery changes. Reconnect and refresh.</p> : null}
        </> : null}
      </section>
    </LiteSheet>
  </>;
}
