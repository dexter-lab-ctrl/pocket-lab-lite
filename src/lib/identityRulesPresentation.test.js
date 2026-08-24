import { describe, expect, it } from 'vitest';
import {
  getApprovalPresentation,
  getLiteReasonPresentation,
  getLiteStatusPresentation,
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
});
