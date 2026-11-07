import React from 'react';
import { Fingerprint, History, LockKeyhole, ShieldCheck } from 'lucide-react';
import { GlassCard } from '../LiteUi.jsx';

// Educational wording never grants permissions. Server-authored access facts
// decide whether an action may actually be performed.
export function accessEducationContext(view, signedIn = false) {
  if (!signedIn) return 'Sign in to review your account. Protected changes require current server authorization.';
  if (!view?.fresh) return 'This is saved or unavailable access information. Protected changes require a fresh server decision.';
  const mode = String(view.mode || '').toLowerCase();
  if (mode.includes('enterprise')) return 'In Enterprise Mode, the server checks your current membership, role, and applicable policies for every protected change.';
  if (mode.includes('personal')) return 'In Personal Mode, the server checks current Owner access and any confirmation required for a protected change.';
  return 'Pocket Lab checks your current account and applicable policies before permitting protected changes.';
}

const steps = [
  { title: 'Sign in', description: 'Confirm who you are using a supported sign-in method.', Icon: Fingerprint },
  { title: 'Protect your access', description: 'Review passkeys, signed-in sessions and account recovery.', Icon: ShieldCheck },
  { title: 'Make protected changes', description: 'Pocket Lab checks current server authorization and any confirmation or approval policy.', Icon: LockKeyhole },
  { title: 'Review activity', description: 'Review access events Pocket Lab actually reported.', Icon: History },
];

export default function AccessHowItWorks({ view, signedIn = false }) {
  return (
    <section className="lite-access-education" aria-labelledby="lite-access-education-title">
      <div className="lite-access-education-heading">
        <h3 id="lite-access-education-title">How Access works</h3>
        <p>Your identity, protection and account changes work together.</p>
      </div>
      <ol className="lite-access-education-steps">
        {steps.map(({ title, description, Icon }, index) => (
          <li key={title}>
            <GlassCard className="lite-access-education-step">
              <span className="lite-access-education-icon" aria-hidden="true"><Icon size={20} /></span>
              <div><small>Step {index + 1}</small><strong>{title}</strong><p>{description}</p></div>
            </GlassCard>
          </li>
        ))}
      </ol>
      <p className="lite-access-education-mode">{accessEducationContext(view, signedIn)}</p>
    </section>
  );
}
