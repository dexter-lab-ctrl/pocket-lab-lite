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
  if (payload.sanitized !== true || payload.schema_version !== '1.0.0') {
    console.error(`[ui-performance] FAIL ${label}: invalid evidence contract`);
    failures += 1;
    continue;
  }
  if (payload.gate_passed !== true) {
    console.error(`[ui-performance] FAIL ${label}: ${(payload.gate_violations || []).join(', ')}`);
    failures += 1;
  } else {
    console.log(`[ui-performance] PASS ${label}: p95=${payload.p95_frame_ms}ms smooth=${payload.target_smooth_frame_ratio}`);
  }
  if (payload.target_met !== true) {
    targetMisses += 1;
    console.warn(`[ui-performance] TARGET-MISS ${label}: ${(payload.target_misses || []).join(', ')}`);
  }
}

console.log(`[ui-performance] evidence=${files.length} gate_failures=${failures} target_misses=${targetMisses}`);
if (failures) process.exit(1);
