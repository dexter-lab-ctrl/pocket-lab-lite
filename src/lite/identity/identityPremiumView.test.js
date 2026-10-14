import { describe, expect, it } from 'vitest';
import { identityPremiumProjection, identityJourneyStages, identityActivityView, identityDecisionLabel, IDENTITY_MANAGE_SECTIONS } from './identityPremiumView.js';

describe('Premium Identity selectors — server authority and safe projection', () => {
  it('never interprets browser passkey support as a session authentication method', () => {
    const projection = identityPremiumProjection({ authenticated: true, passkeys: [{ active: true }], sessions: [{ active: true, current: true }] });
    expect(projection.authentication).toBe('Not reported');
  });
  it('retains unknown counts instead of manufacturing zeroes', () => {
    const projection = identityPremiumProjection({ authenticated: true, recovery: {} });
    expect(projection.passkeys).toBeNull();
    expect(projection.sessions).toBeNull();
    expect(projection.remaining).toBeNull();
    expect(projection.recoveryConfigured).toBeNull();
  });
  it('counts active passkeys and sessions and recognizes the current session only when reported', () => {
    const projection = identityPremiumProjection({ authenticated: true,
      sessions: [{ active: true, current: true, auth_method: 'passkey' }, { active: false, current: false }],
      passkeys: [{ active: true }, { active: false }], recovery: { configured: true, remaining: 4 } });
    expect(projection).toMatchObject({ authentication: 'Passkey', passkeys: 1, sessions: 1, currentSessionKnown: true, remaining: 4 });
  });
  it('keeps stale authority non-executable in all four journey stages', () => {
    const stages = identityJourneyStages(identityPremiumProjection({ authenticated: true }, { fresh: false }));
    expect(stages.map((s) => s.state)).toEqual(['saved', 'saved', 'saved', 'saved']);
  });
  it('projects only explicit activity types and outcomes without guessing from event prose', () => {
    const rows = identityActivityView([
      { event_type: 'session.signed_in', summary: 'Logged in', correlation_id: 'one', outcome: 'completed', occurred_at: '2026-10-14T00:00:00Z' },
      { event_type: 'unknown.source', summary: 'passkey added by admin', payload: { secret: 'do-not-expose' }, outcome: 'amazing' },
    ]);
    expect(rows[0].family).toBe('sign-ins');
    expect(rows[1].family).toBe('other');
    expect(rows[1].outcome).toBe('Not reported');
    expect(JSON.stringify(rows)).not.toContain('do-not-expose');
    expect(rows[0].key).not.toBe(rows[1].key);
  });
  it('does not create permissions from unsupported decision codes', () => {
    expect(identityDecisionLabel('allow')).toBe('Direct');
    expect(identityDecisionLabel('approval')).toBe('Requires review');
    expect(identityDecisionLabel('step_up')).toBe('Passkey confirmation');
    expect(identityDecisionLabel('anything')).toBe('Not reported');
  });
  it('keeps Personal Manage free from Enterprise sections', () => {
    expect(IDENTITY_MANAGE_SECTIONS.map(([id]) => id)).not.toContain('people');
  });
});
