import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// New baselines are deliberately not generated in the implementation-only stage.
// Capture/review in the separately authorized validation session.
for (const scenario of ['identity-summary', 'identity-enterprise-owner', 'identity-enterprise-admin', 'identity-premium-multiple', 'identity-premium-recovery-missing', 'identity-premium-long-text']) {
  for (const width of [390, 1440]) {
    test('premium identity visual reference ' + scenario + ' at ' + width, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await installScenario(page, scenario);
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page, 'identity');
      await expect(page.locator('[data-lite-screen-id="identity"]')).toHaveScreenshot('premium-identity-' + scenario + '-' + width + '.png', { animations: 'disabled' });
    });
  }
}
