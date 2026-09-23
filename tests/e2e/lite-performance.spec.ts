import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import {
  expectLitePerformanceBudget,
  installLiteFrameSampler,
  measureLiteInteraction,
  writeLitePerformanceEvidence,
} from './lite-performance-helpers';

const SCREEN_CASES = [
  ['home', 'healthy'],
  ['catalog', 'healthy'],
  ['devices', 'devices-repairing'],
  ['security', 'security-full-running'],
  ['identity', 'identity-password-change-required'],
  ['rules', 'rules-disabled'],
  ['recovery', 'recovery-backup-running'],
] as const;

test.beforeEach(async ({ page }) => {
  await installLiteFrameSampler(page);
});

for (const [screenId, scenario] of SCREEN_CASES) {
  test(`${screenId} stays within the UI frame gate during visible work`, async ({ page }, testInfo) => {
    await installScenario(page, scenario);
    await page.goto(`/?screen=${screenId}`);
    await waitForLiteScreenToSettle(page, screenId);
    await expect(page.locator(`[data-lite-screen-id="${screenId}"]`)).toBeVisible();

    const report = await measureLiteInteraction(
      page,
      testInfo,
      `${screenId}:screen-steady`,
      async () => {
        await page.evaluate(() => window.scrollBy({ top: Math.max(160, Math.round(window.innerHeight * 0.45)), behavior: 'auto' }));
        await page.waitForTimeout(120);
        await page.evaluate(() => window.scrollBy({ top: -Math.max(160, Math.round(window.innerHeight * 0.45)), behavior: 'auto' }));
      },
      { settleMs: 900, mode: 'mocked' },
    );

    expectLitePerformanceBudget(report);
    await writeLitePerformanceEvidence(testInfo, report);
  });
}

test('cross-tab navigation stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');

  const report = await measureLiteInteraction(
    page,
    testInfo,
    'screen-navigation:home-to-devices',
    async () => {
      const devicesButton = page.getByRole('button', { name: /^Devices$/ }).first();
      await devicesButton.hover().catch(() => null);
      await devicesButton.click();
      await waitForLiteScreenToSettle(page, 'devices');
    },
    { settleMs: 800, mode: 'mocked' },
  );

  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});

test('App Catalog Manage overlay stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page, 'catalog');

  const manage = page.getByRole('button', { name: /^Manage$/ }).first();
  await expect(manage).toBeVisible();

  const report = await measureLiteInteraction(
    page,
    testInfo,
    'catalog:manage-open',
    async () => {
      await manage.click();
      await expect(page.locator('[data-lite-overlay-portal="true"]')).toBeVisible();
    },
    { settleMs: 850, mode: 'mocked' },
  );

  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});
