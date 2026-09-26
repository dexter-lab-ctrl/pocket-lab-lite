#!/usr/bin/env node
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { basename, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  compareAndroidBaseline,
  LITE_ANDROID_BASELINE_SCHEMA_VERSION,
  summarizeAndroidBaselineSamples,
} from '../../../src/performance/liteAndroidBaselinePolicy.js';
import { LITE_UI_PERFORMANCE_BUDGET } from '../../../src/performance/litePerformanceBudget.js';

function metricSample(report) {
  return {
    p50_frame_ms: Number(report.p50_frame_ms || 0),
    p95_frame_ms: Number(report.p95_frame_ms || 0),
    max_frame_ms: Number(report.max_frame_ms || 0),
    target_smooth_frame_ratio: Number(report.target_smooth_frame_ratio || 0),
    gate_smooth_frame_ratio: Number(report.gate_smooth_frame_ratio ?? report.target_smooth_frame_ratio ?? 0),
    target_severe_frame_ratio: Number(report.target_severe_frame_ratio || 0),
    gate_severe_frame_ratio: Number(report.gate_severe_frame_ratio ?? report.target_severe_frame_ratio ?? 0),
    max_long_task_ms: Number(report.max_long_task_ms || 0),
    max_long_animation_frame_ms: Number(report.max_long_animation_frame_ms || 0),
    max_event_duration_ms: Number(report.max_event_duration_ms || 0),
  };
}

function absoluteStatus(summary) {
  const target = LITE_UI_PERFORMANCE_BUDGET.target;
  const gate = LITE_UI_PERFORMANCE_BUDGET.gate;
  const misses = [];
  const violations = [];
  const evaluate = (limits, output) => {
    if (summary.p95_frame_ms > limits.maxP95FrameMs) output.push('p95_frame_ms');
    if (summary.target_smooth_frame_ratio < limits.minSmoothFrameRatio) output.push('smooth_frame_ratio');
    if (summary.target_severe_frame_ratio > limits.maxSevereFrameRatio) output.push('severe_frame_ratio');
    if (summary.max_long_task_ms > limits.maxLongTaskMs) output.push('long_task_ms');
    if (summary.max_long_animation_frame_ms > limits.maxLongAnimationFrameMs) output.push('long_animation_frame_ms');
    if (summary.max_event_duration_ms > limits.maxInpMs) output.push('event_duration_ms');
  };
  evaluate(target, misses);
  if (summary.p95_frame_ms > gate.maxP95FrameMs) violations.push('p95_frame_ms');
  if (summary.gate_smooth_frame_ratio < gate.minSmoothFrameRatio) violations.push('smooth_frame_ratio');
  if (summary.gate_severe_frame_ratio > gate.maxSevereFrameRatio) violations.push('severe_frame_ratio');
  if (summary.max_long_task_ms > gate.maxLongTaskMs) violations.push('long_task_ms');
  if (summary.max_long_animation_frame_ms > gate.maxLongAnimationFrameMs) violations.push('long_animation_frame_ms');
  if (summary.max_event_duration_ms > gate.maxInpMs) violations.push('event_duration_ms');
  return {
    target_met: misses.length === 0,
    target_misses: misses,
    gate_passed: violations.length === 0,
    gate_violations: violations,
  };
}

export function summarizeBaselineReports(reports = []) {
  const safe = reports.filter((report) => report && typeof report === 'object');
  const counts = {
    PLATFORM_DOMINATED: 0,
    APP_INCREMENTAL_COST: 0,
    MIXED: 0,
    WITHIN_BASELINE: 0,
    INCONCLUSIVE: 0,
  };
  let absoluteTargetPasses = 0;
  let absoluteGatePasses = 0;
  for (const report of safe) {
    const classification = String(report.baseline_classification || 'INCONCLUSIVE');
    if (Object.hasOwn(counts, classification)) counts[classification] += 1;
    else counts.INCONCLUSIVE += 1;
    if (report.target_met === true) absoluteTargetPasses += 1;
    if (report.gate_passed === true) absoluteGatePasses += 1;
  }
  return {
    schema_version: LITE_ANDROID_BASELINE_SCHEMA_VERSION,
    report_count: safe.length,
    absolute_target_passes: absoluteTargetPasses,
    absolute_gate_passes: absoluteGatePasses,
    classifications: counts,
    app_materially_worse_count: counts.APP_INCREMENTAL_COST + counts.MIXED,
    platform_limited_count: counts.PLATFORM_DOMINATED,
    within_baseline_count: counts.WITHIN_BASELINE,
    inconclusive_count: counts.INCONCLUSIVE,
    sanitized: true,
  };
}

async function json(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

export async function analyzeBaselineRuns(runsRoot, outputDir = '') {
  const root = resolve(runsRoot);
  const runNames = (await readdir(root, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory() && /^run-\d+$/.test(entry.name))
    .map((entry) => entry.name)
    .sort();
  if (runNames.length < 3) throw new Error('insufficient_android_baseline_runs');

  const groups = new Map();
  const runStates = [];
  let sourceCommit = '';
  for (const runName of runNames) {
    const runRoot = resolve(root, runName);
    const before = await json(resolve(runRoot, 'baseline-before.json'));
    const after = await json(resolve(runRoot, 'baseline-after.json'));
    const state = await json(resolve(runRoot, 'device-state.json'));
    runStates.push({ run: runName, ...state });
    sourceCommit ||= String(before.source_commit || '');
    if (sourceCommit !== String(before.source_commit || '') || sourceCommit !== String(after.source_commit || '')) {
      throw new Error('baseline_source_commit_mismatch');
    }
    const baselineSamples = [
      ...(before.samples || []).map(metricSample),
      ...(after.samples || []).map(metricSample),
    ];
    const evidenceDir = resolve(runRoot, 'evidence');
    const evidenceNames = (await readdir(evidenceDir))
      .filter((name) => /^ui-performance-android-cdp-.*\.json$/.test(name))
      .sort();
    if (!evidenceNames.length) throw new Error(`missing_android_evidence:${runName}`);
    for (const evidenceName of evidenceNames) {
      const report = await json(resolve(evidenceDir, evidenceName));
      if (String(report.source_commit || '') !== sourceCommit) throw new Error('interaction_source_commit_mismatch');
      const key = String(
        report.performance_evidence_id
        || `${report.interaction_scope || 'unknown'}.${report.phase4_interaction || report.interaction || evidenceName}`,
      );
      const group = groups.get(key) || {
        key,
        interaction: report.phase4_interaction || report.interaction,
        scope: report.interaction_scope || 'unknown',
        surface: report.interaction_surface || 'unknown',
        evidenceId: report.performance_evidence_id || null,
        baselineSamples: [],
        interactionSamples: [],
        chromeVersions: new Set(),
      };
      group.baselineSamples.push(...baselineSamples);
      group.interactionSamples.push(metricSample(report));
      if (report.android_chrome_version) group.chromeVersions.add(String(report.android_chrome_version));
      groups.set(key, group);
    }
  }

  const reports = [];
  if (outputDir) await mkdir(resolve(outputDir), { recursive: true });
  for (const group of groups.values()) {
    const comparison = compareAndroidBaseline({
      baselineSamples: group.baselineSamples,
      interactionSamples: group.interactionSamples,
    });
    const absolute = absoluteStatus(comparison.interaction);
    const report = {
      schema_version: '1.0.0',
      baseline_schema_version: LITE_ANDROID_BASELINE_SCHEMA_VERSION,
      evidence_type: 'android-baseline-normalized-interaction',
      source_commit: sourceCommit,
      mode: 'live',
      qualification_surface: 'android-cdp-baseline-normalized',
      browser_project: 'android-cdp-baseline',
      rendering_surface: 'physical-android-chrome',
      interaction: group.interaction,
      phase4_interaction: group.interaction,
      interaction_scope: group.scope,
      interaction_surface: group.surface,
      performance_evidence_id: group.evidenceId,
      android_chrome_versions: [...group.chromeVersions].sort(),
      repetition_count: group.interactionSamples.length,
      platform_baseline_sample_count: group.baselineSamples.length,
      platform_baseline: comparison.baseline,
      interaction_summary: comparison.interaction,
      baseline_delta: comparison.delta,
      baseline_classification: comparison.classification,
      baseline_comparable: comparison.comparable,
      baseline_reasons: comparison.reasons,
      p50_frame_ms: comparison.interaction.p50_frame_ms,
      p95_frame_ms: comparison.interaction.p95_frame_ms,
      max_frame_ms: comparison.interaction.max_frame_ms,
      target_smooth_frame_ratio: comparison.interaction.target_smooth_frame_ratio,
      gate_smooth_frame_ratio: comparison.interaction.gate_smooth_frame_ratio,
      target_severe_frame_ratio: comparison.interaction.target_severe_frame_ratio,
      gate_severe_frame_ratio: comparison.interaction.gate_severe_frame_ratio,
      max_long_task_ms: comparison.interaction.max_long_task_ms,
      max_long_animation_frame_ms: comparison.interaction.max_long_animation_frame_ms,
      max_event_duration_ms: comparison.interaction.max_event_duration_ms,
      ...absolute,
      device_state_samples: runStates,
      sanitized: true,
    };
    reports.push(report);
    if (outputDir) {
      const safeName = keyName(group.key);
      await writeFile(
        resolve(outputDir, `ui-performance-android-baseline-${safeName}.json`),
        JSON.stringify(report, null, 2) + '\n',
        'utf8',
      );
    }
  }
  reports.sort((left, right) => String(left.performance_evidence_id || left.interaction).localeCompare(
    String(right.performance_evidence_id || right.interaction),
  ));
  return { reports, summary: summarizeBaselineReports(reports) };
}

function keyName(value) {
  return String(value || 'unknown').toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 100) || 'unknown';
}

async function main(argv = process.argv.slice(2)) {
  let runsRoot = '';
  let outputDir = '.pocketlab-dev/performance';
  let summaryPath = '';
  let failOnAppCost = false;
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--runs-root') runsRoot = argv[++index] || '';
    else if (value === '--output-dir') outputDir = argv[++index] || '';
    else if (value === '--write-summary') summaryPath = argv[++index] || '';
    else if (value === '--fail-on-app-cost') failOnAppCost = true;
    else throw new Error(`unknown_argument:${value}`);
  }
  if (!runsRoot) throw new Error('runs_root_required');
  const result = await analyzeBaselineRuns(runsRoot, outputDir);
  const encoded = JSON.stringify(result.summary, null, 2) + '\n';
  if (summaryPath) await writeFile(resolve(summaryPath), encoded, 'utf8');
  process.stdout.write(encoded);
  if (failOnAppCost && result.summary.app_materially_worse_count > 0) process.exitCode = 1;
}

const invokedAsScript = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (invokedAsScript) {
  main().catch((error) => {
    console.error(`[ui-performance-android-baseline] ERROR: ${error?.message || error}`);
    process.exit(1);
  });
}
