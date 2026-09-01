import { describe, expect, it } from 'vitest';
import { selectRecoveryOperationalStoryView } from './liteViewModels.js';

const verifiedBackup = (overrides = {}) => ({
  latest_backup: {
    backup_id: 'backup-1', status: 'completed', verification_status: 'verified', created_at: '2026-09-01T10:00:00Z',
    ...overrides,
  },
});

describe('selectRecoveryOperationalStoryView', () => {
  it('asks for a first backup without surfacing restore', () => {
    const story = selectRecoveryOperationalStoryView({});
    expect(story.state).toBe('no_backup');
    expect(story.nextAction).toEqual({ id: 'backup', label: 'Back Up Now' });
  });

  it('keeps a saved backup distinct from a verified backup', () => {
    const story = selectRecoveryOperationalStoryView(verifiedBackup({ verification_status: 'pending' }));
    expect(story.state).toBe('verification_pending');
    expect(story.nextAction).toEqual({ id: 'verify', label: 'Verify Backup' });
    expect(story.summary).toContain('not confirmed');
  });

  it('offers preview after verified evidence without claiming full protection', () => {
    const story = selectRecoveryOperationalStoryView(verifiedBackup());
    expect(story.state).toBe('verified');
    expect(story.nextAction).toEqual({ id: 'preview', label: 'Preview Restore' });
    expect(story.headline).not.toContain('fully');
  });

  it('keeps preview readiness separate from a completed restore', () => {
    const story = selectRecoveryOperationalStoryView({
      ...verifiedBackup(),
      latest_restore_preview: { preview_id: 'preview-1', backup_id: 'backup-1', status: 'ready', restore_allowed: true, change_count: 3 },
    });
    expect(story.state).toBe('preview_ready');
    expect(story.summary).toContain('Nothing was changed');
    expect(story.nextAction).toEqual({ id: 'manage', label: 'Review Restore', section: 'restore' });
  });

  it('does not call a completed restore healthy until backend health evidence is present', () => {
    const story = selectRecoveryOperationalStoryView({
      ...verifiedBackup(),
      last_restore: { restore_id: 'restore-1', backup_id: 'backup-1', status: 'completed', completed_at: '2026-09-01T11:00:00Z' },
    });
    expect(story.state).toBe('restore_health_pending');
    expect(story.headline).toContain('health validation is still pending');
  });

  it('never lets saved information authorize a restore action', () => {
    const story = selectRecoveryOperationalStoryView(verifiedBackup(), { savedStateOnly: true, backendReachable: false });
    expect(story.state).toBe('saved');
    expect(story.nextAction).toEqual({ id: 'refresh', label: 'Refresh Recovery' });
    expect(story.freshness.detail).toContain('cannot be confirmed');
  });
});
