import { describe, expect, it } from 'vitest';
import {
  getApprovalPresentation,
  getLiteReasonPresentation,
  getLiteStatusPresentation,
  buildLiteIdentityAccessOverview,
  buildLiteEnterpriseRulesOverview,
  buildLiteRulesOverview,
  getLiteRulesActionLabel,
  identityActionStageLabel,
  shortRevision,
} from './identityRulesPresentation.js';

describe('Identity and Rules presentation helpers', () => {
  it('translates sensitive reason codes into user-facing guidance', () => {
    expect(getLiteReasonPresentation('passkey_step_up_required')).toMatchObject({
      title: 'Confirm with your passkey',
      tone: 'review',
    });
    expect(getLiteReasonPresentation('approval_self_forbidden')).toMatchObject({
      title: 'Another person must approve',
      tone: 'blocked',
    });
    expect(getLiteReasonPresentation('policy_revision_uncertain').message).toContain('protected changes remain blocked');
  });

  it('normalizes lifecycle statuses without relying on color alone', () => {
    expect(getLiteStatusPresentation('pending')).toEqual({ label: 'Waiting', tone: 'review' });
    expect(getLiteStatusPresentation('expired')).toEqual({ label: 'Expired', tone: 'neutral' });
    expect(getLiteStatusPresentation('degraded')).toEqual({ label: 'Degraded', tone: 'degraded' });
  });

  it('uses server-derived approval capabilities for requester guidance', () => {
    const requester = getApprovalPresentation({
      status: 'pending',
      viewer_relationship: 'requester',
      viewer_actions: { approve: false, reject: false, cancel: true },
      eligible_approver_count: 0,
    });
    expect(requester.actions.approve).toBe(false);
    expect(requester.actions.cancel).toBe(true);
    expect(requester.guidance).toContain('Another Owner or Admin is required');

    const reviewer = getApprovalPresentation({
      status: 'pending',
      viewer_relationship: 'reviewer',
      viewer_actions: { approve: true, reject: true, cancel: false },
      eligible_approver_count: 1,
    });
    expect(reviewer.actions.approve).toBe(true);
    expect(reviewer.guidance).toContain('passkey confirmation');
  });

  it('keeps long revision identifiers secondary and copyable', () => {
    expect(shortRevision('plr-9b2fe6614d2d1cf8074f17900ed71866')).toMatch(/^plr-9b2fe661…/);
    expect(shortRevision('short')).toBe('short');
  });

  it('names truthful async stages', () => {
    expect(identityActionStageLabel('pending')).toBe('Waiting for Pocket Lab…');
    expect(identityActionStageLabel('verifying')).toBe('Verifying…');
    expect(identityActionStageLabel('completed')).toBe('Completed');
  });

  it('keeps an absent Identity projection unknown instead of signed in or signed out', () => {
    const overview = buildLiteIdentityAccessOverview(null);
    expect(overview.workspaceStory).toMatchObject({ state: 'unknown', tone: 'unknown' });
    expect(overview.workspaceStory.headline).toContain('not confirmed');
  });

  it('keeps saved Identity data visibly non-authoritative', () => {
    const overview = buildLiteIdentityAccessOverview({
      authenticated: true,
      passkeys: [{ active: true }],
      sessions: [{ active: true }],
      recovery: { configured: true },
      enterprise: { enabled: false },
    }, { savedStateOnly: true, lastUpdatedLabel: 'Saved earlier' });
    expect(overview.workspaceStory).toMatchObject({ state: 'saved', tone: 'saved' });
    expect(overview.workspaceStory.summary).toContain('cannot currently be confirmed');
    expect(overview.workspaceStory.nextAction).toEqual({ id: 'refresh', label: 'Refresh access' });
  });

  it('prioritizes a passkey sign-in only when the server and browser both support it', () => {
    const eligible = buildLiteIdentityAccessOverview({
      authenticated: false,
      setup_required: false,
      owner: { username: 'owner' },
      sign_in_methods: { passkey: true },
    }, { passkeyEligible: true });
    expect(eligible.workspaceStory.nextAction).toEqual({ id: 'sign_in_passkey', label: 'Sign in with Passkey' });

    const unavailable = buildLiteIdentityAccessOverview({
      authenticated: false,
      setup_required: false,
      owner: { username: 'owner' },
      sign_in_methods: { passkey: true },
    }, { passkeyEligible: false });
    expect(unavailable.workspaceStory.nextAction).toBeNull();
  });

  it('does not claim signed-in access is ready when passkeys or recovery are missing', () => {
    const missingPasskey = buildLiteIdentityAccessOverview({
      authenticated: true,
      passkeys: [],
      sessions: [{ active: true }],
      recovery: { configured: true },
      enterprise: { enabled: false },
    }, { passkeyEligible: true });
    expect(missingPasskey.workspaceStory.nextAction).toEqual({ id: 'add_passkey', label: 'Add Passkey' });
    expect(missingPasskey.workspaceStory.tone).toBe('review');

    const missingRecovery = buildLiteIdentityAccessOverview({
      authenticated: true,
      passkeys: [{ active: true }],
      sessions: [{ active: true }],
      recovery: { configured: false },
      enterprise: { enabled: false },
    }, { passkeyEligible: true });
    expect(missingRecovery.workspaceStory.nextAction).toEqual({ id: 'review_recovery', label: 'Review Recovery' });
  });

  it('keeps Personal Rules unknown until prepared engine and policy truth exist', () => {
    expect(buildLiteRulesOverview(null).workspaceStory).toMatchObject({ state: 'unknown', tone: 'unknown' });
    expect(buildLiteRulesOverview({ status: 'ready' }).workspaceStory.state).toBe('unknown');
  });

  it('keeps saved Personal Rules non-authoritative and refresh-only', () => {
    const overview = buildLiteRulesOverview({
      status: 'ready',
      engine: { healthy: true, loopback_only: true },
      policy_groups: [],
    }, { savedStateOnly: true, lastUpdatedLabel: 'Saved earlier' });
    expect(overview.workspaceStory).toMatchObject({ state: 'saved', tone: 'saved' });
    expect(overview.workspaceStory.nextAction).toEqual({ id: 'refresh', label: 'Refresh Rules' });
    expect(overview.workspaceStory.consequence).toContain('server verification');
  });

  it('maps only verified protected actions to friendly labels', () => {
    expect(getLiteRulesActionLabel('catalog.install')).toBe('Install an app');
    expect(getLiteRulesActionLabel('device.remove')).toBe('Remove a device');
    expect(getLiteRulesActionLabel('unverified.action')).toBe('');
  });

  it('keeps an allowed policy decision separate from protected-action execution', () => {
    const overview = buildLiteRulesOverview({
      status: 'ready',
      engine: { healthy: true, loopback_only: true },
      recent_decisions: [{ allow: true }],
      policy_groups: [],
    });
    expect(overview.recentDecisionSummary).toBe('1 recent protected decision');
    expect(overview.workspaceStory.consequence).toContain('stays blocked');
  });

  it('prioritizes approval review without implying protected-action execution', () => {
    const overview = buildLiteEnterpriseRulesOverview({
      health: { consistency_state: 'ready' },
      approvals: [{ status: 'pending' }],
    });
    expect(overview.workspaceStory.nextAction).toEqual({ id: 'requests', label: 'Review requests' });
    expect(overview.workspaceStory.consequence).toContain('requester must retry');
  });

  it('keeps temporary Enterprise exceptions distinct from permanent Rules changes', () => {
    const overview = buildLiteEnterpriseRulesOverview({
      health: { consistency_state: 'ready' },
      exceptions: [{ status: 'active' }],
    });
    expect(overview.workspaceStory.nextAction).toEqual({ id: 'exceptions', label: 'Review temporary access' });
    expect(overview.workspaceStory.consequence).toContain('not a permanent Rules change');
  });
});
