import React from 'react';
import { Activity, BookOpenText, ChevronRight, Fingerprint, KeyRound, MonitorSmartphone, ShieldCheck, ShieldUser, ShieldAlert, Clock3 } from 'lucide-react';
import { GlassCard, LiteButton } from '../LiteUi.jsx';
import { accessCenterLatestActivity, accessCenterProtectionRows, accessCenterReadiness, formatAccessTimestamp } from './accessCenterPresentation.js';

const protectionIcons = { passkeys: Fingerprint, sessions: MonitorSmartphone, recovery: KeyRound };

export default function AccessCenterSummary({ view, data, onManage, onActivity, onActivityDetails, onExplain, children }) {
  const readiness = accessCenterReadiness(view, data);
  const activity = accessCenterLatestActivity(data);
  return (
    <main className="lite-access-center" data-identity-horizon="account" data-identity-mode={data?.enterprise?.enabled ? 'enterprise' : 'personal'}>
      <section className="lite-access-hero" aria-label="Access profile" data-access-readiness={readiness.state}>
        <div className="lite-access-hero-layout">
          <div className="lite-access-person">
            <div className="lite-access-avatar" aria-hidden="true"><ShieldUser size={27} /></div>
            <div>
              <span className="lite-access-eyebrow">Your account</span>
              <h2>{view.name}</h2>
              <p>{view.role} · {view.mode}</p>
              <small>{view.fresh ? 'Signed in' : 'Saved information'} · Sign-in method: {view.authentication}</small>
            </div>
          </div>
          <div className="lite-access-hero-action">
            <div className="lite-access-readiness" role="status" aria-live="polite">
              {readiness.state === 'ready' ? <ShieldCheck size={20} aria-hidden="true" /> : <ShieldAlert size={20} aria-hidden="true" />}
              <div><strong>{readiness.title}</strong><p>{readiness.detail}</p></div>
            </div>
            <LiteButton onClick={() => onManage(null)}>Manage Access</LiteButton>
          </div>
        </div>
      </section>

      <section className="lite-access-section" aria-labelledby="lite-access-protection-heading">
        <h2 id="lite-access-protection-heading">Sign-in &amp; protection</h2>
        <GlassCard className="lite-access-settings-card">
          {accessCenterProtectionRows(view).map(({ id, title, description }) => {
            const Icon = protectionIcons[id];
            return <button className="lite-access-settings-row" type="button" key={id}
              onClick={() => onManage(id)} aria-label={`${title}, ${description}`}>
              <span className="lite-access-row-icon"><Icon size={19} aria-hidden="true" /></span>
              <span className="lite-access-row-copy"><strong>{title}</strong><small>{description}</small></span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>;
          })}
        </GlassCard>
      </section>

      {children}
      <section className="lite-access-section" aria-labelledby="lite-access-activity-heading">
        <div className="lite-access-section-heading"><h2 id="lite-access-activity-heading">Recent activity</h2><button type="button" onClick={onActivity}>View history</button></div>
        <GlassCard className="lite-access-activity-card">
          {activity ? <button type="button" className="lite-access-activity-row" onClick={() => onActivityDetails(activity)}>
            <Activity size={19} aria-hidden="true" />
            <span><strong>{activity.title}</strong><small>{view.fresh ? 'Latest reported activity' : 'Saved activity'} · {formatAccessTimestamp(activity.timestamp)}</small></span>
            <ChevronRight size={18} aria-hidden="true" />
          </button> : <div className="lite-access-activity-empty"><Clock3 size={19} aria-hidden="true" /><p>No recent access activity was reported.</p></div>}
        </GlassCard>
      </section>
      <section className="lite-access-section lite-access-learning-entry" aria-label="Access guidance">
        <button className="lite-access-education-link" type="button" onClick={onExplain}>
          <span className="lite-access-row-icon"><BookOpenText size={19} aria-hidden="true" /></span>
          <span className="lite-access-row-copy"><strong>How Access works</strong><small>Understand how your identity, protection and account changes work together.</small></span>
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </section>
    </main>
  );
}
