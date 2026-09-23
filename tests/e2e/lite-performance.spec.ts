import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import {
  exerciseLiteScroll,
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
        await exerciseLiteScroll(page);
      },
      { settleMs: 180, mode: 'mocked' },
    );

    expectLitePerformanceBudget(report);
    await writeLitePerformanceEvidence(testInfo, report);
  });
}

test('[interaction] cross-tab navigation stays inside the render budget', async ({ page }, testInfo) => {
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

const MANAGE_CASES = [
  ['home', 'healthy', /Workspace details/i, '[role="dialog"]'],
  ['catalog', 'catalog-ready', /^Manage$/i, '[role="dialog"]'],
  ['devices', 'healthy', /Manage Test-Phone-4/i, '.lite-device-details-panel'],
  ['security', 'healthy', /Manage Security details/i, '[role="dialog"]'],
  ['identity', 'healthy', /Manage Access/i, '[role="dialog"]'],
  ['rules', 'healthy', /Manage Safety Rules/i, '[role="dialog"]'],
  ['recovery', 'healthy', /Manage Recovery/i, '[role="dialog"]'],
] as const;

for (const [screenId, scenario, openerName, surfaceSelector] of MANAGE_CASES) {
  test(`[interaction] ${screenId} Manage-open stays inside the render budget`, async ({ page }, testInfo) => {
    await installScenario(page, scenario);
    await page.goto(`/?screen=${screenId}`);
    await waitForLiteScreenToSettle(page, screenId);

    const opener = page.getByRole('button', { name: openerName }).first();
    await expect(opener).toBeVisible();

    const report = await measureLiteInteraction(
      page,
      testInfo,
      `${screenId}:manage-open`,
      async () => {
        await opener.click();
        await expect(page.locator(`${surfaceSelector}:visible`).first()).toBeVisible();
      },
      { settleMs: 320, mode: 'mocked' },
    );

    expectLitePerformanceBudget(report);
    await writeLitePerformanceEvidence(testInfo, report);
  });
}

test('[interaction] Home refresh feedback stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');

  const refresh = page.getByRole('button', { name: /^Refresh$/ }).first();
  await expect(refresh).toBeVisible();

  const report = await measureLiteInteraction(
    page,
    testInfo,
    'home:refresh-feedback',
    async () => {
      await refresh.click();
      await expect(page.locator('.lite-refresh-status-popover')).toBeVisible();
    },
    { settleMs: 420, mode: 'mocked' },
  );

  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});
