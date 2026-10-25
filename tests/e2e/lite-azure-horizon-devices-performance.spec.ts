import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
// Performance assertions here supplement, never replace, PR #588 hard gates.
test('many-device map and card rendering remains bounded in DOM footprint',async({page})=>{
  await installScenario(page,'devices-online');
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page,'devices');
  const count=await page.locator('.lite-device-relationship-node').count();
  const visible=await page.locator('.lite-device-card').count();
  expect(count).toBeLessThan(501);
  expect(visible).toBeLessThan(501);
});
test('Manage opens without redundant hidden detail mounts',async({page})=>{
  await installScenario(page,'devices-online');
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page,'devices');
  await expect(page.locator('.lite-device-details-focus-anchor')).toHaveCount(0);
  await page.getByRole('button',{name:/Manage /}).first().click();
  await expect(page.locator('.lite-device-details-focus-anchor')).toHaveCount(1);
});

/** Supplemental samples only. PR #588 remains the authoritative gate.
 * Do not add pass/fail timing thresholds until baseline ownership approves them.
 */
for (const appearance of ['light', 'dark'] as const) {
  for (const width of [390, 1440]) {
    test(`Devices interaction sample: ${appearance} ${width}px, first paint, map, Manage, theme`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), appearance);
      await installScenario(page, 'devices-online');
      const enteredAt = Date.now();
      await page.goto('/?screen=devices');
      await waitForLiteScreenToSettle(page, 'devices');
      const firstPaintDuration = Date.now() - enteredAt;
      const mapStart = Date.now();
      await expect(page.locator('.lite-device-relationship-map')).toBeVisible();
      const mapDuration = Date.now() - mapStart;
      const managedAt = Date.now();
      await page.getByRole('button', { name: /Manage Test-Phone-4/i }).first().click();
      const dialog = page.getByRole('dialog', { name: /Manage Test-Phone-4/i });
      await expect(dialog).toBeVisible();
      const manageDuration = Date.now() - managedAt;
      const closedAt = Date.now();
      await dialog.getByRole('button', { name: 'Close device details' }).click();
      await expect(dialog).toHaveCount(0);
      const closeDuration = Date.now() - closedAt;
      const measures = { firstPaintDuration, mapDuration, manageDuration, closeDuration };
      expect(Object.values(measures).every(value => Number.isFinite(value) && value >= 0)).toBe(true);
      test.info().annotations.push({ type: 'azure-devices-performance-sample', description: JSON.stringify(measures) });
    });
  }
}
