import { describe, expect, it } from 'vitest';
import { selectSecuritySafetyStoryView, selectSecuritySummaryView } from './liteViewModels.js';

const completedQuick = (overrides = {}) => ({
  status: 'completed',
  scan_profile: 'quick',
  last_run: {
    run_id: 'Security-Run-Exact-Case',
    status: 'completed',
    scan_profile: 'quick',
    completed_at: '2026-09-01T10:00:00Z',
    items_to_review: 0,
    ...overrides,
  },
});

describe('selectSecuritySafetyStoryView', () => {
  it('does not fabricate a score or full-protection claim when the backend did not report one', () => {
    const story = selectSecuritySafetyStoryView(completedQuick());

    expect(story.score).toEqual({ value: null, provenance: 'not_reported' });
    expect(story.headline).toBe('No issues requiring attention were reported');
    expect(story.summary).toContain('Quick Scan');
    expect(story.consequence).toContain('coverage');
    expect(story.headline).not.toContain('Protected');
    expect(selectSecuritySummaryView(completedQuick()).score).toBeNull();
    expect(selectSecuritySummaryView(completedQuick()).score_provenance).toBe('not_reported');
  });

  it('keeps an explicitly supplied prepared score as backend-reported', () => {
    const story = selectSecuritySafetyStoryView(completedQuick({ score: 87 }));

    expect(story.score).toEqual({ value: 87, provenance: 'backend_reported' });
    expect(selectSecuritySummaryView(completedQuick({ score: 87 }))).toMatchObject({ score: 87, score_provenance: 'backend_reported' });
  });

  it('keeps attention distinct from an execution failure and directs the user to issues', () => {
    const story = selectSecuritySafetyStoryView(completedQuick({ status: 'review', items_to_review: 2 }));

    expect(story.state).toBe('attention');
    expect(story.headline).toBe('2 items need review');
    expect(story.primaryAction).toEqual({ id: 'manage', label: 'Review issues', section: 'issues' });
    expect(story.consequence).toContain('does not by itself');
  });

  it('labels saved results as saved and never treats them as current protection', () => {
    const story = selectSecuritySafetyStoryView(completedQuick(), { savedStateOnly: true, backendReachable: false });

    expect(story.state).toBe('saved');
    expect(story.headline).toBe('Showing saved Security information');
    expect(story.freshness.detail).toContain('cannot be confirmed');
    expect(story.primaryAction).toEqual({ id: 'refresh', label: 'Refresh Safety Center' });
  });

  it('keeps queued work distinct from running and terminal completion', () => {
    const story = selectSecuritySafetyStoryView({
      scan_progress: { status: 'queued', active_scan: true, stage: 'Waiting for a worker' },
      scan_profile: 'quick',
    });

    expect(story.state).toBe('queued');
    expect(story.headline).toContain('getting ready');
    expect(story.primaryAction).toBeNull();
  });
});
