import React, { useState } from 'react';
import { Clock3, KeyRound, ShieldCheck, ShieldAlert, LogIn, LogOut, UsersRound, Settings2, LifeBuoy, History } from 'lucide-react';
import { identityActivityView } from './identityPremiumView.js';

const iconFor = (event) => {
  if (event.outcome === 'denied' || event.outcome === 'blocked') return ShieldAlert;
  return ({ sign_in: LogIn, login: LogIn, sign_out: LogOut, logout: LogOut, passkey_added: KeyRound,
    passkey_removed: KeyRound, passkey_renamed: KeyRound, session_revoked: LogOut,
    recovery_used: LifeBuoy, recovery_generated: LifeBuoy, role_changed: ShieldCheck,
    membership_changed: UsersRound, mode_changed: Settings2 })[event.type] || Clock3;
};
export default function IdentityActivityTimeline({ items = [], limit = 0, onDetails }) {
  const [filter, setFilter] = useState('all');
  const entries = identityActivityView(items);
  const filtered = entries.filter((item) => filter === 'all' || item.family === filter);
  const shown = limit > 0 ? filtered.slice(0, limit) : filtered;
  return <section className="lite-id-activity" aria-label="Recent access activity">
    {!limit ? <div className="lite-id-activity-filters" role="group" aria-label="Filter access activity">
      {[['all', 'All'], ['sign-ins', 'Sign-ins'], ['access', 'Access changes']].map(([id, label]) =>
        <button type="button" key={id} aria-pressed={filter === id} className={filter === id ? 'is-active' : ''} onClick={() => setFilter(id)}>{label}</button>)}
    </div> : null}
    {shown.length ? <ol className="lite-id-timeline">{shown.map((event) => {
      const Icon = iconFor(event);
      return <li key={event.key}><span className="lite-id-timeline-marker"><Icon size={17} aria-hidden="true" /></span><div>
        <strong>{event.title}</strong><span className="lite-id-timeline-outcome">{event.outcome}</span>
        <p>{event.reasonCode ? 'Pocket Lab reported an access decision reason.' : 'Recorded by Pocket Lab.'}</p>
        <time dateTime={event.timestamp}>{event.timestamp ? new Date(event.timestamp).toLocaleString() : 'Time unavailable'}</time>
        <button type="button" onClick={() => onDetails(event)} aria-label={'View activity details: ' + event.title}>Details</button>
      </div></li>;
    })}</ol> : <p role="status">No reported activity in this view.</p>}
  </section>;
}
