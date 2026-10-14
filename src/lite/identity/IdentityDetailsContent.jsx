import React, { useEffect, useState } from 'react';
import { BookOpenText, LockKeyhole } from 'lucide-react';
import { LiteButton, StateSurface } from '../LiteUi.jsx';
import { LiteTechnicalFacts } from '../LiteUx.jsx';
import { getLiteReasonPresentation } from '../../lib/identityRulesPresentation.js';
import { identityDecisionLabel } from './identityPremiumView.js';

function Fact({ label, children }) {
  return <div className="lite-id-detail-fact"><dt>{label}</dt><dd>{children == null || children === '' ? 'Not reported' : children}</dd></div>;
}
function DetailGroup({ title, children }) { return <section className="lite-id-detail-group"><h3>{title}</h3>{children}</section>; }
function Action({ label, onClick, disabled = false, why = '' }) {
  return <div className="lite-id-detail-action"><LiteButton variant="secondary" onClick={onClick} disabled={disabled}>{label}</LiteButton>{disabled && why ? <p>{why}</p> : null}</div>;
}
export default function IdentityDetailsContent({ selection, view, onRename, onRemovePasskey, onSignOutSession, onRegenerate, onSignOutOtherSessions, onOpenManage, disabled = false }) {
  if (!selection) return null;
  const { kind, item = {} } = selection;
  const [roleDraft, setRoleDraft] = useState(item.role || '');
  useEffect(() => setRoleDraft(item.role || ''), [item.role, kind]);
  const explanation = kind === 'explain';
  const reason = getLiteReasonPresentation(item.reasonCode || '', item.title || 'Access information');
  const basicTitle = ({ identity: 'Identity', passkey: 'Passkey', session: 'Session', recovery: 'Recovery', person: 'Person', role: 'Role', authorization: 'Access decision', activity: 'Access activity', mode: 'Workspace mode', explain: 'Understand your access' })[kind] || 'Access details';
  const title = kind === 'passkey' ? item.friendly_name || 'Passkey' : kind === 'person' ? item.display_name || 'Person' : basicTitle;
  const status = kind === 'passkey' ? (item.active ? 'Active' : 'Revoked') : kind === 'session' ? (item.current ? 'Current session' : item.active ? 'Active' : 'Inactive') : kind === 'activity' ? item.outcome : kind === 'recovery' ? (view.recoveryConfigured ? 'Configured' : 'Unavailable or unconfigured') : view.fresh ? 'Reported by Pocket Lab' : 'Saved information';
  const summary = ({
    identity: 'Your displayed identity is server-reported. A role alone does not authorize a protected change.',
    passkey: 'This passkey belongs to your signed-in identity. Protected removal may need another passkey confirmation.',
    session: 'Pocket Lab reports this session; no browser, device or location details have been inferred.',
    recovery: 'Regenerating recovery codes invalidates the previous set. Codes are visible only in the authorized generation result.',
    person: 'This membership is managed through server-owned Enterprise authorization.',
    role: 'The role and action matrix come from the existing server projection, not client-side permission rules.',
    authorization: 'Only the server can decide whether the action is allowed now.',
    activity: 'This is a bounded Identity activity record, not proof that an unrelated device or action was affected.',
    mode: 'Workspace mode changes may invalidate sessions and require Owner confirmation.',
    explain: 'The access summary reflects reported facts. Historical or unavailable data cannot grant authority.',
  })[kind];
  return <div className="lite-id-details" data-identity-details-kind={kind}>
    <div className="lite-id-detail-heading"><h2>{title}</h2><span>{status}</span><p>{summary}</p></div>
    <DetailGroup title={explanation ? 'What this means' : 'Reported facts'}>
      <dl className="lite-id-detail-facts">
        {kind === 'identity' ? <><Fact label="Signed in as">{view.name}</Fact><Fact label="Role">{view.role}</Fact><Fact label="Mode">{view.mode}</Fact><Fact label="Sign-in method">{view.authentication}</Fact></> : null}
        {kind === 'passkey' ? <><Fact label="Name">{item.friendly_name}</Fact><Fact label="State">{item.active ? 'Active' : 'Revoked'}</Fact><Fact label="Created">{item.created_at || 'Not reported'}</Fact><Fact label="Last used">{item.last_used_at || 'Not reported'}</Fact></> : null}
        {kind === 'session' ? <><Fact label="Session">{item.current ? 'Current' : 'Other session'}</Fact><Fact label="Method">{item.auth_method || 'Not reported'}</Fact><Fact label="Expires">{item.absolute_expires_at || 'Not reported'}</Fact></> : null}
        {kind === 'recovery' ? <><Fact label="Configured">{view.recoveryConfigured == null ? 'Unavailable' : view.recoveryConfigured ? 'Yes' : 'No'}</Fact><Fact label="Unused codes">{view.remaining == null ? 'Unavailable' : view.remaining}</Fact></> : null}
        {kind === 'person' ? <><Fact label="Name">{item.display_name}</Fact><Fact label="Username">{item.username}</Fact><Fact label="Role">{item.role}</Fact><Fact label="Membership">{item.membership_status || item.status}</Fact><Fact label="Active passkeys">{item.active_passkeys}</Fact><Fact label="Active sessions">{item.active_sessions}</Fact></> : null}
        {kind === 'role' ? <><Fact label="Role">{item.label || item.id}</Fact><Fact label="Purpose">{item.summary}</Fact></> : null}
        {kind === 'authorization' ? <><Fact label="Action">{item.label}</Fact><Fact label="Reported decision">{identityDecisionLabel(item.decision)}</Fact><Fact label="Reason">{item.summary}</Fact></> : null}
        {kind === 'activity' ? <><Fact label="What happened">{item.title}</Fact><Fact label="Outcome">{item.outcome}</Fact><Fact label="When">{item.timestamp}</Fact><Fact label="Reported reason">{item.reasonCode ? getLiteReasonPresentation(item.reasonCode).message : 'Not reported'}</Fact></> : null}
        {kind === 'mode' ? <><Fact label="Workspace mode">{view.mode}</Fact><Fact label="Current role">{view.role}</Fact></> : null}
        {explanation ? <><Fact label="Who">{view.name}</Fact><Fact label="Authority">{view.role} · {view.mode}</Fact><Fact label="Sign-in method">{view.authentication}</Fact></> : null}
      </dl>
    </DetailGroup>
    {explanation ? <DetailGroup title="Why Pocket Lab says this"><p>These facts were reported by the Identity read. Browser passkey support alone does not prove your sign-in method or authorize an action.</p><p><BookOpenText size={16} aria-hidden="true" /> {view.fresh ? 'Live access read available.' : 'Previously reported access information; live authority unavailable.'}</p></DetailGroup> : null}
    <DetailGroup title="What this means"><p>{kind === 'activity' ? 'The record describes only the reported event and outcome.' : summary}</p></DetailGroup>
    <DetailGroup title="What happens next">
      {kind === 'passkey' && item.active ? <><Action label="Rename passkey" onClick={() => onRename(item)} disabled={disabled} why="Live access is required." /><Action label="Remove passkey" onClick={() => onRemovePasskey(item)} disabled={disabled} why="Live access is required." /></> : null}
      {kind === 'session' && item.active && !item.current ? <Action label="Sign out session" onClick={() => onSignOutSession(item)} disabled={disabled} why="Live access is required." /> : null}
      {kind === 'recovery' ? <Action label="Generate new recovery codes" onClick={onRegenerate} disabled={disabled} why="Live access is required." /> : null}
      {kind === 'session' && item.current ? <p>This is your current session. Sign-out controls are in Manage Access.</p> : null}
      {kind === 'person' && typeof item.onChangeRole === 'function' && Array.isArray(item.roleOptions) ? <div className="lite-id-person-role"><label>Role <select value={roleDraft} onChange={(event) => setRoleDraft(event.target.value)} disabled={disabled}>{item.roleOptions.map((role) => <option key={role} value={role}>{role}</option>)}</select></label><Action label="Save role" onClick={() => item.onChangeRole(roleDraft)} disabled={disabled || roleDraft === item.role || !item.roleOptions.includes(roleDraft)} why="Role changes require current server authority." /></div> : null}
      {kind === 'person' && Array.isArray(item.detailActions) ? item.detailActions.map((action) => <Action key={action.label} label={action.label} onClick={action.onClick} disabled={disabled || action.disabled} why={action.reason} />) : null}
      {kind === 'role' || kind === 'authorization' || kind === 'explain' || kind === 'identity' || kind === 'mode' || kind === 'activity' ? <Action label="Back to Manage Access" onClick={onOpenManage} /> : null}
      {kind === 'session' && item.current ? <Action label="Sign out other sessions" onClick={onSignOutOtherSessions} disabled={disabled} /> : null}
    </DetailGroup>
    <DetailGroup title="What this does not confirm"><p>Saved information, reported membership and previous activity do not establish current authorization. Pocket Lab checks live permission and step-up requirements for every protected change.</p></DetailGroup>
    <LiteTechnicalFacts title="Technical facts" facts={[{ id: 'source', label: 'Source', value: 'Identity & Access API' }, { id: 'freshness', label: 'Information', value: view.fresh ? 'Live read' : 'Saved / unavailable' }]} />
    {!view.fresh ? <StateSurface tone="degraded" title="Live access unavailable" description="Protected actions remain disabled until Pocket Lab confirms current authorization." /> : null}
    <div className="lite-id-detail-protection"><LockKeyhole size={17} aria-hidden="true" /> Protected changes still require server authorization.</div>
  </div>;
}
