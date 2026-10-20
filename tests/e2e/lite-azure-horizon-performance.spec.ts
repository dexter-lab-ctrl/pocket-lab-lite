import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import {
  expectLitePerformanceBudget, installLiteFrameSampler,
  measureLiteInteraction, writeLitePerformanceEvidence,
} from './lite-performance-helpers';

// Adds Azure interactions to the existing PR #588 sampler, without weaker budgets.
test.beforeEach(async ({ page }) => { await installLiteFrameSampler(page); });
test('[interaction] Azure theme switch uses the existing performance budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  const picker = page.getByRole('combobox', { name: 'Appearance' });
  const report = await measureLiteInteraction(page, testInfo, 'azure-theme-switch', async () => {
    await picker.selectOption('dark');
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme', 'dark');
  }, { settleMs: 180, mode: 'mocked' });
  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});

test('[interaction] Azure workspace panel opens within the existing frame contract', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  const report = await measureLiteInteraction(page, testInfo, 'azure-home-workspace-details', async () => {
    await page.getByRole('button', { name: 'Workspace details' }).click();
    await expect(page.getByRole('dialog', { name: 'Workspace details' })).toBeVisible();
  }, { settleMs: 180, mode: 'mocked' });
  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});
