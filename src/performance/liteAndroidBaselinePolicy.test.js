import { describe, expect, it } from 'vitest';
import {
  compareAndroidBaseline,
  LITE_ANDROID_BASELINE_POLICY,
  median,
  summarizeAndroidBaselineSamples,
} from './liteAndroidBaselinePolicy.js';

function sample({
  p95 = 16.8,
  smooth = 1,
  severe = 0,
  longTask = 0,
  loaf = 0,
  event = 0,
} = {}) {
  return {
    p50_frame_ms: 16.7,
    p95_frame_ms: p95,
    max_frame_ms: p95,
    target_smooth_frame_ratio: smooth,
    target_severe_frame_ratio: severe,
    max_long_task_ms: longTask,
    max_long_animation_frame_ms: loaf,
    max_event_duration_ms: event,
  };
}

describe('Android baseline normalization', () => {
  it('computes stable medians', () => {
    expect(median([16, 18, 17])).toBe(17);
    expect(median([16, 18, 17, 19])).toBe(17.5);
    expect(median([])).toBe(0);
  });

  it('summarizes repeated samples without using best-case values', () => {
    const summary = summarizeAndroidBaselineSamples([
      sample({ p95: 16.7 }),
      sample({ p95: 41.8 }),
      sample({ p95: 42.2 }),
    ]);
    expect(summary.sample_count).toBe(3);
    expect(summary.p95_frame_ms).toBe(41.8);
  });

  it('classifies a slow platform with a comparable interaction as platform dominated', () => {
    const result = compareAndroidBaseline({
      baselineSamples: [
        sample({ p95: 41.8, smooth: 0.75 }),
        sample({ p95: 42.0, smooth: 0.76 }),
        sample({ p95: 40.9, smooth: 0.77 }),
      ],
      interactionSamples: [
        sample({ p95: 43.0, smooth: 0.73 }),
        sample({ p95: 42.4, smooth: 0.74 }),
        sample({ p95: 42.1, smooth: 0.74 }),
      ],
    });
    expect(result.classification).toBe('PLATFORM_DOMINATED');
    expect(result.comparable).toBe(true);
  });

  it('classifies a healthy platform with a materially slower app interaction as app cost', () => {
    const result = compareAndroidBaseline({
      baselineSamples: [sample(), sample(), sample()],
      interactionSamples: [
        sample({ p95: 55, smooth: 0.70, longTask: 55 }),
        sample({ p95: 53, smooth: 0.71, longTask: 52 }),
        sample({ p95: 54, smooth: 0.72, longTask: 54 }),
      ],
    });
    expect(result.classification).toBe('APP_INCREMENTAL_COST');
    expect(result.reasons).toContain('p95_delta');
  });

  it('classifies a bad platform plus additional app cost as mixed', () => {
    const result = compareAndroidBaseline({
      baselineSamples: [
        sample({ p95: 35, smooth: 0.82 }),
        sample({ p95: 36, smooth: 0.83 }),
        sample({ p95: 34, smooth: 0.84 }),
      ],
      interactionSamples: [
        sample({ p95: 60, smooth: 0.60, loaf: 70 }),
        sample({ p95: 58, smooth: 0.61, loaf: 68 }),
        sample({ p95: 59, smooth: 0.62, loaf: 69 }),
      ],
    });
    expect(result.classification).toBe('MIXED');
  });

  it('fails closed to inconclusive when repetitions are insufficient', () => {
    const result = compareAndroidBaseline({
      baselineSamples: [sample(), sample()],
      interactionSamples: [sample(), sample()],
    });
    expect(result.classification).toBe('INCONCLUSIVE');
    expect(result.comparable).toBe(false);
    expect(result.reasons).toEqual(['insufficient_samples']);
    expect(LITE_ANDROID_BASELINE_POLICY.minSamplesPerSide).toBe(3);
  });
});
