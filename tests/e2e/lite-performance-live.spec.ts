import { expect, test } from '@playwright/test';
import { openTab, waitForLiteScreenToSettle } from './lite-test-helpers';
import {
  expectLitePerformanceBudget,
  installLiteFrameSampler,
  measureLiteInteraction,
  writeLitePerformanceEvidence,
} from './lite-performance-helpers';

const LIVE_TABS = ['home', 'catalog', 'devices', 'security', 'identity', 'rules', 'recovery'] as const;

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
      const report = await measureLiteInteraction(
        page,
        testInfo,
        `live-navigation:${screenId}`,
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
      if (screenId !== 'home') await openTab(page, screenId);
      await waitForLiteScreenToSettle(page, screenId);

      const report = await measureLiteInteraction(
        page,
        testInfo,
        `live-scroll:${screenId}`,
        async () => {
          await page.evaluate(() => window.scrollBy({ top: Math.max(200, Math.round(window.innerHeight * 0.5)), behavior: 'auto' }));
          await page.waitForTimeout(160);
          await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'auto' }));
        },
        { settleMs: 900, mode: 'live' },
      );
      expectLitePerformanceBudget(report);
      await writeLitePerformanceEvidence(testInfo, report);
    }
  });
});
