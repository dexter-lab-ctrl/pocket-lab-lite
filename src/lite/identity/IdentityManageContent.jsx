import React from 'react';
import AccessManageNavigation from './AccessManageNavigation.jsx';
import { BookOpenText, Fingerprint, LifeBuoy, LogOut } from 'lucide-react';
import { LiteButton, StateSurface } from '../LiteUi.jsx';
import IdentityActivityTimeline from './IdentityActivityTimeline.jsx';
import OwnerOperationApprovals from './OwnerOperationApprovals.jsx';
import TrustedAutomationClients from './TrustedAutomationClients.jsx';

export default function IdentityManageContent({
  data, view, section, setSection, busy, notice, passkeyEligible, recoveryCodes,
  onOpenDetails, onAddPasskey, onRename, onRemovePasskey, onSignOutSession,
  onSignOutOthers, onRegenerate, onCopyCodes, onSignOut, passwordForm,
  onPasswordForm, onChangePassword, enterpriseContent, enterpriseEnabled,
  onReviewEnterprise, onEnableEnterprise, showEnterpriseOptIn,
  ownerOperations = [], ownerOperationsFresh = false, onApproveOwnerOperation, onRejectOwnerOperation,
  ownerOperationClients = [], ownerOperationPairings = [], onApproveOwnerClientPairing, onRejectOwnerClientPairing, onRevokeOwnerOperationClient,
}) {
  const hasOwnerOperations = Array.isArray(ownerOperations) && ownerOperations.length > 0;
  const hasOwnerClients = ownerOperationsFresh || (Array.isArray(ownerOperationClients) && ownerOperationClients.length > 0) || (Array.isArray(ownerOperationPairings) && ownerOperationPairings.length > 0);
  const readOnly = !view.fresh;
  // The index is the first mobile Manage screen. Desktop selects Overview while
  // retaining its persistent navigation column.
  const effectiveSection = section || 'overview';
  return <div className="lite-id-manage" data-identity-manage-section={section || 'index'}>
    <AccessManageNavigation section={section} setSection={setSection}
      enterpriseEnabled={enterpriseEnabled} hasApprovals={hasOwnerOperations} hasClients={hasOwnerClients}>
      {notice ? <StateSurface tone={notice.error ? 'degraded' : 'neutral'} title={notice.title} description={notice.message} /> : null}
      {readOnly ? <StateSurface tone="degraded" title="Live authorization unavailable" description="Saved access details are for review only. Protected changes are unavailable." /> : null}
      {effectiveSection === 'overview' ? <div className="lite-id-manage-overview">
        <p>Signed in as <strong>{view.name}</strong>. Role: <strong>{view.role}</strong>. Sign-in method: {view.authentication}.</p>
        <dl className="lite-id-manage-counts"><div><dt>Passkeys</dt><dd>{view.passkeys == null ? 'Unavailable' : view.passkeys}</dd></div><div><dt>Sessions</dt><dd>{view.sessions == null ? 'Unavailable' : view.sessions}</dd></div><div><dt>Recovery</dt><dd>{view.recoveryConfigured == null ? 'Unavailable' : view.recoveryConfigured ? 'Configured' : 'Not configured'}</dd></div></dl>
        <LiteButton variant="secondary" onClick={() => onOpenDetails('identity', {})}>Identity Details</LiteButton>
        <LiteButton variant="secondary" onClick={() => onOpenDetails('explain', {})}><BookOpenText aria-hidden="true" size={16} /> Explain This</LiteButton>
        <p>Only the live server decides whether an action is allowed.</p>
        {enterpriseEnabled ? enterpriseContent : null}
      </div> : null}
      {effectiveSection === 'passkeys' ? <div className="lite-id-manage-list">
        <p>Passkeys belong to your signed-in identity. Removal may require recent confirmation.</p>
        {!passkeyEligible ? <StateSurface tone="neutral" title="Passkeys unavailable in this browser" description="Use the secure Pocket Lab HTTPS address with a platform authenticator to add a passkey." /> : null}
        <LiteButton onClick={onAddPasskey} disabled={Boolean(busy) || readOnly || !passkeyEligible}><Fingerprint aria-hidden="true" size={16} /> Add Passkey</LiteButton>
        {!Array.isArray(data?.passkeys) ? <StateSurface tone="neutral" title="Passkeys unavailable" description="No current passkey list was reported." /> : data.passkeys.length ? data.passkeys.map((key) =>
          <button key={key.credential_id} type="button" className="lite-id-item-row" onClick={() => onOpenDetails('passkey', key)}>
            <span><strong>{key.friendly_name || 'Passkey'}</strong><small>{key.active ? 'Active' : 'Revoked'} · Added {key.created_at || 'time unavailable'}</small></span><span>Details</span>
          </button>) : <StateSurface tone="neutral" title="No passkeys" description="You can add a passkey if your browser supports it." />}
      </div> : null}
      {effectiveSection === 'sessions' ? <div className="lite-id-manage-list">
        <p>Review sessions reported by Pocket Lab. Revoking a session may interrupt work on that device.</p>
        {!Array.isArray(data?.sessions) ? <StateSurface tone="neutral" title="Sessions unavailable" description="No current session list was reported." /> : data.sessions.map((item) =>
          <button key={item.session_id} type="button" className="lite-id-item-row" onClick={() => onOpenDetails('session', item)}>
            <span><strong>{item.active ? (item.current ? 'Current session' : 'Other session') : 'Inactive session'}</strong><small>{item.auth_method || 'Method not reported'} · Expires {item.absolute_expires_at || 'not reported'}</small></span><span>Details</span>
          </button>)}
        {view.sessions === 0 ? <StateSurface tone="neutral" title="No active sessions reported" description="Refresh to confirm the latest sign-in state." /> : null}
        {view.sessions > 1 ? <LiteButton variant="secondary" onClick={onSignOutOthers} disabled={readOnly || Boolean(busy)}>Sign Out Other Sessions</LiteButton> : null}
      </div> : null}
      {effectiveSection === 'recovery' ? <div className="lite-id-manage-list">
        <p>{view.recoveryConfigured === true ? 'Recovery is configured.' : 'Recovery is not confirmed.'} {view.remaining == null ? 'Unused code count unavailable.' : view.remaining + ' unused codes reported.'}</p>
        <button type="button" className="lite-id-item-row" onClick={() => onOpenDetails('recovery', {})}><span><strong>Recovery Details</strong><small>Understand readiness and regeneration consequences.</small></span><span>Details</span></button>
        <LiteButton variant="secondary" onClick={onRegenerate} disabled={Boolean(busy) || readOnly}><LifeBuoy size={16} aria-hidden="true" /> Generate New Codes</LiteButton>
        {recoveryCodes.length ? <div className="lite-identity-recovery-codes" data-private-ephemeral-result="true"><strong>Private recovery codes — shown only once. Store securely and close this panel when finished.</strong><code>{recoveryCodes.join('\n')}</code><LiteButton variant="secondary" onClick={onCopyCodes}>Copy Codes</LiteButton></div> : null}
        {(data?.person?.password_configured || data?.owner?.password_configured) ? <form className="lite-identity-form" onSubmit={onChangePassword}>
          <label className="lite-identity-form-field"><span>Current password</span><input className="pocket-input" type="password" autoComplete="current-password" value={passwordForm.current_password} onChange={(event) => onPasswordForm({ ...passwordForm, current_password: event.target.value })} required /></label>
          <label className="lite-identity-form-field"><span>New password</span><input className="pocket-input" type="password" autoComplete="new-password" value={passwordForm.new_password} onChange={(event) => onPasswordForm({ ...passwordForm, new_password: event.target.value })} required /></label>
          <p>Changing your password signs out other sessions.</p><LiteButton type="submit" disabled={readOnly || Boolean(busy)}>Change Password</LiteButton>
        </form> : null}

      </div> : null}
      {effectiveSection === 'activity' ? <IdentityActivityTimeline items={data?.recent_activity} onDetails={(item) => onOpenDetails('activity', item)} /> : null}
      {effectiveSection === 'approvals' ? <OwnerOperationApprovals operations={ownerOperations} fresh={ownerOperationsFresh} busy={busy} onApprove={onApproveOwnerOperation} onReject={onRejectOwnerOperation} /> : null}
      {effectiveSection === 'automation' ? <TrustedAutomationClients clients={ownerOperationClients} pairings={ownerOperationPairings} fresh={ownerOperationsFresh} busy={busy} onApprove={onApproveOwnerClientPairing} onReject={onRejectOwnerClientPairing} onRevoke={onRevokeOwnerOperationClient} /> : null}
      {effectiveSection === 'settings' ? <div className="lite-id-manage-list">
        <button type="button" className="lite-id-item-row" onClick={() => onOpenDetails('mode', {})}><span><strong>Workspace mode</strong><small>{view.mode}. Review consequences before changing mode.</small></span><span>Details</span></button>
        {!enterpriseEnabled ? <><p>Personal Mode keeps local Owner access simple. Enterprise Mode enables separate people and server-managed roles.</p><LiteButton variant="secondary" onClick={onReviewEnterprise}>{showEnterpriseOptIn ? 'Hide Enterprise option' : 'Review Enterprise Mode'}</LiteButton>{showEnterpriseOptIn ? <div><StateSurface tone="neutral" title="Switching modes signs out sessions" description="Owner passkey confirmation may be required. Role authority will be resolved again after sign-in." /><LiteButton onClick={onEnableEnterprise} disabled={readOnly || Boolean(busy)}>Enable Enterprise Mode</LiteButton></div> : null}</> : enterpriseContent}
        <LiteButton variant="secondary" onClick={onSignOut} disabled={readOnly || Boolean(busy)}><LogOut aria-hidden="true" size={16} /> Sign Out</LiteButton>
      </div> : null}
      {(effectiveSection === 'people' || effectiveSection === 'roles') && enterpriseEnabled ? enterpriseContent : null}
    </AccessManageNavigation>
  </div>;
}
