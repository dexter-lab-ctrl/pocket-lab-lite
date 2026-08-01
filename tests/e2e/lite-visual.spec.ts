import { expect, test } from '@playwright/test';
import { installScenario, LITE_TABS, openTab, waitForLiteScreenToSettle } from './lite-test-helpers';

test('canonical Lite tab screenshots remain stable', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?screen=home');
  for (const [label, screenId] of LITE_TABS) {
    await openTab(page, label, screenId);
    await waitForLiteScreenToSettle(page, screenId);
    await expect(page.locator(`[data-lite-screen-id="${screenId}"]`)).toHaveScreenshot(`${screenId}.png`, {
      animations: 'disabled',
      caret: 'hide',
      maxDiffPixelRatio: 0.02,
    });
  }
});
