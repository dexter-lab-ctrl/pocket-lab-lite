import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { selectRecoveryScreenView } from './liteViewModels.js';
import { recoveryParityScenarios } from '../test/fixtures/generated/parity/recovery-parity.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '../..');

function loadFixture(relativePath) {
  return JSON.parse(readFileSync(resolve(ROOT, relativePath), 'utf8'));
}

function expectSubset(actual, expected) {
  for (const [key, value] of Object.entries(expected || {})) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      expect(actual?.[key]).toBeTruthy();
      expectSubset(actual[key], value);
    } else {
      expect(actual?.[key]).toEqual(value);
    }
  }
}

describe('Recovery projection parity registry', () => {
  it('keeps every generated scenario linked to Storybook, Playwright, a11y and visual evidence', () => {
    expect(recoveryParityScenarios).toHaveLength(15);
    for (const scenario of recoveryParityScenarios) {
      expect(scenario.fixture).toMatch(/^src\/test\/fixtures\/generated\/parity\/recovery\//);
      expect(scenario.storyExport).toBeTruthy();
      expect(scenario.mswScenario).toBeTruthy();
      expect(scenario.visibleText.length).toBeGreaterThan(0);
    }
  });

  for (const scenario of recoveryParityScenarios) {
    it(`${scenario.id}: API payload maps through selectRecoveryScreenView`, () => {
      const fixture = loadFixture(scenario.fixture);
      const selected = selectRecoveryScreenView(fixture.api);
      expectSubset(selected, fixture.selector_expected);
      expect(fixture.authority.raw_sqlite_rows_included).toBe(false);
      expect(fixture.authority.raw_manifest_included).toBe(false);
    });
  }
});
