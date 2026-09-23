import { describe, expect, it } from 'vitest';
import {
  LITE_UI_PERFORMANCE_BUDGET,
  percentile,
  sanitizeLitePerformanceName,
  summarizeLiteFrames,
  summarizeReactCommits,
} from './litePerformanceBudget.js';

describe('Pocket Lab Lite UI performance contract', () => {
  it('keeps the 60 Hz frame budget explicit', () => {
    expect(LITE_UI_PERFORMANCE_BUDGET.refreshHz).toBe(60);
    expect(LITE_UI_PERFORMANCE_BUDGET.frameBudgetMs).toBeCloseTo(16.67, 2);
    expect(LITE_UI_PERFORMANCE_BUDGET.target.minSmoothFrameRatio).toBeGreaterThanOrEqual(0.95);
  });

  it('computes deterministic percentiles', () => {
    expect(percentile([10, 11, 12, 13, 14], 0.95)).toBe(14);
    expect(percentile([], 0.95)).toBe(0);
  });

  it('passes a stable 60 Hz interaction and flags severe regressions', () => {
    const stable = summarizeLiteFrames(Array.from({ length: 80 }, () => 16.7), { warmupFrames: 0 });
    expect(stable.target_met).toBe(true);
    expect(stable.gate_passed).toBe(true);

    const regressed = summarizeLiteFrames([16, 17, 18, 45, 52, 60, 49, 55, 17, 16], { warmupFrames: 0 });
    expect(regressed.gate_passed).toBe(false);
    expect(regressed.gate_violations.length).toBeGreaterThan(0);
  });

  it('keeps profiler evidence sanitized and bounded to timing data', () => {
    expect(sanitizeLitePerformanceName('Security / Manage <token>')).toBe('security-manage-token');
    const commits = summarizeReactCommits([2, 4, 6, 8]);
    expect(commits.p95_commit_ms).toBe(8);
    expect(commits.target_met).toBe(true);
  });
});
