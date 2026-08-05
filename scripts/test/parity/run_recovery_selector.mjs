#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { selectRecoveryScreenView } from '../../../src/lib/liteViewModels.js';

const fixturePath = process.argv[2];
if (!fixturePath) {
  console.error('usage: run_recovery_selector.mjs <fixture.json>');
  process.exit(2);
}
const fixture = JSON.parse(await readFile(resolve(fixturePath), 'utf8'));
const selected = selectRecoveryScreenView(fixture.api || {});
process.stdout.write(`${JSON.stringify(selected, null, 2)}\n`);
