import React, { useEffect, useMemo, useState } from 'react';
import { Activity, ShieldCheck, UsersRound } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { getLiteReasonPresentation, getLiteStatusPresentation } from '../lib/identityRulesPresentation.js';
import { GlassCard, LiteButton, LoadingCard, StateSurface, StatusBadge } from './LiteUi.jsx';

const ROLE_ORDER = ['Owner', 'Admin', 'Operator', 'Auditor', 'Viewer'];

function MemberEditor({ member, roles, disabled, onSave }) {
  const [draft, setDraft] = useState({ role: member.role || 'Viewer', status: member.status || 'active' });
  useEffect(() => {
    setDraft({ role: member.role || 'Viewer', status: member.status || 'active' });
  }, [member.role, member.status]);
  const changed = draft.role !== member.role || draft.status !== member.status;
  const status = getLiteStatusPresentation(member.status);
  return (
    <div className="lite-identity-person-row">
      <div className="lite-identity-person-main">
        <div>
          <strong>{member.display_name || 'Pocket Lab person'}</strong>
          <span>{member.role || 'Member'} · updated {member.updated_at ? formatLiteTime(member.updated_at) : 'recently'}</span>
        </div>
        <StatusBadge status={status.tone}>{status.label}</StatusBadge>
      </div>
      <div className="lite-identity-person-controls" aria-label={`Access settings for ${member.display_name || 'Pocket Lab person'}`}>
        <label>
          <span>Role</span>
          <select value={draft.role} disabled={disabled} onChange={(event) => setDraft((value) => ({ ...value, role: event.target.value }))}>
            {(roles.length ? roles : ROLE_ORDER).map((role) => <option key={role} value={role}>{role}</option>)}
          </select>
        </label>
        <label>
          <span>Status</span>
          <select value={draft.status} disabled={disabled} onChange={(event) => setDraft((value) => ({ ...value, status: event.target.value }))}>
            <option value="active">Active</option>
            <option value="removed">Inactive</option>
          </select>
        </label>
        <LiteButton variant="secondary" disabled={disabled || !changed} onClick={() => onSave(member, draft)}>Save</LiteButton>
      </div>
    </div>
  );
}

export default function LiteIdentityEnterprise({ enterprise, recentActivity = [], onIdentityRefresh }) {
  const currentRole = enterprise?.current_membership?.role || '';
  const canManagePeople = currentRole === 'Owner';
  const members = useLiteResource(liteApi.enterpriseMembers, [], { enabled: Boolean(enterprise?.enabled && canManagePeople) });
  const [busyMember, setBusyMember] = useState('');
  const [notice, setNotice] = useState(null);
  const activeMembers = useMemo(() => (members.data?.members || []).filter((member) => member.status === 'active'), [members.data]);

  async function saveMember(member, draft) {
    setBusyMember(member.human_id);
    setNotice({ stage: 'pending', title: 'Waiting for Pocket Lab', message: 'The existing access stays in place until the server confirms this change.' });
    try {
      await liteApi.updateEnterpriseMember(member.human_id, { role: draft.role, status: draft.status });
      setNotice({ stage: 'verifying', title: 'Verifying access', message: 'The server accepted the change. Refreshing membership truth now.' });
      await Promise.all([members.refresh(), onIdentityRefresh?.()]);
      setNotice({ stage: 'completed', title: 'Access updated', message: `${member.display_name || 'Member'} now has the server-confirmed ${draft.role} / ${draft.status === 'active' ? 'Active' : 'Inactive'} membership.` });
    } catch (error) {
      const reasonCode = error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
      const reason = getLiteReasonPresentation(reasonCode, error?.message || 'Pocket Lab could not update this membership.');
      setNotice({ stage: 'failed', error: true, title: reason.title, message: reason.message });
    } finally {
      setBusyMember('');
    }
  }

  return (
    <section className="lite-identity-enterprise" aria-labelledby="identity-enterprise-heading">
      <div className="lite-identity-section-heading">
        <div>
          <span>Enterprise Mode</span>
          <h2 id="identity-enterprise-heading">Identity & Access governance</h2>
          <p>Server-managed roles add governance without changing the passkey-first sign-in boundary.</p>
        </div>
        <StatusBadge status="healthy">Enabled</StatusBadge>
      </div>

      <div className="lite-identity-posture-grid">
        <GlassCard className="lite-identity-card lite-identity-posture-card">
          <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><ShieldCheck className="h-5 w-5" /></div><StatusBadge status={enterprise?.current_membership?.active ? 'healthy' : 'degraded'}>{enterprise?.current_membership?.active ? 'Active' : 'Needs attention'}</StatusBadge></div>
          <h3>Your access</h3>
          <strong className="lite-identity-posture-value">{currentRole || 'No active role'}</strong>
          <p>Rules approvals and protected actions use this server-resolved role. Browser state cannot grant authority.</p>
        </GlassCard>

        <GlassCard className="lite-identity-card lite-identity-posture-card">
          <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><UsersRound className="h-5 w-5" /></div><StatusBadge status={canManagePeople ? 'healthy' : 'neutral'}>{canManagePeople ? `${activeMembers.length || '—'} active` : 'Owner managed'}</StatusBadge></div>
          <h3>People</h3>
          <strong className="lite-identity-posture-value">{canManagePeople ? `${(members.data?.members || []).length || 0} memberships` : 'Role-aware access'}</strong>
          <p>{canManagePeople ? 'Owners can update existing Enterprise memberships. Every change is server-authorized and invalidates affected sessions.' : 'Only an active Owner can change Enterprise memberships. Your current role remains read-only here.'}</p>
        </GlassCard>

        <GlassCard className="lite-identity-card lite-identity-posture-card">
          <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><Activity className="h-5 w-5" /></div><span className="lite-identity-soft-badge">Activity</span></div>
          <h3>Recent identity activity</h3>
          <strong className="lite-identity-posture-value">{recentActivity.length}</strong>
          <p>Sanitized sign-in, passkey, session, recovery and membership events remain available without exposing credentials.</p>
        </GlassCard>
      </div>

      {canManagePeople ? (
        <GlassCard className="lite-identity-card mt-5">
          <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><UsersRound className="h-5 w-5" /></div><span className="lite-identity-soft-badge">People</span></div>
          <h3>Enterprise people</h3>
          <p>Use human-readable roles and status. Pocket Lab keeps internal identity references out of the visible interface and enforces final-Owner protection on the server.</p>
          {members.loading ? <LoadingCard label="Loading people..." /> : null}
          {members.error ? <StateSurface tone="degraded" title="People are unavailable" description={members.error} className="mt-3" /> : null}
          {!members.loading && !members.error && !(members.data?.members || []).length ? <StateSurface tone="neutral" title="No Enterprise memberships" description="Existing Enterprise memberships will appear here after they are created by the supported identity flow." /> : null}
          <div className="lite-identity-people-list">
            {(members.data?.members || []).map((member) => (
              <MemberEditor key={member.human_id} member={member} roles={members.data?.roles || ROLE_ORDER} disabled={Boolean(busyMember)} onSave={saveMember} />
            ))}
          </div>
        </GlassCard>
      ) : null}

      {notice ? (
        <div className="mt-4" role="status" aria-live="polite">
          <StateSurface tone={notice.error ? 'degraded' : notice.stage === 'completed' ? 'healthy' : 'neutral'} title={notice.title} description={notice.message} />
        </div>
      ) : null}
    </section>
  );
}
