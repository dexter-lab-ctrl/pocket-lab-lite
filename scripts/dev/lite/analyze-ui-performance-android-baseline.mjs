#!/usr/bin/env node
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

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
    schema_version: '1.0.0',
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

export async function loadBaselineReports(directory) {
  const root = resolve(directory);
  const names = (await readdir(root))
    .filter((name) => /^ui-performance-android-baseline-.*\.json$/.test(name))
    .sort();
  const reports = [];
  for (const name of names) {
    const payload = JSON.parse(await readFile(resolve(root, name), 'utf8'));
    reports.push({ ...payload, _file: name });
  }
  return reports;
}

export async function analyzeBaselineDirectory(directory) {
  const reports = await loadBaselineReports(directory);
  if (!reports.length) throw new Error('no_android_baseline_evidence');
  return summarizeBaselineReports(reports);
}

async function main(argv = process.argv.slice(2)) {
  let directory = '.pocketlab-dev/performance';
  let output = '';
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--directory') directory = argv[++index] || '';
    else if (value === '--write') output = argv[++index] || '';
    else throw new Error(`unknown_argument:${value}`);
  }
  if (!directory) throw new Error('baseline_directory_required');
  const summary = await analyzeBaselineDirectory(directory);
  const encoded = JSON.stringify(summary, null, 2) + '\n';
  if (output) await writeFile(resolve(output), encoded, 'utf8');
  process.stdout.write(encoded);
  return 0;
}

const invokedAsScript = process.argv[1]
  && fileURLToPath(import.meta.url) === resolve(process.argv[1]);

if (invokedAsScript) {
  main().catch((error) => {
    console.error(`[ui-performance-android-baseline] ERROR: ${error?.message || error}`);
    process.exit(1);
  });
}
