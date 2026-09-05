import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { installScenario, openTab, waitForLiteScreenToSettle, watchApiFailures } from './lite-test-helpers';

async function openServerDetails(page) {
  await openTab(page, 'Devices', 'devices');
  await waitForLiteScreenToSettle(page, 'devices');
  const serverCard = page.locator('.lite-device-card').filter({ hasText: 'Pocket Lab Lite Server' }).first();
  await expect(serverCard).toBeVisible();
  await serverCard.getByRole('button', { name: /Details|Review health/i }).click();
  await expect(page.getByRole('region', { name: /Pocket Lab Lite Server details/i })).toBeVisible();
}

test('Home and Devices project the same canonical resource facts', async ({ page }) => {
  const failures = watchApiFailures(page);
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');

  const home = page.locator('[data-lite-screen-id="home"]');
  await expect(home).toContainText('2.0 GiB free / 4.0 GiB');
  await expect(home).toContainText('CPU 12%');
  await expect(home).toContainText('125.0 GiB free / 250.0 GiB');

  await openServerDetails(page);
  const details = page.getByRole('region', { name: /Pocket Lab Lite Server details/i });
  await expect(details).toContainText('2048 MB free / 4096 MB');
  await expect(details).toContainText('12%');
  await expect(details).toContainText('42 °C');
  await expect(details).toContainText('3 reported');
  expect(failures).toEqual([]);
});

test('partial and stale resource evidence stays explicit and accessible', async ({ page }) => {
  await installScenario(page, 'devices-resource-partial');
  await page.goto('/?screen=devices');
  await openServerDetails(page);
  const details = page.getByRole('region', { name: /Pocket Lab Lite Server details/i });
  await expect(details).toContainText('Unsupported');

  const result = await new AxeBuilder({ page })
    .include('[data-lite-screen-id="devices"]')
    .disableRules(['color-contrast'])
    .analyze();
  const blocking = result.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''));
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);

  await installScenario(page, 'devices-resource-stale');
  await page.reload();
  await openServerDetails(page);
  await expect(page.getByRole('region', { name: /Pocket Lab Lite Server details/i })).toContainText('Stale');
});

for (const [scenario, expected] of [
  ['devices-capability-pending', 'Verification pending'],
  ['devices-capability-stale', 'Stale'],
  ['devices-capability-unsupported', 'Unsupported'],
  ['devices-capability-missing', 'Not advertised'],
] as const) {
  test(`capability lifecycle preserves ${scenario.replace('devices-capability-', '')} evidence`, async ({ page }) => {
    await installScenario(page, scenario);
    await page.goto('/?screen=devices');
    await openServerDetails(page);
    const capabilityRegion = page.getByRole('region', { name: /Pocket Lab Lite Server details/i })
      .getByRole('region', { name: 'Device capabilities' });
    await expect(capabilityRegion).toContainText(expected);
  });
}
