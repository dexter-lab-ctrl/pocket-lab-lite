import { readdir, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const directory = resolve('.pocketlab-dev/performance');

let files = [];
try {
  files = (await readdir(directory)).filter((name) => /^ui-performance-.*\.json$/.test(name)).sort();
} catch {
  console.error('[ui-performance] no performance evidence directory found');
  process.exit(1);
}

if (!files.length) {
  console.error('[ui-performance] no performance evidence files found');
  process.exit(1);
}

let failures = 0;
let targetMisses = 0;
for (const file of files) {
  const payload = JSON.parse(await readFile(resolve(directory, file), 'utf8'));
  const label = `${payload.browser_project || 'unknown'} ${payload.interaction || file}`;
  if (
    payload.sanitized !== true
    || payload.schema_version !== '1.0.0'
    || !/^[0-9a-f]{40}$/.test(String(payload.source_commit || ''))
    || /^0+$/.test(String(payload.source_commit || ''))
  ) {
    console.error(`[ui-performance] FAIL ${label}: invalid evidence contract`);
    failures += 1;
    continue;
  }
  if (payload.qualification_surface === 'android-cdp-baseline-normalized') {
    const classifications = new Set([
      'WITHIN_BASELINE',
      'PLATFORM_DOMINATED',
      'APP_INCREMENTAL_COST',
      'MIXED',
      'INCONCLUSIVE',
    ]);
    const baselineContractValid = (
      payload.baseline_schema_version === '1.0.0'
      && Number(payload.repetition_count) >= 3
      && Number(payload.platform_baseline_sample_count) >= 6
      && payload.platform_baseline
      && typeof payload.platform_baseline === 'object'
      && payload.interaction_summary
      && typeof payload.interaction_summary === 'object'
      && payload.baseline_delta
      && typeof payload.baseline_delta === 'object'
      && classifications.has(String(payload.baseline_classification || ''))
      && Array.isArray(payload.baseline_reasons)
      && Array.isArray(payload.device_state_samples)
      && payload.device_state_samples.length >= 3
    );
    if (!baselineContractValid) {
      console.error(`[ui-performance] FAIL ${label}: invalid Android baseline-normalized evidence contract`);
      failures += 1;
      continue;
    }
  }
  if (payload.gate_passed !== true) {
    console.error(`[ui-performance] FAIL ${label}: ${(payload.gate_violations || []).join(', ')}`);
    failures += 1;
  }
  if (payload.mode === 'mocked' && payload.react_profile_available !== true) {
    console.error(`[ui-performance] FAIL ${label}: mocked evidence is missing React Profiler data`);
    failures += 1;
  }
  if (payload.react_profile_available === true && payload.react_commit_gate_passed !== true) {
    console.error(`[ui-performance] FAIL ${label}: React commit p95=${payload.react_commit_p95_ms}ms exceeded the hard gate`);
    failures += 1;
  }
  if (payload.gate_passed === true && (payload.react_profile_available !== true || payload.react_commit_gate_passed === true)) {
    const react = payload.react_profile_available === true ? ` react_p95=${payload.react_commit_p95_ms}ms` : '';
    console.log(`[ui-performance] PASS ${label}: p95=${payload.p95_frame_ms}ms smooth=${payload.target_smooth_frame_ratio}${react}`);
  }
  if (payload.target_met !== true) {
    targetMisses += 1;
    console.warn(`[ui-performance] TARGET-MISS ${label}: ${(payload.target_misses || []).join(', ')}`);
  }
  if (payload.react_profile_available === true && payload.react_commit_target_met !== true) {
    targetMisses += 1;
    console.warn(`[ui-performance] TARGET-MISS ${label}: react_commit_p95_ms=${payload.react_commit_p95_ms}`);
  }
}

console.log(`[ui-performance] evidence=${files.length} gate_failures=${failures} target_misses=${targetMisses}`);
if (failures && process.env.LITE_PERF_COLLECT_EVIDENCE === '1') {
  console.warn('[ui-performance] collection-only mode retained gate failures for matrix coverage');
} else if (failures) {
  process.exit(1);
}
