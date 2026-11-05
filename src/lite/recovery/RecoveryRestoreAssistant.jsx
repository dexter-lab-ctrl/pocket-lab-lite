import React from 'react';
import { ArchiveRestore, CheckCircle2, ScanEye, ShieldCheck } from 'lucide-react';
import { triggerLiteHaptic } from '../../lib/liteNativeFeedback.js';

export const RECOVERY_ASSISTANT_STEPS = [
  { id: 'choose', title: 'Choose restore point', summary: 'Choose a recorded backup; selection never starts recovery.', icon: ArchiveRestore },
  { id: 'preview', title: 'Preview changes', summary: 'Request verification and a real matching backend preview.', icon: ScanEye },
  { id: 'safety', title: 'Review safety checks', summary: 'Inspect the evidence and unresolved prerequisites.', icon: ShieldCheck },
  { id: 'confirm', title: 'Confirm and restore', summary: 'An explicit guarded confirmation is always required.', icon: CheckCircle2 },
];

// Presentation only; useLiteRecoveryFlow and FastAPI remain the workflow authority.
export default function RecoveryRestoreAssistant({ step = 'choose', onStepChange, verified = false, previewReady = false, writeBlocked = false, children }) {
  const current = RECOVERY_ASSISTANT_STEPS.find((item) => item.id === step) || RECOVERY_ASSISTANT_STEPS[0];
  return <div className="lite-recovery-restore-assistant" data-recovery-assistant="presentation-only" data-active-step={current.id}>
    <ol className="lite-recovery-assistant-steps" aria-label="Restore Assistant steps">
      {RECOVERY_ASSISTANT_STEPS.map((item, index) => {
        const Icon = item.icon;
        return <li key={item.id}>
          <button type="button" aria-current={step === item.id ? 'step' : undefined} aria-label={`Step ${index + 1}: ${item.title}`}
            onClick={() => { triggerLiteHaptic('accepted'); onStepChange?.(item.id); }}>
            <Icon aria-hidden="true" size={18}/><span>{index + 1}. {item.title}</span>
          </button>
        </li>;
      })}
    </ol>
    <div className="lite-recovery-assistant-content">
      <div className="lite-recovery-assistant-intro"><h4>{current.title}</h4><p>{current.summary}</p></div>
      {writeBlocked ? <p className="lite-recovery-assistant-warning" role="status">Live recovery authority is unavailable. Saved state is for review only.</p> : null}
      {step === 'confirm' && (!verified || !previewReady) ? <p className="lite-recovery-assistant-warning" role="status">A verified restore point and matching backend preview are required before confirmation.</p> : null}
      {children}
    </div>
  </div>;
}
