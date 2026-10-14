import React from 'react';
import { UserRound, Fingerprint, ShieldCheck, LifeBuoy, CheckCircle2, CircleAlert, Clock3 } from 'lucide-react';
import { identityJourneyStages } from './identityPremiumView.js';

const icons = { identity: UserRound, authentication: Fingerprint, authorization: ShieldCheck, recovery: LifeBuoy };
const stateLabels = { confirmed: 'Reported', attention: 'Needs attention', saved: 'Saved information', blocked: 'Blocked', pending: 'Waiting', unavailable: 'Unavailable' };
const statusIcons = { confirmed: CheckCircle2, attention: CircleAlert, saved: Clock3, blocked: CircleAlert, pending: Clock3, unavailable: CircleAlert };

export default function IdentityAccessJourney({ view, onSelect }) {
  return (
    <section className="lite-id-journey" aria-labelledby="identity-access-journey-title">
      <header><span className="lite-id-eyebrow">Access Journey</span><h2 id="identity-access-journey-title">How your access fits together</h2><p>A guide to your reported access, not a live sign-in sequence.</p></header>
      <ol className="lite-id-journey-steps">
        {identityJourneyStages(view).map((stage) => {
          const Icon = icons[stage.id]; const StateIcon = statusIcons[stage.state] || CircleAlert;
          return <li key={stage.id} className={'is-' + stage.state}>
            <button type="button" onClick={() => onSelect(stage.id)} aria-label={'View ' + stage.title + ' details'}>
              <span className="lite-id-journey-icon"><Icon aria-hidden="true" size={23} /></span>
              <span className="lite-id-journey-copy"><strong>{stage.title}</strong><span>{stage.value}</span><small>{stage.detail}</small><em><StateIcon aria-hidden="true" size={14} />{stateLabels[stage.state] || 'Unavailable'}</em></span>
            </button>
          </li>;
        })}
      </ol>
    </section>
  );
}
