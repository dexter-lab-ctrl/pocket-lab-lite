import React from 'react';
import {
  Activity, BookOpenText, Fingerprint, Info, KeyRound, LockKeyhole,
  MonitorSmartphone, Settings2, ShieldCheck, ShieldUser, UsersRound,
} from 'lucide-react';
import { GlassCard } from '../LiteUi.jsx';

// Visual presentation only: every title, status and fact comes from the caller's
// sanitized Identity projection. This component has no authorization authority.
const detailIcons = {
  identity: ShieldUser,
  passkey: Fingerprint,
  session: MonitorSmartphone,
  recovery: KeyRound,
  person: UsersRound,
  role: ShieldCheck,
  authorization: LockKeyhole,
  activity: Activity,
  mode: Settings2,
  explain: BookOpenText,
};

export default function AccessDetailPresentation({ kind = 'identity', title, status, summary }) {
  const Icon = detailIcons[kind] || ShieldUser;
  return (
    <div className="lite-access-detail-intro" data-access-detail-presentation={kind}>
      <header className="lite-access-detail-heading">
        <span className="lite-access-detail-icon" aria-hidden="true"><Icon size={22} strokeWidth={1.9} /></span>
        <div className="lite-access-detail-heading-copy">
          <small>Access details</small>
          <h2>{title}</h2>
          <span className="lite-access-detail-status">{status || 'Not reported'}</span>
        </div>
      </header>
      {summary ? (
        <GlassCard className="lite-access-detail-explanation">
          <Info size={19} aria-hidden="true" />
          <div><h3>What this means</h3><p>{summary}</p></div>
        </GlassCard>
      ) : null}
    </div>
  );
}
