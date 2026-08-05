#!/usr/bin/env node
import { readFile, readdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { selectRecoveryScreenView } from '../../../src/lib/liteViewModels.js';

const root = resolve(new URL('../../..', import.meta.url).pathname);
const fixtureDir = resolve(root, 'src/test/fixtures/generated/parity/recovery');

function compareSubset(actual, expected, path = '$') {
  const failures = [];
  if (expected && typeof expected === 'object' && !Array.isArray(expected)) {
    if (!actual || typeof actual !== 'object' || Array.isArray(actual)) return [`${path}: expected object`];
    for (const [key, value] of Object.entries(expected)) {
      if (!(key in actual)) failures.push(`${path}.${key}: missing`);
      else failures.push(...compareSubset(actual[key], value, `${path}.${key}`));
    }
  } else if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures.push(`${path}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
  return failures;
}

let checked = 0;
for (const name of (await readdir(fixtureDir)).filter((value) => value.endsWith('.json')).sort()) {
  const fixture = JSON.parse(await readFile(resolve(fixtureDir, name), 'utf8'));
  const selected = selectRecoveryScreenView(fixture.api || {});
  const failures = compareSubset(selected, fixture.selector_expected || {});
  if (failures.length) {
    console.error(`${fixture.scenario_id}: ${failures.join('; ')}`);
    process.exitCode = 1;
  }
  checked += 1;
}
if (!process.exitCode) console.log(`PASS Recovery selector parity: ${checked} generated scenarios`);
