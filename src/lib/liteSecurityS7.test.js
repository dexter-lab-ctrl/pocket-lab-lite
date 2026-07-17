import { describe, expect, it } from 'vitest';
import {
  mergeSecurityHistoryPages,
  selectSecurityFindingDeltaView,
  selectSecurityProfileSnapshotView,
  selectSecurityStatePrecedence,
} from './liteViewModels.js';
import { liteSecurityProfileSnapshotPath } from './liteSafeSnapshots.js';

const savedQuick = {
  view_model: 'security-profile-snapshot-v2',
  profile: 'quick',
  latest_run_id: 'security-quick-saved',
  status: 'succeeded',
  score: 99,
  summary: 'Protected',
  completed_at: '2026-07-17T10:00:00Z',
  evidence_saved: true,
  finding_counts: { critical: 0, high: 0, medium: 0, low: 1, info: 0 },
  change_summary: { new: 0, resolved: 1, ongoing: 0, comparison_available: true, summary: 'No new changes. 1 item resolved.' },
  revision: 'security-profile-quick-1',
  sanitized: true,
};

function withSavedProfile(profile, snapshot, meta = null) {
  return {
    security_profiles: { [profile]: { ...snapshot, ...(meta ? { __liteSnapshot: meta } : {}) } },
    ...(meta ? { __liteSnapshot: meta } : {}),
  };
}

describe('Phase S7 Security state precedence', () => {
  it.each([
    ['quick', '', 'quick'],
    ['full', '', 'full'],
    ['app', 'photoprism', 'app'],
  ])('active %s scan outranks saved profile state', (profile, appId, expectedProfile) => {
    const payload = {
      ...withSavedProfile(profile, { ...savedQuick, profile, app_id: appId }),
      scan_progress: { active_scan: true, status: 'running', profile, app_id: appId, run_id: `active-${profile}` },
    };
    const result = selectSecurityStatePrecedence(payload, profile, appId);
    expect(result.precedence).toBe(1);
    expect(result.profile).toBe(expectedProfile);
  });

  it('saved Quick state does not hide an active Full scan', () => {
    const payload = {
      ...withSavedProfile('quick', savedQuick),
      scan_progress: { active_scan: true, status: 'running', profile: 'full', run_id: 'active-full' },
    };
    const result = selectSecurityStatePrecedence(payload, 'quick');
    expect(result.source).toBe('active_backend_scan');
    expect(result.profile).toBe('full');
    expect(result.matches_selected_profile).toBe(false);
  });

  it('fresh terminal FastAPI data outranks an offline Dexie snapshot', () => {
    const payload = {
      ...withSavedProfile('quick', savedQuick, { source: 'cache', cached: true, stale: true }),
      last_run: { run_id: 'fresh-terminal', status: 'failed', scan_profile: 'quick', completed_at: '2026-07-17T11:00:00Z' },
    };
    const result = selectSecurityStatePrecedence(payload, 'quick');
    expect(result.precedence).toBe(2);
    expect(result.state.run_id).toBe('fresh-terminal');
  });

  it('marks cached profile metadata as offline saved state', () => {
    const payload = withSavedProfile('quick', savedQuick, { source: 'cache', cached: true, stale: true, expired: true });
    const result = selectSecurityStatePrecedence(payload, 'quick');
    expect(result.source).toBe('offline_dexie_snapshot');
    expect(result.expired).toBe(true);
  });
});

describe('Phase S7 sanitized profile snapshots and deltas', () => {
  it('persists only bounded profile metadata', () => {
    const snapshot = selectSecurityProfileSnapshotView({
      security_profiles: {
        quick: {
          ...savedQuick,
          findings: [{ summary: '/data/data/private token=secret' }],
          evidence_refs: ['/private/evidence.json'],
          tool_status: [{ tool: 'lynis', status: 'succeeded', duration_ms: 10, timed_out: false }],
        },
      },
    }, 'quick');
    expect(snapshot.view_model).toBe('security-profile-snapshot-v2');
    expect(snapshot.evidence_saved).toBe(true);
    expect(snapshot).not.toHaveProperty('findings');
    expect(snapshot).not.toHaveProperty('evidence_refs');
    expect(JSON.stringify(snapshot)).not.toContain('/data/data/private');
  });

  it('does not claim no new changes without comparison data', () => {
    const delta = selectSecurityFindingDeltaView({ finding_delta: { comparison_available: false, comparison_reason: 'No earlier comparable check is available.' } });
    expect(delta.comparison_available).toBe(false);
    expect(delta.summary).not.toBe('No new changes');
  });

  it('keeps future app snapshot keys separate', () => {
    expect(liteSecurityProfileSnapshotPath('app', 'photoprism')).not.toBe(liteSecurityProfileSnapshotPath('app', 'future-app'));
  });
});

describe('Phase S7 cursor history merging', () => {
  it('appends older pages without duplicates', () => {
    const rows = mergeSecurityHistoryPages([
      { history: [{ run_id: 'c' }, { run_id: 'b' }] },
      { history: [{ run_id: 'b' }, { run_id: 'a' }] },
    ]);
    expect(rows.map((row) => row.run_id)).toEqual(['c', 'b', 'a']);
  });
});
