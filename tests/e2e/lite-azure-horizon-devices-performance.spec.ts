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
