// @vitest-environment jsdom
// Azure Horizon Identity source contracts — deliberately not executed in implementation-only session.
import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import IdentityManageContent from './IdentityManageContent.jsx';
import { identityPremiumProjection, identityJourneyStages, identityActivityView } from './identityPremiumView.js';

const empty = () => {};
function mount({ data = {}, fresh = true, section = 'overview', enterpriseEnabled = false } = {}) {
  const view = identityPremiumProjection({ authenticated: true, ...data }, { fresh });
  render(<IdentityManageContent
    data={data} view={view} section={section} setSection={empty} busy="" notice={null}
    passkeyEligible recoveryCodes={[]} onOpenDetails={empty} onAddPasskey={empty}
    onRename={empty} onRemovePasskey={empty} onSignOutSession={empty} onSignOutOthers={empty}
    onRegenerate={empty} onCopyCodes={empty} onSignOut={empty}
    passwordForm={{ current_password: '', new_password: '' }} onPasswordForm={empty} onChangePassword={empty}
    enterpriseEnabled={enterpriseEnabled} onReviewEnterprise={empty} onEnableEnterprise={empty}
    onApproveOwnerOperation={empty} onRejectOwnerOperation={empty}
  />);
}
describe('Azure Horizon account facts and Manage authorization posture', () => {
  it('never invents a passkey, recovery code count, or session', () => {
    const p = identityPremiumProjection({ authenticated: true, owner: { display_name: 'Synthetic Owner' } });
    expect(p.name).toBe('Synthetic Owner');
    expect(p.passkeys).toBeNull();
    expect(p.sessions).toBeNull();
    expect(p.recoveryConfigured).toBeNull();
  });
  it('only counts explicitly active credentials and sessions', () => {
    const p = identityPremiumProjection({ authenticated: true, passkeys: [{ active: true }, { active: false }],
      sessions: [{ active: true, current: true }, { active: false }], recovery: { configured: true, remaining: 2 } });
    expect([p.passkeys, p.sessions, p.remaining]).toEqual([1, 1, 2]);
    expect(p.currentSessionKnown).toBe(true);
  });
  it('marks the conceptual journey saved rather than live for stale data', () => {
    expect(identityJourneyStages(identityPremiumProjection({ authenticated: true }, { fresh: false }))
      .every((stage) => stage.state === 'saved')).toBe(true);
  });
  it('omits sensitive payloads from access activity projections', () => {
    const view = identityActivityView([{ event_type: 'sign_in', summary: 'Signed in', payload: { password: 'synthetic-private' } }]);
    expect(JSON.stringify(view)).not.toContain('synthetic-private');
  });
  it('shows unavailable account facts explicitly rather than zero', () => {
    mount();
    expect(screen.getAllByText('Unavailable', { selector: 'dd' }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'People' })).toBeNull();
  });
  it('prevents stale passkey registration and recovery-code generation', () => {
    mount({ fresh: false, section: 'passkeys', data: { passkeys: [] } });
    expect(screen.getByRole('button', { name: /Add Passkey/i }).disabled).toBe(true);
  });
  it('retains read-only recovery on unavailable authorization', () => {
    mount({ fresh: false, section: 'recovery', data: { recovery: { configured: false } } });
    expect(screen.getByRole('button', { name: /Generate New Codes/i }).disabled).toBe(true);
    expect(screen.queryByText('synthetic-private')).toBeNull();
  });
  it('distinguishes current and other active sessions', () => {
    mount({ section: 'sessions', data: { sessions: [
      { session_id: 'synthetic-a', active: true, current: true, auth_method: 'passkey' },
      { session_id: 'synthetic-b', active: true, current: false, auth_method: 'password' },
    ] } });
    expect(screen.getByRole('button', { name: /Current session/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Other session/i })).toBeTruthy();
  });
  it('shows Enterprise navigation only when server projection enables it', () => {
    mount({ enterpriseEnabled: true });
    expect(screen.getByRole('button', { name: 'People' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Roles & Access' })).toBeTruthy();
  });
});
