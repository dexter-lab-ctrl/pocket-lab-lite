import { afterEach, describe, expect, it } from 'vitest';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  analyzeBaselineRuns,
  summarizeBaselineReports,
} from '../../scripts/dev/lite/analyze-ui-performance-android-baseline.mjs';

const roots = [];

function frame({
  p95 = 16.8,
  smooth = 1,
  gateSmooth = 1,
  severe = 0,
  gateSevere = 0,
  longTask = 0,
  loaf = 0,
} = {}) {
  return {
    p50_frame_ms: 16.7,
    p95_frame_ms: p95,
    max_frame_ms: p95,
    target_smooth_frame_ratio: smooth,
    gate_smooth_frame_ratio: gateSmooth,
    target_severe_frame_ratio: severe,
    gate_severe_frame_ratio: gateSevere,
    max_long_task_ms: longTask,
    max_long_animation_frame_ms: loaf,
    max_event_duration_ms: 0,
  };
}

async function writeJson(path, payload) {
  await writeFile(path, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

async function fixture({ baseline, interaction }) {
  const root = await mkdtemp(join(tmpdir(), 'pocketlab-android-baseline-'));
  roots.push(root);
  const sha = 'a'.repeat(40);
  for (let index = 1; index <= 3; index += 1) {
    const run = join(root, `run-0${index}`);
    const evidence = join(run, 'evidence');
    await mkdir(evidence, { recursive: true });
    const control = {
      source_commit: sha,
      samples: [baseline, baseline, baseline],
      sanitized: true,
    };
    await writeJson(join(run, 'baseline-before.json'), control);
    await writeJson(join(run, 'baseline-after.json'), control);
    await writeJson(join(run, 'device-state.json'), {
      schema_version: '1.0.0',
      screen_on: true,
      foreground_package: 'com.android.chrome',
      battery_saver: false,
      sanitized: true,
    });
    await writeJson(join(evidence, 'ui-performance-android-cdp-home-screen-steady.json'), {
      schema_version: '1.0.0',
      source_commit: sha,
      phase4_interaction: 'screen-steady',
      interaction_scope: 'home',
      interaction_surface: 'Home',
      performance_evidence_id: 'home.screen-steady',
      android_chrome_version: '153.0.0.0',
      ...interaction,
      sanitized: true,
    });
  }
  return root;
}

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

describe('Android baseline analyzer', () => {
  it('normalizes repeated interaction evidence against contemporaneous controls', async () => {
    const root = await fixture({
      baseline: frame({ p95: 41.8, smooth: 0.75, gateSmooth: 0.84 }),
      interaction: frame({ p95: 43.0, smooth: 0.73, gateSmooth: 0.82 }),
    });
    const { reports, summary } = await analyzeBaselineRuns(root);
    expect(reports).toHaveLength(1);
    expect(reports[0].repetition_count).toBe(3);
    expect(reports[0].platform_baseline_sample_count).toBe(18);
    expect(reports[0].baseline_classification).toBe('PLATFORM_DOMINATED');
    expect(reports[0].device_state_samples).toHaveLength(3);
    expect(summary.platform_limited_count).toBe(1);
  });

  it('surfaces material app incremental cost independently from absolute target status', async () => {
    const root = await fixture({
      baseline: frame(),
      interaction: frame({ p95: 55, smooth: 0.70, gateSmooth: 0.75, longTask: 58, loaf: 60 }),
    });
    const { reports, summary } = await analyzeBaselineRuns(root);
    expect(reports[0].baseline_classification).toBe('APP_INCREMENTAL_COST');
    expect(reports[0].target_met).toBe(false);
    expect(summary.app_materially_worse_count).toBe(1);
  });

  it('summarizes classifications without converting target misses into passes', () => {
    const summary = summarizeBaselineReports([
      { baseline_classification: 'PLATFORM_DOMINATED', target_met: false, gate_passed: false },
      { baseline_classification: 'WITHIN_BASELINE', target_met: true, gate_passed: true },
      { baseline_classification: 'MIXED', target_met: false, gate_passed: false },
    ]);
    expect(summary.report_count).toBe(3);
    expect(summary.absolute_target_passes).toBe(1);
    expect(summary.absolute_gate_passes).toBe(1);
    expect(summary.app_materially_worse_count).toBe(1);
    expect(summary.platform_limited_count).toBe(1);
  });
});
