import { describe, expect, it } from 'vitest';
import { accessCenterReadiness, accessCenterProtectionRows, accessCenterLatestActivity, accessManageGroups } from './accessCenterPresentation.js';
import { identityPremiumProjection } from './identityPremiumView.js';

const ready = identityPremiumProjection({ authenticated: true,
  owner: { human_id: 'fixture-owner', display_name: 'Fixture Owner' }, enterprise: { enabled: false },
  passkeys: [{ active: true }], sessions: [{ active: true, current: true, auth_method: 'passkey' }],
  recovery: { configured: true, remaining: 4 } });

describe('Azure Horizon Access presentation — authored, not executed', () => {
  it('requires confirmed recovery, passkeys, sessions and role before reporting ready', () => {
    expect(accessCenterReadiness(ready, {}).state).toBe('ready');
    expect(accessCenterReadiness({ ...ready, passkeys: null }, {}).state).toBe('unavailable');
    expect(accessCenterReadiness({ ...ready, sessions: null }, {}).state).toBe('unavailable');
    expect(accessCenterReadiness({ ...ready, recoveryConfigured: null }, {}).state).toBe('unavailable');
    expect(accessCenterReadiness({ ...ready, role: 'Unavailable' }, {}).state).toBe('unavailable');
  });
  it('never treats saved or signed-out projection as verified protection', () => {
    expect(accessCenterReadiness({ ...ready, fresh: false }, {}).state).toBe('saved');
    expect(accessCenterReadiness({ ...ready, signedIn: false }, {}).state).toBe('signed-out');
  });
  it('surfaces missing passkeys, missing recovery and password changes as attention', () => {
    expect(accessCenterReadiness({ ...ready, passkeys: 0 }, {}).state).toBe('attention');
    expect(accessCenterReadiness({ ...ready, recoveryConfigured: false }, {}).title).toBe('Recovery is not configured');
    expect(accessCenterReadiness(ready, { person: { password_change_required: true } }).title).toBe('Password change required');
  });
  it('preserves unknown protection counts instead of displaying zero', () => {
    const rows = accessCenterProtectionRows({ ...ready, passkeys: null, sessions: null, recoveryConfigured: null });
    expect(rows.map((r) => r.description)).toEqual(['Not reported', 'Not reported', 'Not reported']);
  });
  it('extracts one bounded activity event and drops raw event payloads', () => {
    const data = { recent_activity: [{ event_type: 'sign_in', summary: 'Signed in', occurred_at: '2026-10-01T00:00:00Z', payload: { password: 'secret' } }] };
    expect(accessCenterLatestActivity(data).title).toBe('Signed in');
    expect(JSON.stringify(accessCenterLatestActivity(data))).not.toContain('secret');
    expect(accessCenterLatestActivity({ recent_activity: [] })).toBeNull();
  });
  it('only exposes Enterprise sections when explicitly enabled, while preserving pending review', () => {
    const personal = accessManageGroups();
    const enterprise = accessManageGroups({ enterpriseEnabled: true, hasApprovals: true, hasClients: true });
    expect(JSON.stringify(personal)).not.toContain('people');
    expect(enterprise.flatMap((g) => g.items.map((i) => i.id))).toEqual(expect.arrayContaining(['people', 'roles', 'approvals', 'automation']));
  });
});
