import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// CANONICAL AZURE HORIZON BASELINES — PROMOTED AFTER REVIEW.
// Captures were reviewed in the authorized stabilization session.
// Do not run --update-snapshots in the default aggregate qualification lane.
const variants = [
  { name: 'daylight-mobile', theme: 'light', width: 390, scenario: 'healthy' },
  { name: 'black-mobile', theme: 'dark', width: 390, scenario: 'healthy' },
  { name: 'daylight-desktop', theme: 'light', width: 1440, scenario: 'healthy' },
  { name: 'black-desktop', theme: 'dark', width: 1440, scenario: 'healthy' },
  { name: 'black-attention-mobile', theme: 'dark', width: 360, scenario: 'lifecycle-attention' },
  { name: 'daylight-saved-desktop', theme: 'light', width: 1440, scenario: 'offline-saved' },
  { name: 'black-unavailable-mobile', theme: 'dark', width: 430, scenario: 'api-unavailable' },
] as const;
for (const variant of variants) {
  test(`Azure visual: ${variant.name} [CANONICAL BASELINE]`, async ({ page }) => {
    await page.setViewportSize({ width: variant.width, height: variant.width < 500 ? 844 : 960 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.addInitScript((p) => localStorage.setItem('pocketlab:appearance', p), variant.theme);
    await installScenario(page, variant.scenario);
    await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page, 'home');
    await expect(page.locator('[data-azure-horizon-home]')).toHaveScreenshot(`${variant.name}.png`, {
      animations: 'disabled', caret: 'hide', maxDiffPixelRatio: 0.02,
    });
  });
}
for (const theme of ['light','dark'] as const) {
  for (const [area, buttonName, dialogName] of [
    ['workspace', 'Workspace details', 'Workspace details'],
    ['activity', 'View activity', 'Recent activity'],
  ]) {
    test(`Azure visual: ${theme} ${area} details [CANONICAL BASELINE]`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript((p) => localStorage.setItem('pocketlab:appearance', p), theme);
      await installScenario(page, 'healthy');
      await page.goto('/?screen=home');
      await waitForLiteScreenToSettle(page, 'home');
      await page.getByRole('button', { name: buttonName }).click();
      await expect(page.getByRole('dialog', { name: dialogName })).toHaveScreenshot(
        `azure-${theme}-${area}-details.png`, { animations: 'disabled', caret: 'hide', maxDiffPixelRatio: 0.02 },
      );
    });
  }
}
