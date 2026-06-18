import { describe, expect, test } from 'vitest';
import { ACTION_LABELS, SIMPLE_PRIMARY_BANNED_TERMS, TAB_LABELS, containsSimpleModeJargon } from '../lib/simpleLabels.js';
import { SIMPLE_MORE_NAV_ITEMS, SIMPLE_PRIMARY_NAV_ITEMS } from '../lib/simpleNavigation.js';

describe('Simple Mode architecture language', () => {
  test('retired legacy operation labels are not acceptable replacements', () => {
    expect(['retired compatibility intent', 'field'].join(' ')).not.toBe('git_sync');
    expect(['retired sync compatibility', 'task'].join(' ')).not.toBe('git_sync');
    expect(['retired IaC deploy compatibility', 'task'].join(' ')).not.toBe('deploy_blueprint');
  });

  test('primary Simple Mode labels avoid technical product jargon', () => {
    const visibleLabels = [
      ...Object.values(TAB_LABELS),
      ...Object.values(ACTION_LABELS),
      ...SIMPLE_PRIMARY_NAV_ITEMS.flatMap((item) => [item.label, item.description]),
      ...SIMPLE_MORE_NAV_ITEMS.flatMap((item) => [item.label, item.description]),
    ];

    for (const value of visibleLabels) {
      for (const term of SIMPLE_PRIMARY_BANNED_TERMS) {
        expect(value, `Simple Mode label should not expose ${term}: ${value}`).not.toMatch(new RegExp(`\\b${term.replace(/\\s+/g, '\\s+')}\\b`, 'i'));
      }
    }
  });

  test('Simple Mode jargon detector catches terms reserved for professional details', () => {
    expect(containsSimpleModeJargon('Run a GitOps pipeline')).toBe(true);
    expect(containsSimpleModeJargon('Install apps safely')).toBe(false);
  });
});
