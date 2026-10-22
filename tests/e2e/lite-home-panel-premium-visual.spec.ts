import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// CANONICAL HOME PREMIUM BASELINES — PROMOTED AFTER FOCUSED REVIEW.
// Keep the snapshot suite in the normal qualification lane; update mode is
// reserved for an explicitly reviewed visual change.
const states = [
  { name: 'daylight', theme: 'light', scenario: 'healthy' },
  { name: 'black', theme: 'dark', scenario: 'healthy' },
  { name: 'attention', theme: 'dark', scenario: 'lifecycle-attention' },
  { name: 'saved', theme: 'light', scenario: 'offline-saved' },
  { name: 'unavailable', theme: 'dark', scenario: 'api-unavailable' },
] as const;
for (const state of states) for (const width of [390, 1440]) {
  for (const kind of ['workspace','activity'] as const) {
    test(`Home premium ${state.name} ${kind} ${width}px [CANONICAL BASELINE]`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 500 ? 844 : 960 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript((theme) => localStorage.setItem('pocketlab:appearance', theme), state.theme);
      await installScenario(page, state.scenario);
      await page.goto('/?screen=home');
      await waitForLiteScreenToSettle(page, 'home');
      await page.getByRole('button', { name: kind === 'workspace' ? 'Workspace details' : 'View activity' }).click();
      const dialog = page.getByRole('dialog', { name: kind === 'workspace' ? 'Workspace details' : 'Recent activity' });
      await expect(dialog).toHaveScreenshot(`home-premium-${state.name}-${kind}-${width}.png`, {
        animations: 'disabled', caret: 'hide', maxDiffPixelRatio: .02,
      });
    });
  }
}
