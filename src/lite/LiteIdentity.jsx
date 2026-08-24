import './identityRules.css';
import React, { useEffect, useMemo, useState } from 'react';
import { Copy, Fingerprint, KeyRound, LogIn, RefreshCw, ShieldCheck } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { getLiteReasonPresentation, identityActionStageLabel } from '../lib/identityRulesPresentation.js';
import { takePendingOwnerClaim } from '../lib/liteOwnerClaim.js';
import { createLitePasskey, getLitePasskey, webAuthnAvailable } from '../lib/liteWebAuthn.js';
import LiteIdentityEnterprise from './LiteIdentityEnterprise.jsx';
import { LiteSheet } from './LiteOverlay.jsx';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  PageHeader,
  LiteButton,
  LiteRefreshButton,
  LoadingCard,
  copyTextToClipboard,
} from './LiteUi.jsx';

function IdentityField({ label, ...props }) {
  return (
    <label className="lite-identity-form-field">
      <span>{label}</span>
      <input className="pocket-input" {...props} />
    </label>
  );
}

function ActionNotice({ notice, actionStage }) {
  if (!notice && !actionStage) return null;
  const title = notice?.title || identityActionStageLabel(actionStage) || 'Working';
  const message = notice?.message || 'Pocket Lab is verifying this change with the server.';
  return (
    <div role="status" aria-live="polite" className="mt-4">
      <StateSurface
        tone={notice?.error ? 'degraded' : actionStage === 'completed' ? 'healthy' : 'neutral'}
        title={title}
        description={message}
      />
    </div>
  );
}

function errorReason(error) {
  return error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
}

export default function IdentityScreen() {
  const {
    data,
    loading,
    error,
    refresh,
    cacheStatus,
    refreshing,
    savedStateOnly,
    backendReachable,
    lastUpdatedLabel,
    isExpired,
    backendDegraded,
  } = useLiteResource(liteApi.identity, []);
  const [busy, setBusy] = useState('');
  const [actionStage, setActionStage] = useState('');
  const [notice, setNotice] = useState(null);
  const [recoveryCodes, setRecoveryCodes] = useState([]);
  const [showRecovery, setShowRecovery] = useState(false);
  const [advancedSetup, setAdvancedSetup] = useState(false);
  const [advancedSignIn, setAdvancedSignIn] = useState(false);
  const [showEnterpriseOptIn, setShowEnterpriseOptIn] = useState(false);
  const [claimState, setClaimState] = useState({ checked: false, active: false, status: '' });
  const [passkeyProfile, setPasskeyProfile] = useState({ username: 'owner', display_name: 'Pocket Lab Owner', friendly_name: 'Primary passkey' });
  const [setup, setSetup] = useState({ username: 'owner', display_name: 'Pocket Lab Owner', password: '', setup_token: '' });
  const [login, setLogin] = useState({ username: 'owner', password: '' });
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' });
  const [recover, setRecover] = useState({ username: 'owner', recovery_code: '', new_password: '' });
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameName, setRenameName] = useState('');
  const [confirmation, setConfirmation] = useState(null);

  const activeSessions = useMemo(() => (data?.sessions || []).filter((item) => item.active), [data?.sessions]);
  const activePasskeys = useMemo(() => (data?.passkeys || []).filter((item) => item.active), [data?.passkeys]);
  const passkeyEligible = webAuthnAvailable();
  const status = data?.setup_required ? 'review' : data?.authenticated ? 'healthy' : 'degraded';
  const enterpriseRole = data?.enterprise?.current_membership?.role || '';

  useEffect(() => {
    let cancelled = false;
    async function hydrateClaim() {
      const rawClaim = takePendingOwnerClaim();
      try {
        if (rawClaim) {
          const result = await liteApi.consumeOwnerClaim(rawClaim);
          if (!cancelled) setClaimState({ checked: true, active: true, status: result?.status || 'claim_verified' });
          return;
        }
        const claim = await liteApi.ownerClaimStatus();
        if (!cancelled) setClaimState({ checked: true, active: Boolean(claim?.active), status: claim?.status || '' });
      } catch (claimError) {
        if (!cancelled) {
          setClaimState({ checked: true, active: false, status: errorReason(claimError) || 'claim_unavailable' });
          if (rawClaim) setNotice({ error: true, title: 'Owner setup link unavailable', message: claimError?.message || 'The owner claim could not be verified.' });
        }
      }
    }
    hydrateClaim();
    return () => { cancelled = true; };
  }, []);

  async function run(name, callback, successMessage, { refreshAfter = true } = {}) {
    setBusy(name);
    setActionStage('preparing');
    setNotice({ title: 'Preparing', message: 'Pocket Lab is preparing this protected change.' });
    try {
      setActionStage('pending');
      setNotice({ title: 'Waiting for Pocket Lab', message: 'No success is shown until the server accepts and verifies this action.' });
      const result = await callback();
      setActionStage('accepted');
      setNotice({ title: 'Server accepted', message: 'The server accepted the request. Verifying current Identity state now.' });
      if (refreshAfter) {
        setActionStage('verifying');
        await refresh();
      }
      setActionStage('completed');
      setNotice({ title: 'Completed', message: result?.summary || successMessage });
      return result;
    } catch (err) {
      const reason = getLiteReasonPresentation(errorReason(err), err?.message || 'Pocket Lab could not complete that identity action.');
      setActionStage(reason.tone === 'blocked' ? 'blocked' : 'failed');
      setNotice({ error: true, title: reason.title, message: reason.message });
      return null;
    } finally {
      setBusy('');
    }
  }

  function requestConfirmation({ title, description, confirmLabel, onConfirm }) {
    setConfirmation({ title, description, confirmLabel, onConfirm });
  }

  async function confirmRequestedAction() {
    const requested = confirmation;
    setConfirmation(null);
    if (requested?.onConfirm) await requested.onConfirm();
  }

  async function createOwnerWithPasskey(event) {
    event.preventDefault();
    const result = await run('claim-passkey', async () => {
      const options = await liteApi.ownerClaimPasskeyOptions({ username: passkeyProfile.username, display_name: passkeyProfile.display_name });
      const credential = await createLitePasskey(options);
      return liteApi.verifyOwnerClaimPasskey({
        challenge: options.publicKey.challenge,
        credential,
        username: passkeyProfile.username,
        display_name: passkeyProfile.display_name,
        friendly_name: passkeyProfile.friendly_name,
      });
    }, 'Owner created with a passkey.');
    if (result?.recovery_codes) setRecoveryCodes(result.recovery_codes);
    if (result) setClaimState({ checked: true, active: false, status: 'completed' });
  }

  async function setupOwner(event) {
    event.preventDefault();
    const result = await run('setup', () => liteApi.setupIdentity(setup), 'Owner created and signed in.');
    if (result) setSetup((value) => ({ ...value, password: '', setup_token: '' }));
  }

  async function signInWithPasskey() {
    await run('passkey-login', async () => {
      const options = await liteApi.passkeyLoginOptions();
      const credential = await getLitePasskey(options);
      return liteApi.verifyPasskeyLogin({ challenge: options.publicKey.challenge, credential });
    }, 'Signed in with your passkey.');
  }

  async function signIn(event) {
    event.preventDefault();
    const result = await run('login', () => liteApi.loginIdentity(login), 'Signed in.');
    if (result) setLogin((value) => ({ ...value, password: '' }));
  }

  async function addPasskey() {
    await run('add-passkey', async () => {
      const options = await liteApi.passkeyRegistrationOptions();
      const credential = await createLitePasskey(options);
      return liteApi.verifyPasskeyRegistration({ challenge: options.publicKey.challenge, credential, friendly_name: `Passkey ${activePasskeys.length + 1}` });
    }, 'Passkey added.');
  }

  function renamePasskey(passkey) {
    setRenameTarget(passkey);
    setRenameName(passkey.friendly_name || 'Passkey');
  }

  async function confirmRenamePasskey(event) {
    event.preventDefault();
    const passkey = renameTarget;
    const nextName = renameName.trim();
    if (!passkey || !nextName || nextName === passkey.friendly_name) {
      setRenameTarget(null);
      return;
    }
    setRenameTarget(null);
    await run(`rename-${passkey.credential_id}`, () => liteApi.renameIdentityPasskey(passkey.credential_id, nextName), 'Passkey renamed.');
  }

  async function revokePasskey(passkey) {
    setBusy(`revoke-passkey-${passkey.credential_id}`);
    setActionStage('pending');
    setNotice({ title: 'Requesting sensitive change', message: 'Pocket Lab is checking whether recent passkey confirmation is required.' });
    try {
      try {
        await liteApi.revokeIdentityPasskey(passkey.credential_id);
      } catch (firstError) {
        if (firstError?.status !== 428 && errorReason(firstError) !== 'passkey_step_up_required') throw firstError;
        setActionStage('preparing');
        setNotice({ title: 'Confirm with your passkey', message: 'Passkey confirmation is required before this credential can be revoked.' });
        const options = await liteApi.passkeyStepUpOptions('identity.passkey.revoke');
        const credential = await getLitePasskey(options);
        await liteApi.verifyPasskeyStepUp({ purpose: 'identity.passkey.revoke', challenge: options.publicKey.challenge, credential });
        setNotice({ title: 'Confirmation completed', message: 'Pocket Lab is submitting the revocation again with recent passkey assurance.' });
        await liteApi.revokeIdentityPasskey(passkey.credential_id);
      }
      setActionStage('verifying');
      setNotice({ title: 'Server accepted', message: 'Revocation was accepted. Verifying the current passkey list.' });
      await refresh();
      setActionStage('completed');
      setNotice({ title: 'Passkey removed', message: 'The server confirmed this passkey is no longer active.' });
    } catch (err) {
      const reason = getLiteReasonPresentation(errorReason(err), err?.message || 'Pocket Lab could not remove that passkey.');
      setActionStage(reason.tone === 'blocked' ? 'blocked' : 'failed');
      setNotice({ error: true, title: reason.title, message: reason.message });
    } finally {
      setBusy('');
    }
  }

  async function recoverAccess(event) {
    event.preventDefault();
    const result = await run('recover', () => liteApi.recoverIdentity(recover), 'Access recovered and old sessions signed out.');
    if (result) {
      setRecover((value) => ({ ...value, recovery_code: '', new_password: '' }));
      setShowRecovery(false);
    }
  }

  async function changePassword(event) {
    event.preventDefault();
    const result = await run('password', () => liteApi.changeIdentityPassword(passwords), 'Password changed. Other sessions were signed out as required.');
    if (result) setPasswords({ current_password: '', new_password: '' });
  }

  async function generateRecoveryCodes() {
    const result = await run('recovery', () => liteApi.regenerateIdentityRecovery(), 'New recovery codes generated. The older set is no longer valid.');
    if (result?.codes) setRecoveryCodes(result.codes);
  }

  async function signOut() {
    await run('logout', () => liteApi.logoutIdentity(), 'Signed out.');
    setRecoveryCodes([]);
  }

  async function enableEnterpriseMode() {
    await run('enterprise-enable', () => liteApi.setEnterpriseMode(true), 'Enterprise Mode enabled. Active sessions were invalidated so server-managed roles can take effect.');
  }

  return (
    <>
      <PageHeader
        eyebrow="Identity"
        title="Identity & Access"
        description="Use a passkey for normal access, review active sessions, keep recovery local, and add server-managed roles only when Enterprise Mode is enabled."
        actions={<LiteRefreshButton scope="identity" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <section className="lite-identity-hero" aria-labelledby="identity-posture-title">
        <div className="lite-identity-hero-copy">
          <div className="lite-home-pill"><span className="lite-ready-dot" />{data?.authenticated ? 'Owner signed in' : data?.setup_required ? 'Owner setup needed' : 'Sign in required'}</div>
          <h2 id="identity-posture-title">{data?.authenticated ? 'Your local access is protected.' : data?.setup_required ? 'Create the local Pocket Lab owner.' : 'Sign in before making protected changes.'}</h2>
          <p>{data?.summary || 'Pocket Lab keeps human sign-in separate from device and service identities.'}</p>
        </div>
        <div className="lite-identity-status-card">
          <div className="lite-identity-icon"><Fingerprint className="h-7 w-7" /></div>
          <span>Owner access</span>
          <strong>{data?.authenticated ? 'Signed in' : data?.setup_required ? 'Setup' : 'Signed out'}</strong>
          <StatusBadge status={status}>{data?.authenticated ? 'Protected' : 'Action needed'}</StatusBadge>
        </div>
      </section>

      {loading ? <LoadingCard label="Checking Identity & Access..." /> : null}
      {error && !data ? <StateSurface tone="degraded" title="Identity is unavailable" description={String(error)} className="mb-5" /> : null}
      {savedStateOnly ? <StateSurface tone="neutral" title="Showing saved Identity state" description={`${isExpired ? 'This saved state is old. ' : ''}${lastUpdatedLabel || 'Pocket Lab will refresh when the backend is reachable.'} Sign-in and protected write actions still require the live server.`} className="mb-5" /> : null}
      {backendDegraded && backendReachable ? <StateSurface tone="degraded" title="Identity needs attention" description="Pocket Lab is reachable, but one or more Identity checks are degraded. Protected changes remain server-authorized." className="mb-5" /> : null}

      {!loading && data?.setup_required ? (
        <GlassCard className="lite-identity-card lite-identity-auth-card">
          <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><Fingerprint className="h-5 w-5" /></div><span className="lite-identity-soft-badge">First owner</span></div>
          <h2>{claimState.active ? 'Create your passkey' : 'Open your owner connect link'}</h2>
          {claimState.active ? (
            <>
              <p>The short-lived owner claim is verified and no longer remains in the address bar. Finish setup with a platform passkey.</p>
              {!passkeyEligible ? <StateSurface tone="degraded" title="Passkeys are not ready here" description="Use Pocket Lab over HTTPS, or use Advanced setup as the local fallback." className="mb-4" /> : null}
              <form className="lite-identity-form" onSubmit={createOwnerWithPasskey}>
                <IdentityField label="Owner name" value={passkeyProfile.username} onChange={(event) => setPasskeyProfile({ ...passkeyProfile, username: event.target.value })} autoComplete="username" />
                <IdentityField label="Display name" value={passkeyProfile.display_name} onChange={(event) => setPasskeyProfile({ ...passkeyProfile, display_name: event.target.value })} autoComplete="name" />
                <IdentityField label="Passkey name" value={passkeyProfile.friendly_name} onChange={(event) => setPasskeyProfile({ ...passkeyProfile, friendly_name: event.target.value })} autoComplete="off" />
                <LiteButton type="submit" disabled={Boolean(busy) || !passkeyEligible}>{busy === 'claim-passkey' ? 'Creating passkey…' : 'Create Passkey'}</LiteButton>
              </form>
            </>
          ) : <p>Create a short-lived owner claim from the trusted Pocket Lab local setup channel, then open that link on this browser. The normal flow does not ask you to type a setup token or password.</p>}
          <div className="mt-5"><LiteButton variant="secondary" onClick={() => setAdvancedSetup((value) => !value)}>{advancedSetup ? 'Hide Advanced Setup' : 'Advanced Setup'}</LiteButton></div>
          {advancedSetup ? (
            <div className="lite-identity-advanced mt-4">
              <p>Manual setup remains available for recovery or browsers where passkeys are not eligible. These values are never saved in browser storage.</p>
              <form className="lite-identity-form" onSubmit={setupOwner}>
                <IdentityField label="Owner name" value={setup.username} onChange={(event) => setSetup({ ...setup, username: event.target.value })} autoComplete="username" />
                <IdentityField label="Display name" value={setup.display_name} onChange={(event) => setSetup({ ...setup, display_name: event.target.value })} autoComplete="name" />
                <IdentityField label="Password" type="password" value={setup.password} onChange={(event) => setSetup({ ...setup, password: event.target.value })} autoComplete="new-password" />
                <IdentityField label="One-time setup token" type="password" value={setup.setup_token} onChange={(event) => setSetup({ ...setup, setup_token: event.target.value })} autoComplete="off" />
                <LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'setup' ? 'Creating…' : 'Create Owner Manually'}</LiteButton>
              </form>
            </div>
          ) : null}
        </GlassCard>
      ) : null}

      {!loading && data?.owner && !data?.authenticated ? (
        <div className="lite-identity-grid">
          <GlassCard className="lite-identity-card lite-identity-auth-card">
            <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><LogIn className="h-5 w-5" /></div><StatusBadge status="review">Signed out</StatusBadge></div>
            <h2>Sign in</h2>
            <p>Use your passkey for normal sign-in. Password sign-in remains under Advanced when configured.</p>
            <LiteButton onClick={signInWithPasskey} disabled={Boolean(busy) || !data?.sign_in_methods?.passkey || !passkeyEligible}>{busy === 'passkey-login' ? 'Checking passkey…' : 'Sign In with Passkey'}</LiteButton>
            <div className="mt-4"><LiteButton variant="secondary" onClick={() => setAdvancedSignIn((value) => !value)}>{advancedSignIn ? 'Hide Advanced Sign-In' : 'Advanced Sign-In'}</LiteButton></div>
            {advancedSignIn && data?.sign_in_methods?.password ? (
              <form className="lite-identity-form mt-4" onSubmit={signIn}>
                <IdentityField label="Owner name" value={login.username} onChange={(event) => setLogin({ ...login, username: event.target.value })} autoComplete="username" />
                <IdentityField label="Password" type="password" value={login.password} onChange={(event) => setLogin({ ...login, password: event.target.value })} autoComplete="current-password" />
                <LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'login' ? 'Signing in…' : 'Sign In with Password'}</LiteButton>
              </form>
            ) : null}
          </GlassCard>
          <GlassCard className="lite-identity-card">
            <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><KeyRound className="h-5 w-5" /></div><span className="lite-identity-soft-badge">Recovery</span></div>
            <h2>Recover access</h2>
            <p>Use one unused recovery code to set a new password. Previous sessions are revoked.</p>
            {!showRecovery ? <LiteButton variant="secondary" onClick={() => setShowRecovery(true)}>Use Recovery Code</LiteButton> : (
              <form className="lite-identity-form" onSubmit={recoverAccess}>
                <IdentityField label="Owner name" value={recover.username} onChange={(event) => setRecover({ ...recover, username: event.target.value })} autoComplete="username" />
                <IdentityField label="Recovery code" type="password" value={recover.recovery_code} onChange={(event) => setRecover({ ...recover, recovery_code: event.target.value })} autoComplete="off" />
                <IdentityField label="New password" type="password" value={recover.new_password} onChange={(event) => setRecover({ ...recover, new_password: event.target.value })} autoComplete="new-password" />
                <LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'recover' ? 'Recovering…' : 'Recover Access'}</LiteButton>
              </form>
            )}
          </GlassCard>
        </div>
      ) : null}

      {data?.authenticated ? (
        <>
          <div className="lite-identity-posture-strip" aria-label="Access posture">
            <div><span>Owner</span><strong>{data?.owner?.display_name || 'Pocket Lab Owner'}</strong><small>{enterpriseRole ? `${enterpriseRole} role` : 'Personal Mode'}</small></div>
            <div><span>Passkeys</span><strong>{activePasskeys.length ? `${activePasskeys.length} ready` : 'Needs attention'}</strong><small>{passkeyEligible ? 'Browser eligible' : 'HTTPS/passkey support needed'}</small></div>
            <div><span>Sessions</span><strong>{activeSessions.length} active</strong><small>{activeSessions.some((session) => session.current) ? 'Current session verified' : 'Session posture available'}</small></div>
            <div><span>Recovery</span><strong>{data?.recovery?.configured ? 'Ready' : 'Needs attention'}</strong><small>{data?.recovery?.configured ? `${data.recovery.remaining} unused` : 'Generate a recovery set'}</small></div>
          </div>

          <div className="lite-identity-grid mt-5">
            <GlassCard className="lite-identity-card">
              <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><ShieldCheck className="h-5 w-5" /></div><StatusBadge status="healthy">Owner</StatusBadge></div>
              <h2>{data?.owner?.display_name || 'Pocket Lab Owner'}</h2>
              <p>@{data?.owner?.username || 'owner'} · Signed in with {data?.session?.auth_method || 'server session'}</p>
              <div className="lite-identity-checklist"><div><span className="lite-check-dot" />HttpOnly server session</div><div><span className="lite-check-dot" />CSRF-protected changes</div><div><span className="lite-check-dot" />Fixed idle and absolute expiry</div></div>
              <div className="mt-5"><LiteButton variant="secondary" onClick={signOut} disabled={Boolean(busy)}>{busy === 'logout' ? 'Signing out…' : 'Sign Out'}</LiteButton></div>
            </GlassCard>

            <GlassCard className="lite-identity-card lite-identity-action-card">
              <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><Fingerprint className="h-5 w-5" /></div><StatusBadge status={activePasskeys.length ? 'healthy' : 'review'}>{activePasskeys.length ? `${activePasskeys.length} active` : 'Needs attention'}</StatusBadge></div>
              <h2>Passkeys</h2>
              <p>Add friendly passkey names for this owner. Removing a passkey may require a recent passkey confirmation.</p>
              <LiteButton onClick={addPasskey} disabled={Boolean(busy) || !passkeyEligible}>{busy === 'add-passkey' ? 'Adding…' : 'Add Passkey'}</LiteButton>
              <div className="lite-identity-session-list mt-4">
                {(data?.passkeys || []).length ? data.passkeys.map((passkey) => (
                  <div key={passkey.credential_id} className="lite-identity-session-row">
                    <div><strong>{passkey.friendly_name || 'Passkey'}</strong><span>{passkey.active ? `Created ${passkey.created_at ? formatLiteTime(passkey.created_at) : 'earlier'} · Last used ${passkey.last_used_at ? formatLiteTime(passkey.last_used_at) : 'not yet'}` : 'Revoked'}</span></div>
                    {passkey.active ? <div className="lite-identity-inline-actions"><LiteButton variant="secondary" onClick={() => renamePasskey(passkey)} disabled={Boolean(busy)}>Rename</LiteButton><LiteButton variant="secondary" onClick={() => revokePasskey(passkey)} disabled={Boolean(busy)}>Remove</LiteButton></div> : <StatusBadge status="neutral">Revoked</StatusBadge>}
                  </div>
                )) : <StateSurface tone="neutral" title="No passkeys yet" description="Add a passkey to use passkey-first sign-in and step-up protection." />}
              </div>
            </GlassCard>
          </div>

          <div className="lite-identity-grid mt-5">
            <GlassCard className="lite-identity-card">
              <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><RefreshCw className="h-5 w-5" /></div><StatusBadge status={data?.recovery?.configured ? 'healthy' : 'review'}>{data?.recovery?.configured ? `${data.recovery.remaining} unused` : 'Not created'}</StatusBadge></div>
              <h2>Recovery</h2>
              <p>Generating a new one-time recovery set invalidates every code from the older set.</p>
              <LiteButton variant="secondary" onClick={() => requestConfirmation({ title: 'Generate new recovery codes?', description: 'The current recovery codes will stop working. New codes are shown once in this browser result and are not stored by the frontend.', confirmLabel: 'Generate New Codes', onConfirm: generateRecoveryCodes })} disabled={Boolean(busy)}>{busy === 'recovery' ? 'Generating…' : 'Generate New Codes'}</LiteButton>
              {recoveryCodes.length ? (
                <div className="lite-identity-recovery-codes">
                  <div className="lite-identity-safe-note"><strong>Save these now</strong><span>They are shown only in this result and are not stored by the frontend.</span></div>
                  <code>{recoveryCodes.join('\n')}</code>
                  <LiteButton variant="secondary" onClick={() => copyTextToClipboard(recoveryCodes.join('\n'))}><Copy className="h-4 w-4" /> Copy Codes</LiteButton>
                </div>
              ) : null}
            </GlassCard>

            <GlassCard className="lite-identity-card">
              <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><Fingerprint className="h-5 w-5" /></div><StatusBadge status="healthy">{activeSessions.length} active</StatusBadge></div>
              <h2>Sessions</h2>
              <p>Current and other owner sessions remain distinct. Raw cookies and session tokens are never displayed.</p>
              <div className="lite-identity-session-list">
                {activeSessions.length ? activeSessions.map((session) => (
                  <div key={session.session_id} className="lite-identity-session-row">
                    <div><strong>{session.current ? 'This device' : 'Other owner session'}</strong><span>{session.auth_method || 'server session'} · created {formatLiteTime(session.created_at)} · expires {formatLiteTime(session.absolute_expires_at)}</span></div>
                    {!session.current ? <LiteButton variant="secondary" onClick={() => requestConfirmation({ title: 'Sign out this session?', description: 'This signs out only the selected owner session after the server confirms the revocation.', confirmLabel: 'Sign Out Session', onConfirm: () => run(`revoke-${session.session_id}`, () => liteApi.revokeIdentitySession(session.session_id), 'The selected session was signed out.') })} disabled={Boolean(busy)}>Sign Out</LiteButton> : <StatusBadge status="healthy">Current</StatusBadge>}
                  </div>
                )) : <StateSurface tone="neutral" title="No active sessions" description="Active owner sessions will appear here without exposing session tokens." />}
              </div>
              {activeSessions.length > 1 ? <LiteButton variant="secondary" onClick={() => requestConfirmation({ title: 'Sign out other sessions?', description: 'Your current session stays active. Other active owner sessions are revoked only after the server confirms the request.', confirmLabel: 'Sign Out Others', onConfirm: () => run('revoke-others', () => liteApi.revokeOtherIdentitySessions(), 'Other sessions were signed out.') })} disabled={Boolean(busy)}>Sign Out Other Sessions</LiteButton> : null}
            </GlassCard>
          </div>

          {data?.owner?.password_configured ? (
            <details className="lite-identity-advanced lite-identity-advanced-card mt-5">
              <summary>Advanced password access</summary>
              <GlassCard className="lite-identity-card mt-3">
                <h2>Change password</h2>
                <p>Password access remains available for existing owners and recovery. Changing it signs out other sessions.</p>
                <form className="lite-identity-form" onSubmit={changePassword}>
                  <IdentityField label="Current password" type="password" value={passwords.current_password} onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })} autoComplete="current-password" />
                  <IdentityField label="New password" type="password" value={passwords.new_password} onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })} autoComplete="new-password" />
                  <LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'password' ? 'Changing…' : 'Change Password'}</LiteButton>
                </form>
              </GlassCard>
            </details>
          ) : null}

          {!data?.enterprise?.enabled ? (
            <GlassCard className="lite-identity-card mt-5">
              <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><ShieldCheck className="h-5 w-5" /></div><span className="lite-identity-soft-badge">Optional</span></div>
              <h2>Additional access options</h2>
              <p>Personal Mode stays simple by default. Enable Enterprise Mode only when you need server-managed roles and independent governance.</p>
              <LiteButton variant="secondary" onClick={() => setShowEnterpriseOptIn((value) => !value)} disabled={Boolean(busy)}>{showEnterpriseOptIn ? 'Hide Option' : 'Review Option'}</LiteButton>
              {showEnterpriseOptIn ? <div className="lite-identity-advanced mt-4"><p>Enabling Enterprise Mode keeps the local Owner, signs out active sessions, and moves role authority to the server.</p><LiteButton onClick={() => requestConfirmation({ title: 'Enable Enterprise Mode?', description: 'Active sessions will be signed out so server-managed role authority can take effect. Personal Mode remains the default unless you confirm this change.', confirmLabel: 'Enable Enterprise Mode', onConfirm: enableEnterpriseMode })} disabled={Boolean(busy)}>{busy === 'enterprise-enable' ? 'Enabling…' : 'Enable Enterprise Mode'}</LiteButton></div> : null}
            </GlassCard>
          ) : <LiteIdentityEnterprise enterprise={data.enterprise} recentActivity={data?.recent_activity || []} onIdentityRefresh={refresh} />}

          <GlassCard className="lite-identity-card mt-5">
            <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><ShieldCheck className="h-5 w-5" /></div><span className="lite-identity-soft-badge">Activity</span></div>
            <h2>Identity activity</h2>
            <p>Bounded, sanitized owner activity. Claims, passkeys, sessions and recovery never expose secret material here.</p>
            <div className="lite-identity-activity-list">
              {(data?.recent_activity || []).length ? data.recent_activity.map((item, index) => {
                const reason = getLiteReasonPresentation(item.reason_code, item.summary || 'Identity activity');
                return <div key={`${item.correlation_id || item.occurred_at}-${index}`} className="lite-identity-session-row"><div><strong>{item.summary}</strong><span>{reason.title} · {formatLiteTime(item.occurred_at)}</span></div><details className="lite-identity-event-details"><summary>Details</summary><code>{item.reason_code || 'none'}</code></details></div>;
              }) : <StateSurface tone="neutral" title="No identity activity yet" description="Sanitized identity events will appear here after sign-in, passkey, session, recovery or membership changes." />}
            </div>
          </GlassCard>
        </>
      ) : null}

      <ActionNotice notice={notice} actionStage={actionStage} />

      <LiteSheet open={Boolean(renameTarget)} onClose={() => setRenameTarget(null)} title="Rename passkey" eyebrow="Passkey" description="Choose a friendly name. The credential identifier remains hidden from normal UI." className="lite-identity-sheet">
        <form className="lite-identity-form" onSubmit={confirmRenamePasskey}>
          <IdentityField label="Passkey name" value={renameName} onChange={(event) => setRenameName(event.target.value)} autoFocus maxLength="80" />
          <div className="lite-identity-sheet-actions"><LiteButton type="button" variant="secondary" onClick={() => setRenameTarget(null)}>Cancel</LiteButton><LiteButton type="submit" disabled={!renameName.trim()}>Save Name</LiteButton></div>
        </form>
      </LiteSheet>

      <LiteSheet open={Boolean(confirmation)} onClose={() => setConfirmation(null)} title={confirmation?.title || 'Confirm change'} eyebrow="Confirm" description={confirmation?.description || ''} className="lite-identity-sheet">
        <div className="lite-identity-confirmation">
          <StateSurface tone="neutral" title="Pocket Lab will verify this on the server" description="The interface will not claim success until the server accepts the request and refreshed Identity state is available." />
          <div className="lite-identity-sheet-actions"><LiteButton variant="secondary" onClick={() => setConfirmation(null)}>Cancel</LiteButton><LiteButton onClick={confirmRequestedAction}>{confirmation?.confirmLabel || 'Confirm'}</LiteButton></div>
        </div>
      </LiteSheet>
    </>
  );
}
