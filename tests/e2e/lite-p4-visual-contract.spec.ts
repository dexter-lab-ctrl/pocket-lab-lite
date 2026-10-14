import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// New baselines deliberately require a human-reviewed first approval.
// Never use --update-snapshots as part of a default validation task.
const cases = [
  { screen: 'home', scenario: 'lifecycle-attention', region: 'Needs your attention', name: 'home-attention' },
  { screen: 'devices', scenario: 'devices-repairing', region: 'Connection review', name: 'devices-connection' },
  { screen: 'catalog', scenario: 'catalog-install-available', region: 'App readiness', name: 'apps-readiness' },
  { screen: 'security', scenario: 'security-action-needed', region: 'Safety result and coverage', name: 'safety-evidence' },
  { screen: 'identity', scenario: 'healthy', region: 'Access profile', name: 'access-evidence' },
  { screen: 'rules', scenario: 'rules-disabled', region: 'How protection decisions work', name: 'rules-evidence' },
  { screen: 'recovery', scenario: 'recovery-restore-blocked', region: 'Protection readiness', name: 'recovery-guidance' },
] as const;
for (const item of cases) {
  test(`P4 visual: ${item.name} guidance contract`, async ({ page }) => {
    await installScenario(page, item.scenario);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(`/?screen=${item.screen}`);
    await waitForLiteScreenToSettle(page, item.screen);
    const guidance = page.locator(`[data-lite-screen-id="${item.screen}"]`).getByRole('region', { name: item.region });
    await expect(guidance).toBeVisible();
    await expect(guidance).toHaveScreenshot(`${item.name}.png`, { animations: 'disabled', caret: 'hide', maxDiffPixelRatio: 0.02 });
  });
}
test('P4 visual: keyboard navigation overlay on mobile and desktop', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await page.getByRole('button', { name: 'Find a Pocket Lab section' }).click();
  const modal = page.getByRole('dialog', { name: 'Go to a section' });
  await expect(modal).toBeVisible();
  await expect(modal).toHaveScreenshot('quick-find-open.png', { animations: 'disabled', caret: 'hide', maxDiffPixelRatio: 0.02 });
});
