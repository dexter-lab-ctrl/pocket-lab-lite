import './identityRules.css';
import './identityRulesGovernance.css';
import React, { useEffect, useMemo, useState } from 'react';
import { Copy, Fingerprint, KeyRound, LogIn, RefreshCw, ShieldCheck, UserCheck } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { clearLiteIdentityCsrf, formatLiteTime, liteApi } from '../lib/liteApi.js';
import { liteEnterpriseApi } from '../lib/liteEnterpriseApi.js';
import { getLiteReasonPresentation, identityActionStageLabel, buildLiteIdentityAccessOverview } from '../lib/identityRulesPresentation.js';
import { takePendingOwnerClaim } from '../lib/liteOwnerClaim.js';
import { takePendingPersonClaim } from '../lib/litePersonClaim.js';
import { createLitePasskey, getLitePasskey, webAuthnAvailable } from '../lib/liteWebAuthn.js';
import { triggerLiteHaptic } from '../lib/liteNativeFeedback.js';
import { useLiteUiStore } from '../stores/liteUiStore.js';
import LiteIdentityEnterprise from './LiteIdentityEnterprise.jsx';
import LiteHelp, { LiteHelpHeading } from './LiteHelp.jsx';
import { LiteSheet } from './LiteOverlay.jsx';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  PageHeader,
  LiteButton,
  LiteActionRow,
  LiteOperationalStory,
  LiteRefreshButton,
  LoadingCard,
  copyTextToClipboard,
} from './LiteUi.jsx';

function IdentityField({ label, hint = '', ...props }) {
  return (
    <label className="lite-identity-form-field">
      <span>{label}</span>
      <input className="pocket-input" {...props} />
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

function ActionNotice({ notice, actionStage }) {
  if (!notice && !actionStage) return null;
  return (
    <div role="status" aria-live="polite" className="mt-4">
      <StateSurface
        tone={notice?.error ? 'degraded' : actionStage === 'completed' ? 'healthy' : 'neutral'}
        title={notice?.title || identityActionStageLabel(actionStage) || 'Working'}
        description={notice?.message || 'Pocket Lab is verifying this change with the server.'}
      />
    </div>
  );
}

function errorReason(error) {
  return error?.payload?.detail?.reason_code || error?.payload?.reason_code || '';
}

export default function IdentityScreen() {
  const identity = useLiteResource(liteEnterpriseApi.identitySelf, []);
  const { data, loading, error, refresh, cacheStatus, refreshing, savedStateOnly, backendReachable, lastUpdatedLabel, isExpired, backendDegraded } = identity;
  const [busy, setBusy] = useState('');
  const [actionStage, setActionStage] = useState('');
  const [notice, setNotice] = useState(null);
  const [recoveryCodes, setRecoveryCodes] = useState([]);
  const [showRecovery, setShowRecovery] = useState(false);
  const [advancedSetup, setAdvancedSetup] = useState(false);
  const [advancedSignIn, setAdvancedSignIn] = useState(false);
  const [showEnterpriseOptIn, setShowEnterpriseOptIn] = useState(false);
  const [ownerClaim, setOwnerClaim] = useState({ checked: false, active: false, status: '' });
  const [personClaim, setPersonClaim] = useState({ checked: false, active: false, status: '', person: null });
  const [passkeyProfile, setPasskeyProfile] = useState({ username: 'owner', display_name: 'Pocket Lab Owner', friendly_name: 'Primary passkey' });
  const [setup, setSetup] = useState({ username: 'owner', display_name: 'Pocket Lab Owner', password: '', setup_token: '' });
  const [login, setLogin] = useState({ username: '', password: '' });
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' });
  const [recover, setRecover] = useState({ username: '', recovery_code: '', new_password: '' });
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameName, setRenameName] = useState('');
  const [confirmation, setConfirmation] = useState(null);
  const [manageOpen, setManageOpen] = useState(false);
  const pushToast = useLiteUiStore((state) => state.pushToast);

  const activeSessions = useMemo(() => (data?.sessions || []).filter((item) => item.active), [data?.sessions]);
  const activePasskeys = useMemo(() => (data?.passkeys || []).filter((item) => item.active), [data?.passkeys]);
  const passkeyEligible = webAuthnAvailable();
  const identityReadOnly = savedStateOnly || !backendReachable;
  const enterpriseRole = data?.enterprise?.current_membership?.role || data?.person?.role || '';
  const currentPerson = data?.person || (data?.authenticated && data?.owner?.human_id ? {
    human_id: data.owner.human_id,
    username: data.owner.username,
    display_name: data.owner.display_name,
    status: data.owner.status,
    role: enterpriseRole || 'Owner',
    is_local_owner: true,
    password_configured: data.owner.password_configured,
  } : null);
  const personLabel = currentPerson?.display_name || data?.owner?.display_name || 'Pocket Lab person';
  const ownerConfigured = Boolean(data?.owner);
  const accessOverview = useMemo(() => buildLiteIdentityAccessOverview(data, {
    savedStateOnly,
    backendReachable,
    lastUpdatedLabel,
    isExpired,
    passkeyEligible,
    claimActive: ownerClaim.active || personClaim.active,
  }), [data, savedStateOnly, backendReachable, lastUpdatedLabel, isExpired, passkeyEligible, ownerClaim.active, personClaim.active]);

  useEffect(() => {
    let cancelled = false;
    async function hydrateClaims() {
      const rawPersonClaim = takePendingPersonClaim();
      if (rawPersonClaim) {
        try {
          await liteEnterpriseApi.consumeEnrollment(rawPersonClaim);
          const state = await liteEnterpriseApi.enrollmentStatus();
          if (!cancelled) setPersonClaim({ checked: true, active: Boolean(state?.active), status: state?.status || 'claim_verified', person: state?.person || null });
        } catch (claimError) {
          if (!cancelled) {
            setPersonClaim({ checked: true, active: false, status: errorReason(claimError) || 'claim_unavailable', person: null });
            setNotice({ error: true, title: 'Person connect link unavailable', message: claimError?.message || 'Pocket Lab could not verify this one-time connect link.' });
          }
        }
        return;
      }
      try {
        const state = await liteEnterpriseApi.enrollmentStatus();
        if (!cancelled) setPersonClaim({ checked: true, active: Boolean(state?.active), status: state?.status || '', person: state?.person || null });
      } catch (_error) {
        if (!cancelled) setPersonClaim({ checked: true, active: false, status: '', person: null });
      }

      const rawOwnerClaim = takePendingOwnerClaim();
      try {
        if (rawOwnerClaim) {
          const result = await liteApi.consumeOwnerClaim(rawOwnerClaim);
          if (!cancelled) setOwnerClaim({ checked: true, active: true, status: result?.status || 'claim_verified' });
          return;
        }
        const claim = await liteApi.ownerClaimStatus();
        if (!cancelled) setOwnerClaim({ checked: true, active: Boolean(claim?.active), status: claim?.status || '' });
      } catch (claimError) {
        if (!cancelled) {
          setOwnerClaim({ checked: true, active: false, status: errorReason(claimError) || 'claim_unavailable' });
          if (rawOwnerClaim) setNotice({ error: true, title: 'Owner setup link unavailable', message: claimError?.message || 'The owner claim could not be verified.' });
        }
      }
    }
    hydrateClaims();
    return () => { cancelled = true; };
  }, []);

  async function run(name, callback, successMessage, { refreshAfter = true, signedOutAfter = false } = {}) {
    setBusy(name);
    setActionStage('preparing');
    setNotice({ title: 'Preparing', message: 'Pocket Lab is preparing this protected identity change.' });
    try {
      setActionStage('pending');
      setNotice({ title: 'Waiting for Pocket Lab', message: 'Nothing is shown as completed until the server accepts the request.' });
      const result = await callback();
      if (signedOutAfter) clearLiteIdentityCsrf();
      setActionStage('verifying');
      setNotice({ title: 'Server accepted', message: 'Pocket Lab accepted the request. Reading current Identity state now.' });
      if (refreshAfter) await refresh();
      setActionStage('completed');
      setNotice({ title: 'Completed', message: result?.summary || successMessage });
      triggerLiteHaptic('success');
      pushToast({ id: `identity:${String(result?.correlation_id || result?.event_id || name).slice(0, 120)}`, kind: 'success', title: 'Identity updated', message: result?.summary || successMessage });
      return result;
    } catch (err) {
      const reason = getLiteReasonPresentation(errorReason(err), err?.message || 'Pocket Lab could not complete that identity action.');
      setActionStage(reason.tone === 'blocked' ? 'blocked' : 'failed');
      setNotice({ error: true, title: reason.title, message: reason.message });
      triggerLiteHaptic(reason.tone === 'blocked' ? 'blocked' : 'warning');
      pushToast({ id: `identity:${name}:problem`, kind: reason.tone === 'blocked' ? 'warning' : 'error', title: reason.title, message: reason.message });
      return null;
    } finally { setBusy(''); }
  }

  function requestConfirmation({ title, description, confirmLabel, onConfirm }) {
    setManageOpen(false);
    setConfirmation({ title, description, confirmLabel, onConfirm });
  }

  async function confirmRequestedAction() {
    const requested = confirmation;
    setConfirmation(null);
    triggerLiteHaptic('confirm');
    if (requested?.onConfirm) await requested.onConfirm();
  }

  async function withOwnerStepUp(purpose, callback) {
    try { return await callback(); }
    catch (firstError) {
      if (firstError?.status !== 428 && !['owner_step_up_required', 'passkey_step_up_required'].includes(errorReason(firstError))) throw firstError;
      setNotice({ title: 'Confirm with your passkey', message: 'This root-level change needs recent Owner confirmation.' });
      const options = await liteApi.passkeyStepUpOptions(purpose);
      const credential = await getLitePasskey(options);
      await liteApi.verifyPasskeyStepUp({ purpose, challenge: options.publicKey.challenge, credential });
      return callback();
    }
  }

  async function createOwnerWithPasskey(event) {
    event.preventDefault();
    const result = await run('claim-passkey', async () => {
      const options = await liteApi.ownerClaimPasskeyOptions({ username: passkeyProfile.username, display_name: passkeyProfile.display_name });
      const credential = await createLitePasskey(options);
      return liteApi.verifyOwnerClaimPasskey({ challenge: options.publicKey.challenge, credential, username: passkeyProfile.username, display_name: passkeyProfile.display_name, friendly_name: passkeyProfile.friendly_name });
    }, 'Owner created with a passkey.');
    if (result?.recovery_codes) setRecoveryCodes(result.recovery_codes);
    if (result) setOwnerClaim({ checked: true, active: false, status: 'completed' });
  }

  async function completePersonEnrollment(event) {
    event.preventDefault();
    const result = await run('person-passkey', async () => {
      const options = await liteEnterpriseApi.enrollmentPasskeyOptions();
      const credential = await createLitePasskey(options);
      return liteEnterpriseApi.verifyEnrollmentPasskey({ challenge: options.publicKey.challenge, credential, friendly_name: 'Primary passkey' });
    }, 'Your Pocket Lab access is ready.');
    if (result?.recovery_codes) setRecoveryCodes(result.recovery_codes);
    if (result) setPersonClaim({ checked: true, active: false, status: 'completed', person: result?.person || personClaim.person });
  }

  async function setupOwner(event) {
    event.preventDefault();
    const result = await run('setup', () => liteApi.setupIdentity(setup), 'Owner created and signed in.');
    if (result) setSetup((value) => ({ ...value, password: '', setup_token: '' }));
  }

  async function signInWithPasskey() {
    await run('passkey-login', async () => {
      const options = await liteEnterpriseApi.passkeyLoginOptions(login.username);
      const credential = await getLitePasskey(options);
      return liteEnterpriseApi.verifyPasskeyLogin({ challenge: options.publicKey.challenge, credential });
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
    setManageOpen(false);
    setRenameTarget(passkey);
    setRenameName(passkey.friendly_name || 'Passkey');
  }

  async function confirmRenamePasskey(event) {
    event.preventDefault();
    if (!renameTarget || !renameName.trim()) return;
    const passkey = renameTarget; const nextName = renameName.trim();
    setRenameTarget(null);
    await run(`rename-${passkey.credential_id}`, () => liteApi.renameIdentityPasskey(passkey.credential_id, nextName), 'Passkey renamed.');
  }

  async function revokePasskey(passkey) {
    await run(`revoke-passkey-${passkey.credential_id}`, async () => {
      try { return await liteApi.revokeIdentityPasskey(passkey.credential_id); }
      catch (firstError) {
        if (firstError?.status !== 428 && errorReason(firstError) !== 'passkey_step_up_required') throw firstError;
        const purpose = 'identity.passkey.revoke';
        const options = await liteApi.passkeyStepUpOptions(purpose);
        const credential = await getLitePasskey(options);
        await liteApi.verifyPasskeyStepUp({ purpose, challenge: options.publicKey.challenge, credential });
        return liteApi.revokeIdentityPasskey(passkey.credential_id);
      }
    }, 'Passkey removed.');
  }

  async function recoverAccess(event) {
    event.preventDefault();
    const result = await run('recover', () => liteApi.recoverIdentity(recover), 'Access recovered and previous sessions signed out.');
    if (result) { setRecover((value) => ({ ...value, recovery_code: '', new_password: '' })); setShowRecovery(false); }
  }

  async function changePassword(event) {
    event.preventDefault();
    const result = await run('password', () => liteApi.changeIdentityPassword(passwords), 'Password changed. Other sessions were signed out.');
    if (result) setPasswords({ current_password: '', new_password: '' });
  }

  async function generateRecoveryCodes() {
    const result = await run('recovery', () => liteApi.regenerateIdentityRecovery(), 'New recovery codes generated. The older set no longer works.');
    if (result?.codes) setRecoveryCodes(result.codes);
  }

  async function signOut() {
    await run('logout', () => liteApi.logoutIdentity(), 'Signed out.', { signedOutAfter: true });
    setRecoveryCodes([]);
  }

  async function enableEnterpriseMode() {
    const result = await run('enterprise-enable', () => withOwnerStepUp('enterprise.mode.change', () => liteEnterpriseApi.setMode(true)), 'Enterprise Mode enabled. Sign in again so server-managed role authority can take effect.', { signedOutAfter: true });
    if (result) setShowEnterpriseOptIn(false);
  }

  const workspaceStory = accessOverview.workspaceStory;
  const currentRoleLabel = enterpriseRole || (currentPerson?.is_local_owner ? 'Owner' : 'Personal Mode');

  return (
    <>
      <PageHeader
        eyebrow="Identity"
        title="Identity & Access"
        description="Who you are, how you sign in, and what Pocket Lab currently lets you do."
        actions={<div className="lite-governance-inline-actions"><LiteHelp helpKey="identity.overview" /><LiteRefreshButton scope="identity" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} /></div>}
      />

      <LiteOperationalStory
        className="lite-identity-operational-story"
        story={workspaceStory}
        primaryAction={workspaceStory.nextAction?.id === 'create_owner' ? { label: 'Create Owner', onClick: () => document.getElementById('identity-owner-setup')?.scrollIntoView({ block: 'start' }) } : workspaceStory.nextAction?.id === 'sign_in_passkey' ? { label: 'Sign in with Passkey', onClick: signInWithPasskey, disabled: Boolean(busy) || !passkeyEligible } : workspaceStory.nextAction?.id === 'add_passkey' ? { label: 'Add Passkey', onClick: addPasskey, disabled: Boolean(busy) || !passkeyEligible } : workspaceStory.nextAction?.id === 'review_recovery' ? { label: 'Review Recovery', onClick: () => setManageOpen(true) } : workspaceStory.nextAction?.id === 'refresh' ? { label: 'Refresh access', onClick: refresh } : null}
        manageAction={data?.authenticated && !identityReadOnly ? { label: 'Manage Access', onClick: () => setManageOpen(true) } : null}
      />

      {loading ? <LoadingCard label="Checking Identity & Access..." /> : null}
      {error && !data ? <StateSurface tone="degraded" title="Identity is unavailable" description={String(error)} className="mb-5" /> : null}
      {backendDegraded && backendReachable ? <StateSurface tone="degraded" title="Identity needs attention" description="Pocket Lab is reachable, but current access truth could not be fully proved. Protected changes remain server-authorized." className="mb-5" /> : null}

      {!loading && personClaim.active && !data?.authenticated ? (
        <GlassCard className="lite-identity-card lite-identity-auth-card">
          <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><UserCheck className="h-5 w-5" /></div><StatusBadge status="healthy">Connect link verified</StatusBadge></div>
          <LiteHelpHeading title={`Finish joining${personClaim.person?.display_name ? ` as ${personClaim.person.display_name}` : ''}`} helpKey="identity.people" as="h2" />
          <p>Your one-time connect link has been removed from the address bar. Create a passkey to activate this separate Pocket Lab identity.</p>
          {personClaim.person?.role ? <p><strong>Starting role:</strong> {personClaim.person.role}. Safety Rules will determine the effective actions for that role.</p> : null}
          {!passkeyEligible ? <StateSurface tone="degraded" title="Passkeys are not ready here" description="Open Pocket Lab over its HTTPS address on a browser with passkey support." /> : null}
          <form className="lite-identity-form mt-4" onSubmit={completePersonEnrollment}><LiteButton type="submit" disabled={Boolean(busy) || !passkeyEligible}>{busy === 'person-passkey' ? 'Creating passkey…' : 'Create Passkey and Join'}</LiteButton></form>
        </GlassCard>
      ) : null}

      {!loading && data?.setup_required && !identityReadOnly && !personClaim.active ? (
        <GlassCard id="identity-owner-setup" className="lite-identity-card lite-identity-auth-card">
          <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><Fingerprint className="h-5 w-5" /></div><span className="lite-identity-soft-badge">First owner</span></div>
          <LiteHelpHeading title={ownerClaim.active ? 'Create your Owner passkey' : 'Create the local Owner'} helpKey="identity.owner" as="h2" />
          {ownerClaim.active ? <><p>The short-lived Owner claim is verified and no longer remains in the address bar. Finish setup with a platform passkey.</p><form className="lite-identity-form" onSubmit={createOwnerWithPasskey}><IdentityField label="Owner name" value={passkeyProfile.username} onChange={(event) => setPasskeyProfile({ ...passkeyProfile, username: event.target.value })} autoComplete="username" /><IdentityField label="Display name" value={passkeyProfile.display_name} onChange={(event) => setPasskeyProfile({ ...passkeyProfile, display_name: event.target.value })} autoComplete="name" /><IdentityField label="Passkey name" value={passkeyProfile.friendly_name} onChange={(event) => setPasskeyProfile({ ...passkeyProfile, friendly_name: event.target.value })} autoComplete="off" /><LiteButton type="submit" disabled={Boolean(busy) || !passkeyEligible}>{busy === 'claim-passkey' ? 'Creating passkey…' : 'Create Passkey'}</LiteButton></form></> : <p>Use the trusted local setup flow to create the short-lived Owner connect link. Pocket Lab does not ask you to keep a reusable setup secret in the browser.</p>}
          <div className="mt-4"><LiteButton variant="secondary" onClick={() => setAdvancedSetup((value) => !value)}>{advancedSetup ? 'Hide Advanced Setup' : 'Advanced Setup'}</LiteButton></div>
          {advancedSetup ? <form className="lite-identity-form mt-4" onSubmit={setupOwner}><IdentityField label="Owner name" value={setup.username} onChange={(event) => setSetup({ ...setup, username: event.target.value })} autoComplete="username" /><IdentityField label="Display name" value={setup.display_name} onChange={(event) => setSetup({ ...setup, display_name: event.target.value })} autoComplete="name" /><IdentityField label="Password" type="password" value={setup.password} onChange={(event) => setSetup({ ...setup, password: event.target.value })} autoComplete="new-password" /><IdentityField label="One-time setup token" type="password" value={setup.setup_token} onChange={(event) => setSetup({ ...setup, setup_token: event.target.value })} autoComplete="off" /><LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'setup' ? 'Creating…' : 'Create Owner Manually'}</LiteButton></form> : null}
        </GlassCard>
      ) : null}

      {!loading && ownerConfigured && !data?.authenticated && !identityReadOnly && !personClaim.active ? (
        <div className="lite-identity-grid">
          <GlassCard className="lite-identity-card lite-identity-auth-card">
            <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><LogIn className="h-5 w-5" /></div><StatusBadge status="review">Signed out</StatusBadge></div>
            <LiteHelpHeading title="Sign in" helpKey="identity.passkeys" as="h2" />
            <p>Use a passkey for normal sign-in. In Enterprise Mode, every person signs in as their own identity; the server resolves the role after authentication.</p>
            <IdentityField label="Sign-in name (optional)" value={login.username} onChange={(event) => setLogin({ ...login, username: event.target.value })} autoComplete="username" hint="Leave blank to choose from passkeys available for this workspace." />
            <LiteButton variant="secondary" onClick={signInWithPasskey} disabled={Boolean(busy) || !data?.sign_in_methods?.passkey || !passkeyEligible}>{busy === 'passkey-login' ? 'Checking passkey…' : 'Sign In with Passkey'}</LiteButton>
            <div className="mt-4"><LiteButton variant="secondary" onClick={() => setAdvancedSignIn((value) => !value)}>{advancedSignIn ? 'Hide Advanced Sign-In' : 'Advanced Sign-In'}</LiteButton></div>
            {advancedSignIn && data?.sign_in_methods?.password ? <form className="lite-identity-form mt-4" onSubmit={signIn}><IdentityField label="Sign-in name" value={login.username} onChange={(event) => setLogin({ ...login, username: event.target.value })} autoComplete="username" /><IdentityField label="Password" type="password" value={login.password} onChange={(event) => setLogin({ ...login, password: event.target.value })} autoComplete="current-password" /><LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'login' ? 'Signing in…' : 'Sign In with Password'}</LiteButton></form> : null}
          </GlassCard>
          <GlassCard className="lite-identity-card">
            <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><KeyRound className="h-5 w-5" /></div><LiteHelp helpKey="identity.recovery" /></div>
            <h2>Recover your access</h2><p>Use one unused recovery code for your own identity. Previous sessions for that identity are revoked.</p>
            {!showRecovery ? <LiteButton variant="secondary" onClick={() => setShowRecovery(true)}>Use Recovery Code</LiteButton> : <form className="lite-identity-form" onSubmit={recoverAccess}><IdentityField label="Sign-in name" value={recover.username} onChange={(event) => setRecover({ ...recover, username: event.target.value })} autoComplete="username" /><IdentityField label="Recovery code" type="password" value={recover.recovery_code} onChange={(event) => setRecover({ ...recover, recovery_code: event.target.value })} autoComplete="off" /><IdentityField label="New password" type="password" value={recover.new_password} onChange={(event) => setRecover({ ...recover, new_password: event.target.value })} autoComplete="new-password" /><LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'recover' ? 'Recovering…' : 'Recover Access'}</LiteButton></form>}
          </GlassCard>
        </div>
      ) : null}

      {data?.authenticated && !identityReadOnly ? (
        <>
          <section className="lite-identity-posture-strip" aria-label="Access posture">
            <div><span>Signed in as</span><strong>{personLabel}</strong><small>{currentRoleLabel}</small></div>
            <div><span>Passkeys</span><strong>{activePasskeys.length ? `${activePasskeys.length} ready` : 'Needs attention'}</strong><small>{passkeyEligible ? 'Browser ready' : 'HTTPS/passkey support needed'}</small></div>
            <div><span>Sessions</span><strong>{activeSessions.length} active</strong><small>{activeSessions.some((session) => session.current) ? 'This session verified' : 'Session state available'}</small></div>
            <div><span>Recovery</span><strong>{data?.recovery?.configured ? 'Ready' : 'Needs attention'}</strong><small>{data?.recovery?.configured ? `${data.recovery.remaining} unused` : 'Create a recovery set'}</small></div>
          </section>

          <section className="lite-identity-key-areas" aria-labelledby="identity-key-areas"><div className="lite-identity-key-areas-head"><span>Access overview</span><div className="lite-governance-title-row"><h2 id="identity-key-areas">What to review</h2><LiteHelp helpKey="identity.overview" /></div></div>{accessOverview.keyAreas.map((item) => <LiteActionRow key={item.key} label={item.label} value={item.value} summary={item.summary} attention={item.attention} action={{ label: 'Manage', onClick: () => setManageOpen(true) }} />)}</section>

          {data?.enterprise?.enabled ? <LiteIdentityEnterprise enterprise={data.enterprise} currentPerson={currentPerson} onIdentityRefresh={refresh} onModeChanged={refresh} /> : (
            <GlassCard className="lite-identity-card mt-5">
              <div className="lite-identity-card-head"><LiteHelpHeading title="Personal Mode" helpKey="identity.mode" as="h2" /><StatusBadge status="healthy">Simple local access</StatusBadge></div>
              <p>The local Owner is the only human authority. Enterprise roles, separate people, approval requests and temporary access remain off.</p>
              <LiteButton variant="secondary" onClick={() => setShowEnterpriseOptIn((value) => !value)}> {showEnterpriseOptIn ? 'Hide Enterprise option' : 'Review Enterprise Mode'} </LiteButton>
              {showEnterpriseOptIn ? <div className="lite-identity-advanced mt-4"><StateSurface tone="neutral" title="What changes" description="Enterprise Mode keeps the local Owner, enables separate people and roles, and signs out active sessions so the server can apply the new authorization model." /><LiteButton className="mt-3" onClick={() => requestConfirmation({ title: 'Enable Enterprise Mode?', description: 'Pocket Lab will require recent Owner passkey confirmation. Active sessions are signed out after the mode change so role authority can be re-resolved safely.', confirmLabel: 'Enable Enterprise Mode', onConfirm: enableEnterpriseMode })} disabled={Boolean(busy)}>{busy === 'enterprise-enable' ? 'Enabling…' : 'Enable Enterprise Mode'}</LiteButton></div> : null}
            </GlassCard>
          )}

          <LiteSheet open={manageOpen} onClose={() => setManageOpen(false)} title="Manage access" eyebrow="Identity & Access" description="Manage your own passkeys, sessions, recovery and optional password. People and role governance stay in the main Enterprise Identity story." className="lite-identity-manage-sheet">
            <ActionNotice notice={notice} actionStage={actionStage} />
            <div className="lite-identity-manage-stack">
              <section aria-labelledby="identity-manage-passkeys"><div className="lite-identity-card-head"><LiteHelpHeading title="Passkeys" helpKey="identity.passkeys" as="h2" /><StatusBadge status={activePasskeys.length ? 'healthy' : 'review'}>{activePasskeys.length ? `${activePasskeys.length} active` : 'Needs attention'}</StatusBadge></div><p>Each passkey belongs only to your identity. Removing one may require recent passkey confirmation.</p><LiteButton onClick={addPasskey} disabled={Boolean(busy) || !passkeyEligible}>{busy === 'add-passkey' ? 'Adding…' : 'Add Passkey'}</LiteButton><div className="lite-identity-session-list">{(data?.passkeys || []).length ? data.passkeys.map((passkey) => <div key={passkey.credential_id} className="lite-identity-session-row"><div><strong>{passkey.friendly_name || 'Passkey'}</strong><span>{passkey.active ? `Created ${passkey.created_at ? formatLiteTime(passkey.created_at) : 'earlier'} · Last used ${passkey.last_used_at ? formatLiteTime(passkey.last_used_at) : 'not yet'}` : 'Revoked'}</span></div>{passkey.active ? <div className="lite-identity-inline-actions"><LiteButton variant="secondary" onClick={() => renamePasskey(passkey)} disabled={Boolean(busy)}>Rename</LiteButton><LiteButton variant="secondary" onClick={() => requestConfirmation({ title: 'Remove this passkey?', description: 'Pocket Lab may ask for another recent passkey confirmation before the credential is revoked.', confirmLabel: 'Remove Passkey', onConfirm: () => revokePasskey(passkey) })} disabled={Boolean(busy)}>Remove</LiteButton></div> : <StatusBadge status="neutral">Revoked</StatusBadge>}</div>) : <StateSurface tone="neutral" title="No passkeys yet" description="Add a passkey for passkey-first sign-in and protected confirmations." />}</div></section>
              <section aria-labelledby="identity-manage-sessions"><div className="lite-identity-card-head"><LiteHelpHeading title="Sessions" helpKey="identity.sessions" as="h2" /><StatusBadge status="healthy">{activeSessions.length} active</StatusBadge></div><p>Sessions belong to your identity only. Raw cookies and session tokens are never shown.</p><div className="lite-identity-session-list">{activeSessions.map((session) => <div key={session.session_id} className="lite-identity-session-row"><div><strong>{session.current ? 'This device' : 'Other signed-in session'}</strong><span>{session.auth_method || 'server session'} · expires {formatLiteTime(session.absolute_expires_at)}</span></div>{!session.current ? <LiteButton variant="secondary" onClick={() => requestConfirmation({ title: 'Sign out this session?', description: 'Only the selected session for your identity is revoked.', confirmLabel: 'Sign Out Session', onConfirm: () => run(`revoke-${session.session_id}`, () => liteApi.revokeIdentitySession(session.session_id), 'The selected session was signed out.') })} disabled={Boolean(busy)}>Sign Out</LiteButton> : <StatusBadge status="healthy">Current</StatusBadge>}</div>)}</div>{activeSessions.length > 1 ? <LiteButton variant="secondary" onClick={() => requestConfirmation({ title: 'Sign out other sessions?', description: 'Your current session stays active. Other sessions for your identity are revoked.', confirmLabel: 'Sign Out Others', onConfirm: () => run('revoke-others', () => liteApi.revokeOtherIdentitySessions(), 'Other sessions were signed out.') })} disabled={Boolean(busy)}>Sign Out Other Sessions</LiteButton> : null}</section>
              <section aria-labelledby="identity-manage-recovery"><div className="lite-identity-card-head"><LiteHelpHeading title="Recovery" helpKey="identity.recovery" as="h2" /><StatusBadge status={data?.recovery?.configured ? 'healthy' : 'review'}>{data?.recovery?.configured ? `${data.recovery.remaining} unused` : 'Not created'}</StatusBadge></div><p>Generating a new one-time recovery set invalidates the older set for your identity.</p><LiteButton variant="secondary" onClick={() => requestConfirmation({ title: 'Generate new recovery codes?', description: 'The current recovery codes stop working. New codes are shown once and are not saved by the frontend.', confirmLabel: 'Generate New Codes', onConfirm: generateRecoveryCodes })} disabled={Boolean(busy)}>{busy === 'recovery' ? 'Generating…' : 'Generate New Codes'}</LiteButton>{recoveryCodes.length ? <div className="lite-identity-recovery-codes"><div className="lite-identity-safe-note"><strong>Save these now</strong><span>They are shown only in this result.</span></div><code>{recoveryCodes.join('\n')}</code><LiteButton variant="secondary" onClick={() => copyTextToClipboard(recoveryCodes.join('\n'))}><Copy className="h-4 w-4" /> Copy Codes</LiteButton></div> : null}</section>
              {(currentPerson?.password_configured || data?.owner?.password_configured) ? <section aria-labelledby="identity-manage-password"><h2 id="identity-manage-password">Password</h2><p>Password access remains available for this identity. Changing it signs out your other sessions.</p><form className="lite-identity-form" onSubmit={changePassword}><IdentityField label="Current password" type="password" value={passwords.current_password} onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })} autoComplete="current-password" /><IdentityField label="New password" type="password" value={passwords.new_password} onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })} autoComplete="new-password" /><LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'password' ? 'Changing…' : 'Change Password'}</LiteButton></form></section> : null}
              <section aria-labelledby="identity-manage-activity"><h2 id="identity-manage-activity">Your recent activity</h2><p>Bounded, sanitized Identity evidence for this person. Claims, passkeys, sessions and recovery secrets are never exposed.</p><div className="lite-identity-activity-list">{(data?.recent_activity || []).length ? data.recent_activity.map((item, index) => { const reason = getLiteReasonPresentation(item.reason_code, item.summary || 'Identity activity'); return <div key={`${item.correlation_id || item.occurred_at}-${index}`} className="lite-identity-session-row"><div><strong>{item.summary}</strong><span>{reason.title} · {formatLiteTime(item.occurred_at)}</span></div><details className="lite-identity-event-details"><summary>Details</summary><code>{item.reason_code || 'none'}</code></details></div>; }) : <StateSurface tone="neutral" title="No identity activity yet" description="Sanitized sign-in, passkey, session, recovery and role events will appear here." />}</div></section>
              <section className="lite-identity-manage-signout" aria-label="Sign out"><LiteButton variant="secondary" onClick={signOut} disabled={Boolean(busy)}>{busy === 'logout' ? 'Signing out…' : 'Sign Out'}</LiteButton></section>
            </div>
          </LiteSheet>
        </>
      ) : null}

      <ActionNotice notice={notice} actionStage={actionStage} />

      <LiteSheet open={Boolean(renameTarget)} onClose={() => setRenameTarget(null)} title="Rename passkey" eyebrow="Passkey" description="Choose a friendly name. The credential identifier stays hidden from normal UI." className="lite-identity-sheet"><form className="lite-identity-form" onSubmit={confirmRenamePasskey}><IdentityField label="Passkey name" value={renameName} onChange={(event) => setRenameName(event.target.value)} autoFocus maxLength="80" /><div className="lite-identity-sheet-actions"><LiteButton type="button" variant="secondary" onClick={() => setRenameTarget(null)}>Cancel</LiteButton><LiteButton type="submit" disabled={!renameName.trim()}>Save Name</LiteButton></div></form></LiteSheet>

      <LiteSheet open={Boolean(confirmation)} onClose={() => setConfirmation(null)} title={confirmation?.title || 'Confirm change'} eyebrow="Confirm" description={confirmation?.description || ''} className="lite-identity-sheet"><div className="lite-identity-confirmation"><StateSurface tone="neutral" title="Pocket Lab verifies this on the server" description="The interface will not claim success until server-owned Identity state confirms the result." /><div className="lite-identity-sheet-actions"><LiteButton variant="secondary" onClick={() => setConfirmation(null)}>Cancel</LiteButton><LiteButton onClick={confirmRequestedAction}>{confirmation?.confirmLabel || 'Confirm'}</LiteButton></div></div></LiteSheet>
    </>
  );
}
