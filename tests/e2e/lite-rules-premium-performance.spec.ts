import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Instrumentation only: no new budget thresholds and no broad polling traffic.
test('records Rules first paint, Manage and Decision Insight interaction cost', async ({ page }, testInfo) => {
  await installScenario(page, 'rules-present');
  const start = Date.now();
  await page.goto('/?screen=rules');
  await waitForLiteScreenToSettle(page, 'rules');
  const firstPaintMs = Date.now() - start;
  const beginManage = Date.now();
  await page.getByRole('button', { name: 'Manage Safety Rules' }).click();
  await expect(page.getByRole('dialog', { name: 'Manage Safety Rules' })).toBeVisible();
  const manageOpenMs = Date.now() - beginManage;
  await page.keyboard.press('Escape');
  const explain = page.getByLabel('Latest Decision').getByRole('button', { name: 'Explain this' });
  let insightOpenMs: number | null = null;
  if (await explain.count()) {
    const beginInsight = Date.now();
    await explain.click();
    await expect(page.getByRole('dialog', { name: 'Decision Insight' })).toBeVisible();
    insightOpenMs = Date.now() - beginInsight;
    await page.keyboard.press('Escape');
  }
  const requests = await page.evaluate(() => performance.getEntriesByType('resource').filter(e => e.name.includes('/api/lite/')).map(e => new URL(e.name).pathname));
  const evidence = { firstPaintMs, manageOpenMs, insightOpenMs, requests };
  await testInfo.attach('rules-premium-timing', { body: JSON.stringify(evidence, null, 2), contentType: 'application/json' });
  // Owner-owned performance budgets and Android frame gates are unchanged.
  expect(firstPaintMs).toBeGreaterThanOrEqual(0);
});
