import { LiteProtectedConfirmation } from './components/LiteSafeForms.jsx';
import './identityRules.css';
import './identityRulesGovernance.css';
import React, { useEffect, useMemo, useState } from 'react';
import { Fingerprint, KeyRound, LogIn, ShieldUser, UserCheck, BookOpenText } from 'lucide-react';
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
import { LiteSheet, LiteDetailsPanel } from './LiteOverlay.jsx';
import IdentityAccessJourney from './identity/IdentityAccessJourney.jsx';
import IdentityManageContent from './identity/IdentityManageContent.jsx';
import IdentityDetailsContent from './identity/IdentityDetailsContent.jsx';
import IdentityActivityTimeline from './identity/IdentityActivityTimeline.jsx';
import { identityPremiumProjection } from './identity/identityPremiumView.js';
import './identity/identityPremium.css';
import LiteEvidenceGuide from './components/LiteEvidenceGuide.jsx';
import { LiteField } from './components/LiteSafeForms.jsx';
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
import { LiteConsequenceSummary, LiteFreshness, LiteHistoryTimeline } from './LiteUx.jsx';

function IdentityField({ label, hint = '', ...props }) {
  return <LiteField label={label} hint={hint} className="lite-identity-form-field"><input className="pocket-input" {...props} /></LiteField>;
}

function ActionNotice({ notice, actionStage }) {
  if (!notice && !actionStage) return null;
  return (
    <div role="status" aria-live="polite" className="mt-4">
      <StateSurface
        tone={notice?.error ? 'degraded' : actionStage === 'completed' ? 'healthy' : 'neutral'}
        title={notice?.title || identityActionStageLabel(actionStage) || 'Working'}
        description={notice?.message || 'Pocket Lab is verifying this access change.'}
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
  const [manageSection, setManageSection] = useState('overview');
  const [selectedDetails, setSelectedDetails] = useState(null);
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
  const premiumView = useMemo(() => identityPremiumProjection(data, { fresh: !identityReadOnly && !isExpired && !backendDegraded }), [data, identityReadOnly, isExpired, backendDegraded]);
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
    setNotice({ title: 'Preparing', message: 'Pocket Lab is preparing this protected access change.' });
    try {
      setActionStage('pending');
      setNotice({ title: 'Waiting for Pocket Lab', message: 'Nothing is shown as completed until Pocket Lab accepts the request.' });
      const result = await callback();
      if (signedOutAfter) clearLiteIdentityCsrf();
      setActionStage('verifying');
      setNotice({ title: 'Pocket Lab accepted', message: 'Pocket Lab accepted the request. Reading current access information now.' });
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

  function requestConfirmation({ title, description, confirmLabel, onConfirm, will = [], willNot = [], reversible = '', availability = '' }) {
    setSelectedDetails(null);
    setConfirmation({ title, description, confirmLabel, onConfirm, will, willNot, reversible, availability });
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
    setSelectedDetails(null);
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

  async function copyRecoveryCodes() {
    if (!(await copyTextToClipboard(recoveryCodes.join('\n')))) return;
    pushToast({ id: 'identity:recovery-codes-copied', kind: 'success', title: 'Recovery codes copied', message: 'Keep them in a safe place outside Pocket Lab.' });
  }

  async function signOut() {
    await run('logout', () => liteApi.logoutIdentity(), 'Signed out.', { signedOutAfter: true });
    setRecoveryCodes([]);
  }

  async function enableEnterpriseMode() {
    const result = await run('enterprise-enable', () => withOwnerStepUp('enterprise.mode.change', () => liteEnterpriseApi.setMode(true)), 'Enterprise Mode enabled. Sign in again so server-managed role authority can take effect.', { signedOutAfter: true });
    if (result) setShowEnterpriseOptIn(false);
  }

  function openManage(section = 'overview') { setManageSection(section); setManageOpen(true); }
  function openDetails(kind, item = {}) { setSelectedDetails({ kind, item }); }
  function requestRemovePasskey(passkey) {
    requestConfirmation({ title: 'Remove this passkey?', description: 'Pocket Lab may request another recent passkey confirmation before revoking the credential.', confirmLabel: 'Remove Passkey', onConfirm: () => revokePasskey(passkey), will: ['Revoke the selected passkey after server authorization.'], willNot: ['Reveal the credential identifier or affect a different passkey.'] });
  }
  function requestSignOutSession(session) {
    requestConfirmation({ title: 'Sign out this session?', description: 'Only the selected session for your identity is revoked.', confirmLabel: 'Sign Out Session', onConfirm: () => run('revoke-session', () => liteApi.revokeIdentitySession(session.session_id), 'The selected session was signed out.') });
  }
  function requestSignOutOthers() {
    requestConfirmation({ title: 'Sign out other sessions?', description: 'Your current session stays active. Other sessions for your identity are revoked.', confirmLabel: 'Sign Out Others', onConfirm: () => run('revoke-others', () => liteApi.revokeOtherIdentitySessions(), 'Other sessions were signed out.') });
  }
  function requestRecoveryRegeneration() {
    requestConfirmation({ title: 'Generate new recovery codes?', description: 'The existing code set stops working. New codes are shown once in the authorized result, not in saved Details.', confirmLabel: 'Generate New Codes', onConfirm: () => { setManageSection('recovery'); return generateRecoveryCodes(); }, will: ['Invalidate older recovery codes.'], willNot: ['Save the new codes in browser snapshots.'] });
  }
  const workspaceStory = accessOverview.workspaceStory;
  const currentRoleLabel = enterpriseRole || (currentPerson?.is_local_owner ? 'Owner' : 'Personal Mode');

  return (
    <>
      <PageHeader
        eyebrow="Identity"
        title="Identity & Access"
        description="See who can access your Pocket Lab, how you sign in, and how to recover access."
        actions={<div className="lite-governance-inline-actions"><LiteHelp helpKey="identity.overview" /><LiteRefreshButton scope="identity" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} /></div>}
      />

      <LiteOperationalStory
        className="lite-identity-operational-story"
        story={workspaceStory}
        primaryAction={workspaceStory.nextAction?.id === 'create_owner' ? { label: 'Create Owner', onClick: () => document.getElementById('identity-owner-setup')?.scrollIntoView({ block: 'start' }) } : workspaceStory.nextAction?.id === 'sign_in_passkey' ? { label: 'Sign in with Passkey', onClick: signInWithPasskey, disabled: Boolean(busy) || !passkeyEligible } : workspaceStory.nextAction?.id === 'add_passkey' ? { label: 'Add Passkey', onClick: addPasskey, disabled: Boolean(busy) || !passkeyEligible } : workspaceStory.nextAction?.id === 'review_recovery' ? { label: 'Review Recovery', onClick: () => openManage('recovery') } : workspaceStory.nextAction?.id === 'refresh' ? { label: 'Refresh access', onClick: refresh } : null}
        manageAction={data?.authenticated ? { label: 'Manage Access', onClick: () => openManage('overview') } : null}
      />
      <LiteFreshness
        saved={savedStateOnly}
        stale={isExpired}
        refreshing={refreshing}
        lastUpdatedLabel={lastUpdatedLabel}
        backendReachable={backendReachable}
      />

      {data?.authenticated ? <div className="lite-id-explain-entry"><button type="button" onClick={() => openDetails('explain')}><BookOpenText size={17} aria-hidden="true" /> Explain This <span>Understand your access and its limits</span></button></div> : null}
      {loading ? <LoadingCard label="Checking access and sign-in protection…" /> : null}
      {error && !data ? <StateSurface tone="degraded" title="Access information is temporarily unavailable" description="Pocket Lab could not confirm the latest access information. Saved access information remains visible when available." className="mb-5" /> : null}
      {backendDegraded && backendReachable ? <StateSurface tone="degraded" title="Identity needs attention" description="Pocket Lab is reachable, but it could not confirm all current access information. Protected changes stay unavailable until current access is confirmed." className="mb-5" /> : null}

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

      {data?.authenticated ? (
        <>
          <section className="lite-id-overview" aria-label="Access profile">
            <div className="lite-id-profile"><ShieldUser size={27} aria-hidden="true" /><div><span>Signed in as</span><h2>{premiumView.name}</h2><p>{premiumView.role} · {premiumView.mode}</p><small>Sign-in method: {premiumView.authentication}</small></div></div>
            <div className="lite-id-protections" aria-label="Access posture">
              <button type="button" onClick={() => openManage('passkeys')}><strong>Passkeys</strong><span>{premiumView.passkeys == null ? 'Unavailable' : premiumView.passkeys + ' active'}</span></button>
              <button type="button" onClick={() => openManage('sessions')}><strong>Sessions</strong><span>{premiumView.sessions == null ? 'Unavailable' : premiumView.sessions + ' active'}</span><small>{premiumView.currentSessionKnown ? 'Current session known' : 'Current session not identified'}</small></button>
              <button type="button" onClick={() => openManage('recovery')}><strong>Recovery</strong><span>{premiumView.recoveryConfigured == null ? 'Unavailable' : premiumView.recoveryConfigured ? 'Configured' : 'Not configured'}</span><small>{premiumView.remaining == null ? 'Code count unavailable' : premiumView.remaining + ' unused codes'}</small></button>
            </div>
          </section>
          <IdentityAccessJourney view={premiumView} onSelect={(stage) => {
            if (stage === 'authentication') openManage('passkeys');
            else if (stage === 'recovery') openDetails('recovery');
            else if (stage === 'authorization') openDetails('mode');
            else openDetails('identity');
          }} />
          <section className="lite-id-preview"><div><h2>Recent Activity</h2><button type="button" onClick={() => openManage('activity')}>View all activity</button></div><IdentityActivityTimeline items={data?.recent_activity} limit={3} onDetails={(event) => openDetails('activity', event)} /></section>
          <div className="lite-id-overview-action"><LiteButton variant="secondary" onClick={() => openManage('overview')}>Manage Access</LiteButton></div>
          <LiteSheet open={manageOpen} onClose={() => setManageOpen(false)} title="Manage access" eyebrow="Identity & Access" description="Review and manage your reported access." className="lite-identity-manage-sheet">
            <IdentityManageContent
              data={data} view={premiumView} section={manageSection} setSection={setManageSection} busy={busy} notice={notice}
              passkeyEligible={passkeyEligible} recoveryCodes={recoveryCodes} onOpenDetails={openDetails}
              onAddPasskey={addPasskey} onRename={renamePasskey} onRemovePasskey={requestRemovePasskey}
              onSignOutSession={requestSignOutSession} onSignOutOthers={requestSignOutOthers}
              onRegenerate={requestRecoveryRegeneration} onCopyCodes={copyRecoveryCodes} onSignOut={signOut}
              passwordForm={passwords} onPasswordForm={setPasswords} onChangePassword={changePassword}
              enterpriseEnabled={Boolean(data?.enterprise?.enabled)}
              onReviewEnterprise={() => setShowEnterpriseOptIn((value) => !value)}
              showEnterpriseOptIn={showEnterpriseOptIn}
              onEnableEnterprise={() => requestConfirmation({ title: 'Enable Enterprise Mode?', description: 'Owner passkey confirmation may be required and active sessions will be signed out.', confirmLabel: 'Enable Enterprise Mode', onConfirm: enableEnterpriseMode })}
              enterpriseContent={data?.enterprise?.enabled ? <LiteIdentityEnterprise embedded section={manageSection === 'settings' ? 'mode' : manageSection} enterprise={data.enterprise} currentPerson={currentPerson} onIdentityRefresh={refresh} onModeChanged={refresh} onOpenDetails={openDetails} /> : null}
            />
          </LiteSheet>
          <LiteDetailsPanel open={Boolean(selectedDetails)} onClose={() => setSelectedDetails(null)} title={selectedDetails?.kind === 'explain' ? 'Understand your access' : 'Access Details'} description="Server-reported information and safe next actions.">
            <IdentityDetailsContent selection={selectedDetails} view={premiumView} disabled={Boolean(busy) || !premiumView.fresh}
              onRename={renamePasskey} onRemovePasskey={requestRemovePasskey} onSignOutSession={requestSignOutSession}
              onRegenerate={requestRecoveryRegeneration} onSignOutOtherSessions={requestSignOutOthers}
              onOpenManage={() => setSelectedDetails(null)} />
          </LiteDetailsPanel>
        </>
      ) : null}

      <ActionNotice notice={notice} actionStage={actionStage} />

      <LiteSheet open={Boolean(renameTarget)} onClose={() => setRenameTarget(null)} title="Rename passkey" eyebrow="Passkey" description="Choose a friendly name. The credential identifier stays hidden from normal UI." className="lite-identity-sheet"><form className="lite-identity-form" onSubmit={confirmRenamePasskey}><IdentityField label="Passkey name" value={renameName} onChange={(event) => setRenameName(event.target.value)} autoFocus maxLength="80" /><div className="lite-identity-sheet-actions"><LiteButton type="button" variant="secondary" onClick={() => setRenameTarget(null)}>Cancel</LiteButton><LiteButton type="submit" disabled={!renameName.trim()}>Save Name</LiteButton></div></form></LiteSheet>

      <LiteSheet open={Boolean(confirmation)} onClose={() => setConfirmation(null)} title={confirmation?.title || 'Confirm change'} eyebrow="Confirm" description={confirmation?.description || ''} className="lite-identity-sheet"><div className="lite-identity-confirmation"><LiteProtectedConfirmation value={{ title: confirmation?.title, summary: confirmation?.description, will: confirmation?.will?.length ? confirmation.will : ['Apply only the access change shown here.'], willNot: confirmation?.willNot?.length ? confirmation.willNot : ['Show the change as completed until Pocket Lab confirms it.'], reversible: confirmation?.reversible || 'You can review the resulting access state after the change.', availability: confirmation?.availability || 'Your current access stays available unless this confirmation explicitly says otherwise.' }} /><div className="lite-identity-sheet-actions"><LiteButton variant="secondary" onClick={() => setConfirmation(null)}>Cancel</LiteButton><LiteButton onClick={confirmRequestedAction}>{confirmation?.confirmLabel || 'Confirm'}</LiteButton></div></div></LiteSheet>
    </>
  );
}
