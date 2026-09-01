import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

test('Devices progressive connection flow remains visually intentional', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');

  const devices = page.locator('[data-lite-screen-id="devices"]');
  await expect(devices).toHaveScreenshot('devices-progressive-flow.png', {
    animations: 'disabled',
    caret: 'hide',
    maxDiffPixelRatio: 0.02,
  });
});
