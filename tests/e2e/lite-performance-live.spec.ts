import { expect, test } from '@playwright/test';
import { openTab, waitForLiteScreenToSettle } from './lite-test-helpers';
import {
  exerciseLiteScroll,
  expectLitePerformanceBudget,
  installLiteFrameSampler,
  measureLiteInteraction,
  writeLitePerformanceEvidence,
} from './lite-performance-helpers';

const LIVE_TABS = ['home', 'catalog', 'devices', 'security', 'identity', 'rules', 'recovery'] as const;
const REQUESTED_INTERACTION = String(process.env.LITE_QUALIFICATION_INTERACTION || '').trim().toLowerCase();
const LIVE_INTERACTION_IDS = new Set([
  ...LIVE_TABS.slice(1).map((screenId) => `live-navigation:${screenId}`),
  ...LIVE_TABS.map((screenId) => `live-scroll:${screenId}`),
]);

if (REQUESTED_INTERACTION && !LIVE_INTERACTION_IDS.has(REQUESTED_INTERACTION)) {
  throw new Error(`Unsupported live qualification interaction: ${REQUESTED_INTERACTION}`);
}

function interactionRequested(id: string) {
  return !REQUESTED_INTERACTION || REQUESTED_INTERACTION === id.toLowerCase();
}

test.describe('Pocket Lab Lite live UI performance qualification', () => {
  test.skip(
    process.env.LITE_E2E_LIVE !== '1',
    'Set LITE_E2E_LIVE=1 only against an explicitly prepared Pocket Lab Lite runtime.',
  );

  test.beforeEach(async ({ page }) => {
    await installLiteFrameSampler(page);
  });

  test('real runtime tab navigation meets the UI frame gate without write actions', async ({ page }, testInfo) => {
    await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page, 'home');

    for (const screenId of LIVE_TABS.slice(1)) {
      const interactionId = `live-navigation:${screenId}`;
      if (!interactionRequested(interactionId)) continue;
      const report = await measureLiteInteraction(
        page,
        testInfo,
        interactionId,
        async () => {
          await openTab(page, screenId);
          await waitForLiteScreenToSettle(page, screenId);
          await expect(page.locator(`[data-lite-screen-id="${screenId}"]`)).toBeVisible();
        },
        { settleMs: 1000, mode: 'live' },
      );
      expectLitePerformanceBudget(report);
      await writeLitePerformanceEvidence(testInfo, report);
    }
  });

  test('real runtime read-only scrolling meets the UI frame gate on every tab', async ({ page }, testInfo) => {
    await page.goto('/?screen=home');
    for (const screenId of LIVE_TABS) {
      const interactionId = `live-scroll:${screenId}`;
      if (!interactionRequested(interactionId)) continue;
      if (screenId !== 'home') await openTab(page, screenId);
      await waitForLiteScreenToSettle(page, screenId);

      const report = await measureLiteInteraction(
        page,
        testInfo,
        interactionId,
        async () => {
          await exerciseLiteScroll(page, 820);
        },
        { settleMs: 180, mode: 'live' },
      );
      expectLitePerformanceBudget(report);
      await writeLitePerformanceEvidence(testInfo, report);
    }
  });
});
