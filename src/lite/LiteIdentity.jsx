import './identityRules.css';
import React, { useMemo, useState } from 'react';
import { Copy, Fingerprint, KeyRound, LogIn, RefreshCw, ShieldCheck, UserRound } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
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

function ActionNotice({ notice }) {
  if (!notice) return null;
  return (
    <StateSurface
      tone={notice.error ? 'degraded' : 'healthy'}
      title={notice.error ? 'Something changed' : notice.title || 'Done'}
      description={notice.message}
      className="mt-4"
    />
  );
}

export default function IdentityScreen() {
  const { data, loading, error, refresh, cacheStatus, refreshing } = useLiteResource(liteApi.identity, []);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState(null);
  const [recoveryCodes, setRecoveryCodes] = useState([]);
  const [showRecovery, setShowRecovery] = useState(false);
  const [setup, setSetup] = useState({ username: 'owner', display_name: 'Pocket Lab Owner', password: '', setup_token: '' });
  const [login, setLogin] = useState({ username: 'owner', password: '' });
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' });
  const [recover, setRecover] = useState({ username: 'owner', recovery_code: '', new_password: '' });

  const activeSessions = useMemo(() => (data?.sessions || []).filter((item) => item.active), [data?.sessions]);

  async function run(name, callback, successMessage) {
    setBusy(name);
    setNotice(null);
    try {
      const result = await callback();
      setNotice({ title: 'Done', message: result?.summary || successMessage });
      await refresh();
      return result;
    } catch (err) {
      setNotice({ error: true, message: err?.message || 'Pocket Lab could not complete that identity action.' });
      return null;
    } finally {
      setBusy('');
    }
  }

  async function setupOwner(event) {
    event.preventDefault();
    const result = await run('setup', () => liteApi.setupIdentity(setup), 'Owner created and signed in.');
    if (result) setSetup((value) => ({ ...value, password: '', setup_token: '' }));
  }

  async function signIn(event) {
    event.preventDefault();
    const result = await run('login', () => liteApi.loginIdentity(login), 'Signed in.');
    if (result) setLogin((value) => ({ ...value, password: '' }));
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
    const result = await run('password', () => liteApi.changeIdentityPassword(passwords), 'Password changed.');
    if (result) setPasswords({ current_password: '', new_password: '' });
  }

  async function generateRecoveryCodes() {
    const result = await run('recovery', () => liteApi.regenerateIdentityRecovery(), 'Recovery codes generated.');
    if (result?.codes) setRecoveryCodes(result.codes);
  }

  async function signOut() {
    await run('logout', () => liteApi.logoutIdentity(), 'Signed out.');
    setRecoveryCodes([]);
  }

  const status = data?.setup_required ? 'review' : data?.authenticated ? 'healthy' : 'degraded';

  return (
    <>
      <PageHeader
        eyebrow="Identity"
        title="Identity & Access"
        description="Sign in as the local owner, manage password and recovery, and review active sessions without exposing credentials in the browser."
        actions={<LiteRefreshButton scope="identity" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <section className="lite-identity-hero">
        <div className="lite-identity-hero-copy">
          <div className="lite-home-pill"><span className="lite-ready-dot" />{data?.authenticated ? 'Owner signed in' : data?.setup_required ? 'Owner setup needed' : 'Sign in required'}</div>
          <h2>{data?.authenticated ? 'Your local owner session is active.' : data?.setup_required ? 'Create the local Pocket Lab owner.' : 'Sign in before making protected changes.'}</h2>
          <p>{data?.summary || 'Pocket Lab keeps human sign-in separate from device and service identities.'}</p>
        </div>
        <div className="lite-identity-status-card">
          <div className="lite-identity-icon"><Fingerprint className="h-7 w-7" /></div>
          <span>Owner access</span>
          <strong>{data?.authenticated ? 'Signed in' : data?.setup_required ? 'Setup' : 'Signed out'}</strong>
          <StatusBadge status={status}>{data?.authenticated ? 'Protected' : 'Action needed'}</StatusBadge>
        </div>
      </section>

      {loading ? <LoadingCard label="Checking identity..." /> : null}
      {error ? <StateSurface tone="degraded" title="Identity needs a moment" description={error} className="mb-5" /> : null}

      {!loading && data?.setup_required ? (
        <GlassCard className="lite-identity-card lite-identity-auth-card">
          <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><UserRound className="h-5 w-5" /></div><span className="lite-identity-soft-badge">One-time setup</span></div>
          <h2>Create owner</h2>
          <p>Use the one-time setup token configured on the server. The token and password are never saved in browser storage.</p>
          <form className="lite-identity-form" onSubmit={setupOwner}>
            <IdentityField label="Owner name" value={setup.username} onChange={(e) => setSetup({ ...setup, username: e.target.value })} autoComplete="username" />
            <IdentityField label="Display name" value={setup.display_name} onChange={(e) => setSetup({ ...setup, display_name: e.target.value })} autoComplete="name" />
            <IdentityField label="Password" type="password" value={setup.password} onChange={(e) => setSetup({ ...setup, password: e.target.value })} autoComplete="new-password" />
            <IdentityField label="One-time setup token" type="password" value={setup.setup_token} onChange={(e) => setSetup({ ...setup, setup_token: e.target.value })} autoComplete="off" />
            <LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'setup' ? 'Creating...' : 'Create Owner'}</LiteButton>
          </form>
        </GlassCard>
      ) : null}

      {!loading && data?.owner && !data?.authenticated ? (
        <div className="lite-identity-grid">
          <GlassCard className="lite-identity-card lite-identity-auth-card">
            <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><LogIn className="h-5 w-5" /></div><StatusBadge status="review">Signed out</StatusBadge></div>
            <h2>Sign in</h2>
            <p>Protected changes require the local owner session.</p>
            <form className="lite-identity-form" onSubmit={signIn}>
              <IdentityField label="Owner name" value={login.username} onChange={(e) => setLogin({ ...login, username: e.target.value })} autoComplete="username" />
              <IdentityField label="Password" type="password" value={login.password} onChange={(e) => setLogin({ ...login, password: e.target.value })} autoComplete="current-password" />
              <LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'login' ? 'Signing in...' : 'Sign In'}</LiteButton>
            </form>
          </GlassCard>
          <GlassCard className="lite-identity-card">
            <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><KeyRound className="h-5 w-5" /></div><span className="lite-identity-soft-badge">Recovery</span></div>
            <h2>Can’t sign in?</h2>
            <p>Use one unused recovery code to set a new password. Previous sessions are revoked.</p>
            {!showRecovery ? <LiteButton variant="secondary" onClick={() => setShowRecovery(true)}>Use Recovery Code</LiteButton> : (
              <form className="lite-identity-form" onSubmit={recoverAccess}>
                <IdentityField label="Owner name" value={recover.username} onChange={(e) => setRecover({ ...recover, username: e.target.value })} autoComplete="username" />
                <IdentityField label="Recovery code" type="password" value={recover.recovery_code} onChange={(e) => setRecover({ ...recover, recovery_code: e.target.value })} autoComplete="off" />
                <IdentityField label="New password" type="password" value={recover.new_password} onChange={(e) => setRecover({ ...recover, new_password: e.target.value })} autoComplete="new-password" />
                <LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'recover' ? 'Recovering...' : 'Recover Access'}</LiteButton>
              </form>
            )}
          </GlassCard>
        </div>
      ) : null}

      {data?.authenticated ? (
        <>
          <div className="lite-identity-grid">
            <GlassCard className="lite-identity-card">
              <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><ShieldCheck className="h-5 w-5" /></div><StatusBadge status="healthy">Owner</StatusBadge></div>
              <h2>{data?.owner?.display_name || 'Pocket Lab Owner'}</h2>
              <p>@{data?.owner?.username || 'owner'} · Password protection: {data?.owner?.password_algorithm || 'strong local hash'}</p>
              <div className="lite-identity-checklist">
                <div><span className="lite-check-dot" />Server-side session</div>
                <div><span className="lite-check-dot" />HttpOnly sign-in cookie</div>
                <div><span className="lite-check-dot" />CSRF-protected changes</div>
              </div>
              <div className="mt-5"><LiteButton variant="secondary" onClick={signOut} disabled={Boolean(busy)}>{busy === 'logout' ? 'Signing out...' : 'Sign Out'}</LiteButton></div>
            </GlassCard>

            <GlassCard className="lite-identity-card lite-identity-action-card">
              <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><KeyRound className="h-5 w-5" /></div><span className="lite-identity-soft-badge">Credential</span></div>
              <h2>Change password</h2>
              <p>Changing the password signs out other owner sessions and rotates this session.</p>
              <form className="lite-identity-form" onSubmit={changePassword}>
                <IdentityField label="Current password" type="password" value={passwords.current_password} onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })} autoComplete="current-password" />
                <IdentityField label="New password" type="password" value={passwords.new_password} onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })} autoComplete="new-password" />
                <LiteButton type="submit" disabled={Boolean(busy)}>{busy === 'password' ? 'Changing...' : 'Change Password'}</LiteButton>
              </form>
            </GlassCard>
          </div>

          <div className="lite-identity-grid mt-5">
            <GlassCard className="lite-identity-card">
              <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><RefreshCw className="h-5 w-5" /></div><StatusBadge status={data?.recovery?.configured ? 'healthy' : 'review'}>{data?.recovery?.configured ? `${data.recovery.remaining} unused` : 'Not created'}</StatusBadge></div>
              <h2>Recovery codes</h2>
              <p>Generate a fresh one-time set. Generating again invalidates the older set.</p>
              <LiteButton variant="secondary" onClick={generateRecoveryCodes} disabled={Boolean(busy)}>{busy === 'recovery' ? 'Generating...' : 'Generate New Codes'}</LiteButton>
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
              <div className="lite-identity-session-list">
                {activeSessions.length ? activeSessions.map((session) => (
                  <div key={session.session_id} className="lite-identity-session-row">
                    <div><strong>{session.current ? 'This device' : 'Owner session'}</strong><span>{session.auth_method} · {formatLiteTime(session.created_at)}</span></div>
                    {!session.current ? <LiteButton variant="secondary" onClick={() => run(`revoke-${session.session_id}`, () => liteApi.revokeIdentitySession(session.session_id), 'Session signed out.')} disabled={Boolean(busy)}>Revoke</LiteButton> : <StatusBadge status="healthy">Current</StatusBadge>}
                  </div>
                )) : <p>No other active sessions.</p>}
              </div>
              {activeSessions.length > 1 ? <LiteButton variant="secondary" onClick={() => run('revoke-others', () => liteApi.revokeOtherIdentitySessions(), 'Other sessions signed out.')} disabled={Boolean(busy)}>Sign Out Other Sessions</LiteButton> : null}
            </GlassCard>
          </div>

          <GlassCard className="lite-identity-card mt-5">
            <div className="lite-identity-card-head"><div className="lite-identity-mini-icon"><ShieldCheck className="h-5 w-5" /></div><span className="lite-identity-soft-badge">Identity classes</span></div>
            <h2>Who Pocket Lab recognizes</h2>
            <div className="lite-identity-class-grid">
              {Object.values(data?.identity_classes || {}).map((item) => <div key={item.label}><strong>{item.label}</strong><span>{item.managed_by}</span><small>{item.summary || (item.configured ? 'Configured' : 'Not configured')}</small></div>)}
            </div>
            <p className="mt-4">Passkeys and external sign-in remain optional and are not enabled until their deployment prerequisites are validated.</p>
          </GlassCard>
        </>
      ) : null}

      <ActionNotice notice={notice} />
    </>
  );
}
