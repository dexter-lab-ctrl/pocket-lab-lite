import './identityRulesGovernance.css';
import React, { useEffect, useMemo, useState } from 'react';
import { Activity, KeyRound, ShieldCheck, UserPlus, UsersRound } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { clearLiteIdentityCsrf, formatLiteTime, liteApi } from '../lib/liteApi.js';
import { liteEnterpriseApi } from '../lib/liteEnterpriseApi.js';
import { getLitePasskey } from '../lib/liteWebAuthn.js';
import { getLiteReasonPresentation } from '../lib/identityRulesPresentation.js';
import { GlassCard, LiteButton, StateSurface, StatusBadge, copyTextToClipboard } from './LiteUi.jsx';
import { LiteSheet } from './LiteOverlay.jsx';
import LiteHelp, { LiteHelpHeading } from './LiteHelp.jsx';

const ROLE_ORDER = ['Owner', 'Admin', 'Operator', 'Auditor', 'Viewer'];

function reasonCode(error) {
  return error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
}

function roleTone(role) {
  if (role === 'Owner') return 'healthy';
  if (role === 'Admin') return 'ready';
  if (role === 'Operator') return 'review';
  return 'neutral';
}

function PersonRow({ person, currentPersonId, roles, currentRole, busy, onRole, onInvite, onSuspend, onReactivate, onReset, onRemove }) {
  const [draftRole, setDraftRole] = useState(person.role || 'Viewer');
  useEffect(() => setDraftRole(person.role || 'Viewer'), [person.role]);
  const isCurrent = person.human_id === currentPersonId;
  const canChangePrivileged = currentRole === 'Owner';
  const visibleRoles = canChangePrivileged ? roles : roles.filter((role) => !['Owner', 'Admin'].includes(role));
  const canManageTarget = currentRole === 'Owner' || !['Owner', 'Admin'].includes(person.role);
  const statusLabel = person.status === 'invited' ? 'Waiting to join' : person.status === 'suspended' ? 'Suspended' : person.status === 'removed' ? 'Removed' : 'Active';
  return (
    <div className="lite-governance-person">
      <div className="lite-governance-person-head">
        <div>
          <strong>{person.display_name || 'Pocket Lab person'}</strong>
          <div className="lite-governance-person-meta">@{person.username || 'person'} · {person.role || 'Member'}{isCurrent ? ' · You' : ''}</div>
        </div>
        <StatusBadge status={person.status === 'active' ? 'healthy' : person.status === 'suspended' ? 'review' : 'neutral'}>{statusLabel}</StatusBadge>
      </div>
      <p className="lite-governance-muted">
        {person.status === 'invited'
          ? 'This person has a server-created identity but cannot sign in until the one-time connect link is completed with a passkey.'
          : `${person.active_passkeys || 0} active passkey${Number(person.active_passkeys || 0) === 1 ? '' : 's'} · ${person.active_sessions || 0} active session${Number(person.active_sessions || 0) === 1 ? '' : 's'} · ${person.recovery_codes_remaining || 0} recovery code${Number(person.recovery_codes_remaining || 0) === 1 ? '' : 's'} remaining`}
      </p>
      {person.status !== 'removed' && canManageTarget ? (
        <div className="lite-governance-inline-actions">
          <label className="lite-governance-field">
            <span>Role</span>
            <select value={draftRole} disabled={Boolean(busy)} onChange={(event) => setDraftRole(event.target.value)}>
              {(visibleRoles.length ? visibleRoles : ROLE_ORDER).map((role) => <option key={role} value={role}>{role}</option>)}
            </select>
          </label>
          <LiteButton variant="secondary" disabled={Boolean(busy) || draftRole === person.role} onClick={() => onRole(person, draftRole)}>Save role</LiteButton>
        </div>
      ) : null}
      <div className="lite-governance-actions">
        {person.status === 'invited' && canManageTarget ? <LiteButton variant="secondary" onClick={() => onInvite(person)} disabled={Boolean(busy)}>New connect link</LiteButton> : null}
        {person.status === 'active' && !isCurrent && canManageTarget ? <LiteButton variant="secondary" onClick={() => onSuspend(person)} disabled={Boolean(busy)}>Suspend access</LiteButton> : null}
        {person.status === 'suspended' && canManageTarget ? <LiteButton variant="secondary" onClick={() => onReactivate(person)} disabled={Boolean(busy)}>Reactivate</LiteButton> : null}
        {person.status === 'active' && !isCurrent && canManageTarget ? <LiteButton variant="secondary" onClick={() => onReset(person)} disabled={Boolean(busy)}>Reset sign-in</LiteButton> : null}
        {person.status !== 'removed' && !isCurrent && canManageTarget ? <LiteButton variant="secondary" onClick={() => onRemove(person)} disabled={Boolean(busy)}>Remove person</LiteButton> : null}
      </div>
    </div>
  );
}

export default function LiteIdentityEnterprise({ enterprise, access: initialAccess = null, currentPerson = null, onIdentityRefresh, onModeChanged }) {
  const currentRole = enterprise?.current_membership?.role || initialAccess?.current_role || '';
  const canManagePeople = currentRole === 'Owner' || currentRole === 'Admin';
  const canChangeMode = currentRole === 'Owner';
  const [section, setSection] = useState('overview');
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState(null);
  const [invite, setInvite] = useState(null);
  const [modePreview, setModePreview] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [draft, setDraft] = useState({ username: '', display_name: '', role: 'Operator' });
  const access = useLiteResource(liteEnterpriseApi.access, [], { enabled: Boolean(enterprise?.enabled) });
  const people = useLiteResource(liteEnterpriseApi.people, [], { enabled: Boolean(enterprise?.enabled && canManagePeople) });
  const accessData = access.data || initialAccess || {};
  const roleCatalog = accessData.roles || enterprise?.role_catalog || [];
  const roleIds = roleCatalog.length ? roleCatalog.map((item) => item.id) : ROLE_ORDER;
  const activePeople = useMemo(() => (people.data?.people || []).filter((item) => item.status === 'active'), [people.data]);

  async function execute(name, callback, successMessage, refreshPeople = true) {
    setBusy(name); setNotice({ title: 'Waiting for Pocket Lab', message: 'The existing authority stays in place until the server confirms this change.' });
    try {
      const result = await callback();
      setNotice({ title: 'Server accepted', message: 'Pocket Lab accepted the change. Refreshing Identity and Rules authority now.' });
      const jobs = [access.refresh?.(), onIdentityRefresh?.()];
      if (refreshPeople) jobs.push(people.refresh?.());
      await Promise.all(jobs.filter(Boolean));
      setNotice({ title: 'Access updated', message: result?.summary || successMessage });
      return result;
    } catch (error) {
      const reason = getLiteReasonPresentation(reasonCode(error), error?.message || 'Pocket Lab could not complete that access change.');
      setNotice({ error: true, title: reason.title, message: reason.message });
      return null;
    } finally { setBusy(''); }
  }

  async function ownerStepUp(callback, purpose) {
    try { return await callback(); }
    catch (error) {
      if (error?.status !== 428 && reasonCode(error) !== 'owner_step_up_required') throw error;
      setNotice({ title: 'Confirm with your passkey', message: 'This root-level change needs recent Owner confirmation before Pocket Lab can continue.' });
      const options = await liteApi.passkeyStepUpOptions(purpose);
      const credential = await getLitePasskey(options);
      await liteApi.verifyPasskeyStepUp({ purpose, challenge: options.publicKey.challenge, credential });
      return callback();
    }
  }

  async function addPerson(event) {
    event.preventDefault();
    const result = await execute('person:create', () => liteEnterpriseApi.createPerson(draft), 'Person invited.');
    if (result?.invite) {
      setInvite({ ...result.invite, display_name: result.person?.display_name || draft.display_name });
      setDraft({ username: '', display_name: '', role: 'Operator' });
    }
  }

  async function changeRole(person, role) {
    await execute(`role:${person.human_id}`, () => liteEnterpriseApi.updateMember(person.human_id, { role, status: person.membership_status || 'active' }), `${person.display_name} now has ${role} access.`);
  }

  async function replaceInvite(person) {
    const result = await execute(`invite:${person.human_id}`, () => liteEnterpriseApi.regeneratePersonInvite(person.human_id), 'Replacement connect link created.');
    if (result?.invite) setInvite({ ...result.invite, display_name: person.display_name });
  }

  async function previewPersonalMode() {
    setBusy('mode:preview');
    try {
      setModePreview(await liteEnterpriseApi.modePreview(false));
      setNotice(null);
    } catch (error) {
      const reason = getLiteReasonPresentation(reasonCode(error), error?.message || 'Pocket Lab could not preview this mode change.');
      setNotice({ error: true, title: reason.title, message: reason.message });
    } finally { setBusy(''); }
  }

  async function switchToPersonalMode() {
    setConfirm(null);
    const result = await execute('mode:disable', () => ownerStepUp(() => liteEnterpriseApi.setMode(false), 'enterprise.mode.change'), 'Personal Mode is active.', false);
    if (result) {
      clearLiteIdentityCsrf();
      setModePreview(null);
      await onModeChanged?.(result);
    }
  }

  const topology = accessData.topology || enterprise?.topology || {};
  const currentRoleInfo = roleCatalog.find((item) => item.id === currentRole);

  return (
    <section className="lite-identity-enterprise lite-governance-section" aria-labelledby="identity-enterprise-heading">
      <div className="lite-governance-title-row">
        <div><span>Enterprise Mode</span><h2 id="identity-enterprise-heading">Identity & Access governance</h2><p>People, roles and Safety Rules use the same server-owned authority model.</p></div>
        <div className="lite-governance-inline-actions"><StatusBadge status="healthy">Enabled</StatusBadge><LiteHelp helpKey="identity.overview" /></div>
      </div>

      {notice ? <StateSurface tone={notice.error ? 'degraded' : 'neutral'} title={notice.title} description={notice.message} className="mt-4" /> : null}

      <nav className="lite-governance-nav" aria-label="Identity governance sections">
        {[['overview','Overview'],['people','People'],['roles','Roles & access'],['mode','Mode']].map(([id,label]) => <button key={id} type="button" className={section === id ? 'is-active' : ''} aria-current={section === id ? 'page' : undefined} onClick={() => setSection(id)}>{label}</button>)}
      </nav>

      {section === 'overview' ? (
        <div className="lite-governance-stack">
          <div className="lite-governance-grid">
            <GlassCard className="lite-governance-card">
              <div className="lite-governance-card-head"><ShieldCheck className="h-5 w-5" /><LiteHelp helpKey="identity.owner" /></div>
              <h3>Your authority</h3><strong className="lite-governance-value">{currentRole || 'No active role'}</strong>
              <p>{currentRoleInfo?.summary || accessData.role?.summary || 'Pocket Lab resolves your access on the server.'}</p>
              {currentRole === 'Owner' ? <StatusBadge status="healthy">No peer approval</StatusBadge> : null}
            </GlassCard>
            <GlassCard className="lite-governance-card">
              <div className="lite-governance-card-head"><UsersRound className="h-5 w-5" /><LiteHelp helpKey="identity.people" /></div>
              <h3>People</h3><strong className="lite-governance-value">{topology.active_people ?? activePeople.length} active</strong>
              <p>{topology.invited_people || topology.invited || 0} waiting to join · {topology.active_owners || topology.owners || 0} Owner{Number(topology.active_owners || topology.owners || 0) === 1 ? '' : 's'}.</p>
            </GlassCard>
            <GlassCard className="lite-governance-card">
              <div className="lite-governance-card-head"><Activity className="h-5 w-5" /><LiteHelp helpKey="identity.roles" /></div>
              <h3>Rules alignment</h3><strong className="lite-governance-value">Shared authority</strong>
              <p>Identity answers who you are. Rules uses the same role and policy projection to explain what that role can do.</p>
            </GlassCard>
          </div>
          {currentRole === 'Owner' ? <StateSurface tone="healthy" title="Owner is root-equivalent" description="Owner actions do not depend on another human approval. Confirmation, passkey step-up where required, protected Server Host guards, Rules consistency and audit evidence still apply." /> : null}
        </div>
      ) : null}

      {section === 'people' ? (
        <div className="lite-governance-stack">
          <GlassCard className="lite-governance-card">
            <div className="lite-governance-card-head"><LiteHelpHeading title="People" helpKey="identity.people" as="h3" /><StatusBadge status={canManagePeople ? 'healthy' : 'neutral'}>{canManagePeople ? 'Manage' : 'Read only'}</StatusBadge></div>
            <p>Every person gets a separate identity, passkey, sessions, recovery state and role. Internal identifiers stay secondary to human-readable names.</p>
            {!canManagePeople ? <StateSurface tone="neutral" title="People management is not available to this role" description="Owner and Admin roles can manage people. Admin cannot create or change Owner/Admin authority." /> : (
              <form className="lite-governance-form" onSubmit={addPerson}>
                <label><span>Sign-in name</span><input required maxLength="64" value={draft.username} onChange={(event) => setDraft((value) => ({ ...value, username: event.target.value }))} placeholder="alex" autoComplete="off" /></label>
                <label><span>Display name</span><input required maxLength="120" value={draft.display_name} onChange={(event) => setDraft((value) => ({ ...value, display_name: event.target.value }))} placeholder="Alex" autoComplete="off" /></label>
                <label><span>Initial role</span><select value={draft.role} onChange={(event) => setDraft((value) => ({ ...value, role: event.target.value }))}>{roleIds.filter((role) => currentRole === 'Owner' || !['Owner','Admin'].includes(role)).map((role) => <option key={role} value={role}>{role}</option>)}</select></label>
                <div className="lite-governance-actions"><LiteButton type="submit" disabled={Boolean(busy)}><UserPlus className="h-4 w-4" /> {busy === 'person:create' ? 'Creating…' : 'Add person'}</LiteButton></div>
              </form>
            )}
          </GlassCard>

          {invite ? <div className="lite-governance-invite" role="status"><strong>{invite.display_name} is ready to join</strong><span>Share this one-time link privately. It expires {invite.expires_at ? formatLiteTime(invite.expires_at) : 'soon'} and is not saved by the browser after this result.</span><code>{invite.claim_url}</code><div className="lite-governance-actions"><LiteButton variant="secondary" onClick={() => copyTextToClipboard(invite.claim_url)}>Copy connect link</LiteButton><LiteButton variant="secondary" onClick={() => setInvite(null)}>Done</LiteButton></div></div> : null}

          {people.loading ? <StateSurface tone="neutral" title="Loading people" description="Pocket Lab is reading current server-owned Identity state." /> : null}
          {people.error ? <StateSurface tone="degraded" title="People are unavailable" description={String(people.error)} /> : null}
          <div className="lite-governance-people">
            {(people.data?.people || []).map((person) => <PersonRow key={person.human_id} person={person} currentPersonId={currentPerson?.human_id || ''} roles={roleIds} currentRole={currentRole} busy={busy} onRole={changeRole} onInvite={replaceInvite} onSuspend={(item) => setConfirm({ title: `Suspend ${item.display_name}?`, description: 'Active sessions and outstanding authority will be invalidated. The identity and audit history are retained.', confirmLabel: 'Suspend access', action: () => execute(`suspend:${item.human_id}`, () => liteEnterpriseApi.suspendPerson(item.human_id), 'Access suspended.') })} onReactivate={(item) => execute(`reactivate:${item.human_id}`, () => liteEnterpriseApi.reactivatePerson(item.human_id), 'Access reactivated.')} onReset={(item) => setConfirm({ title: `Reset sign-in for ${item.display_name}?`, description: 'Existing passkeys, password credentials, recovery codes, sessions and continuations are invalidated. A new one-time connect link will be created.', confirmLabel: 'Reset sign-in', action: async () => { const result = await execute(`reset:${item.human_id}`, () => liteEnterpriseApi.resetPersonAccess(item.human_id), 'Sign-in reset.'); if (result?.invite) setInvite({ ...result.invite, display_name: item.display_name }); } })} onRemove={(item) => setConfirm({ title: `Remove ${item.display_name}?`, description: 'Active authority and sign-in methods are revoked. Identity and audit history are retained so past evidence remains understandable.', confirmLabel: 'Remove person', action: () => execute(`remove:${item.human_id}`, () => liteEnterpriseApi.removePerson(item.human_id), 'Person removed.') })} />)}
          </div>
          {!people.loading && !(people.data?.people || []).length ? <StateSurface tone="neutral" title="No people yet" description="Add a person to create a short-lived connect link and assign their first role." /> : null}
        </div>
      ) : null}

      {section === 'roles' ? (
        <div className="lite-governance-stack">
          <GlassCard className="lite-governance-card">
            <div className="lite-governance-card-head"><LiteHelpHeading title="Roles & access" helpKey="identity.roles" as="h3" /><StatusBadge status="healthy">Server owned</StatusBadge></div>
            <p>The browser displays authority; it does not grant it. Identity and Rules read the same server projection.</p>
            <div className="lite-governance-role-grid">
              {roleCatalog.map((role) => <div key={role.id} className={`lite-governance-role-card ${role.id === currentRole ? 'is-current' : ''}`}><div className="lite-governance-card-head"><strong>{role.label || role.id}</strong><StatusBadge status={roleTone(role.id)}>{role.id === currentRole ? 'Your role' : role.id}</StatusBadge></div><p>{role.summary}</p></div>)}
            </div>
          </GlassCard>
          <GlassCard className="lite-governance-card">
            <div className="lite-governance-card-head"><h3>Effective capability matrix</h3><LiteHelp helpKey="rules.protection" /></div>
            <div className="lite-governance-matrix">
              {(accessData.action_matrix || []).map((row) => <div className="lite-governance-matrix-row" key={row.action_id}><div><strong>{row.label}</strong><div className="lite-governance-muted">{row.summary}</div></div>{ROLE_ORDER.map((role) => <div key={role} className="lite-governance-matrix-cell"><strong>{role}</strong><br />{row.roles?.[role] === 'allow' ? 'Direct' : row.roles?.[role] === 'approval' ? 'Review' : row.roles?.[role] === 'step_up' ? 'Passkey' : 'Blocked'}</div>)}</div>)}
            </div>
          </GlassCard>
        </div>
      ) : null}

      {section === 'mode' ? (
        <div className="lite-governance-stack">
          <GlassCard className="lite-governance-card">
            <div className="lite-governance-card-head"><LiteHelpHeading title="Workspace mode" helpKey="identity.mode" as="h3" /><StatusBadge status="healthy">Enterprise</StatusBadge></div>
            <p>Enterprise Mode adds separate people, server-owned roles, advanced Rules, requests and temporary access. Personal Mode keeps the local Owner as the only human authority.</p>
            {!canChangeMode ? <StateSurface tone="neutral" title="Only an Owner can change workspace mode" description="Changing mode changes authority for every person and invalidates active sessions." /> : <LiteButton variant="secondary" onClick={previewPersonalMode} disabled={Boolean(busy)}>{busy === 'mode:preview' ? 'Checking impact…' : 'Review switch to Personal Mode'}</LiteButton>}
            {modePreview ? <div className="mt-4"><StateSurface tone="neutral" title="What will change" description="Pocket Lab will preserve Enterprise memberships, close Enterprise-only continuations, and sign out active sessions before Personal Mode becomes authoritative." /><ul className="lite-governance-mode-impact">{(modePreview.changes || []).map((item) => <li key={item}>{item}</li>)}</ul><div className="lite-governance-actions"><LiteButton variant="secondary" onClick={() => setModePreview(null)}>Keep Enterprise Mode</LiteButton><LiteButton onClick={() => setConfirm({ title: 'Switch to Personal Mode?', description: 'This is a root-level authorization change. Pocket Lab will require recent Owner passkey confirmation and sign out active sessions after the switch.', confirmLabel: 'Switch to Personal Mode', action: switchToPersonalMode })}>Switch to Personal Mode</LiteButton></div></div> : null}
          </GlassCard>
        </div>
      ) : null}

      <LiteSheet open={Boolean(confirm)} onClose={() => setConfirm(null)} title={confirm?.title || 'Confirm access change'} eyebrow="Confirm" description={confirm?.description || ''} className="lite-identity-sheet">
        <StateSurface tone="neutral" title="Pocket Lab verifies this on the server" description="No success is shown until server-owned Identity and Rules state confirms the result." />
        <div className="lite-governance-actions"><LiteButton variant="secondary" onClick={() => setConfirm(null)}>Cancel</LiteButton><LiteButton onClick={async () => { const action = confirm?.action; setConfirm(null); if (action) await action(); }}>{confirm?.confirmLabel || 'Confirm'}</LiteButton></div>
      </LiteSheet>
    </section>
  );
}
