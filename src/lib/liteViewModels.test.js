import { describe, expect, it } from 'vitest';
import { selectDevicesScreenView, selectSecurityCoverageSummaryView } from './liteViewModels.js';

describe('security coverage view model authority', () => {
  it('does not mark selector defaults as reported coverage', () => {
    const view = selectSecurityCoverageSummaryView({
      scan_profile: 'quick',
      last_run: { run_id: 'run-without-coverage', status: 'completed' },
    });

    expect(view.coverage_reported).toBe(false);
  });

  it('preserves an explicitly reported empty coverage list', () => {
    const view = selectSecurityCoverageSummaryView({
      scan_profile: 'quick',
      coverage_summary: { profile: 'quick', checked_targets: [], skipped_targets: [] },
    });

    expect(view.coverage_reported).toBe(true);
    expect(view.checked_targets).toEqual([]);
    expect(view.skipped_targets).toEqual([]);
  });
});

describe('Devices saved projection authority', () => {
  it('retains backend degraded-read metadata in the canonical screen view', () => {
    const view = selectDevicesScreenView({
      status: 'degraded',
      devices: [],
      read_degraded: true,
      degraded_reason: 'projection_too_old',
      data_source: 'saved_snapshot',
      __liteSnapshot: { cached: true, stale: true, source: 'cache' },
    });

    expect(view).toMatchObject({
      read_degraded: true,
      degraded_reason: 'projection_too_old',
      data_source: 'saved_snapshot',
      __liteSnapshot: { cached: true, stale: true, source: 'cache' },
    });
  });
});
