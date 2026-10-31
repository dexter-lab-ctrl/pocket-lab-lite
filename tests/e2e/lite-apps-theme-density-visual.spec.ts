import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORING ONLY: these names have NO approved PNG baselines.
// Qualification must render, review, and explicitly approve any new references.
async function setup(page: Page, theme: 'light' | 'dark' | 'system', width: number, scenario = 'catalog-ready') {
  await page.setViewportSize({ width, height: width <= 430 ? 780 : 900 });
  await page.emulateMedia({ colorScheme: theme === 'system' ? 'dark' : 'light', reducedMotion: 'reduce' });
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page, 'catalog');
  await page.evaluate(() => document.fonts.ready);
}
async function manage(page: Page) {
  await page.locator('.lite-catalog-app-card').first().getByRole('button', { name: 'Manage', exact: true }).click();
  const panel = page.getByRole('dialog', { name: /Manage / }).first();
  await expect(panel).toBeVisible();
  return panel;
}

for (const theme of ['light', 'dark', 'system'] as const) {
  for (const width of [320, 390, 768, 1280]) {
    test('Apps balanced density catalog ' + theme + ' ' + width, async ({ page }) => {
      await setup(page, theme, width, 'catalog-multi-app');
      await expect(page.locator('.lite-catalog-screen')).toHaveScreenshot(
        'apps-density-' + theme + '-catalog-' + width + '.png', { animations: 'disabled' },
      );
    });
    test('Apps balanced density Manage ' + theme + ' ' + width, async ({ page }) => {
      await setup(page, theme, width);
      const panel = await manage(page);
      await expect(panel).toHaveScreenshot(
        'apps-density-' + theme + '-manage-' + width + '.png', { animations: 'disabled' },
      );
    });
  }
}
for (const theme of ['light', 'dark'] as const) {
  for (const snap of ['compact', 'medium', 'expanded'] as const) {
    test('Apps density mobile ' + theme + ' ' + snap, async ({ page }) => {
      await setup(page, theme, 390);
      const panel = await manage(page);
      if (snap === 'compact') await panel.getByRole('button', { name: 'Compact', exact: true }).click();
      if (snap === 'expanded') await panel.getByRole('button', { name: 'Expand', exact: true }).click();
      await expect(panel).toHaveAttribute('data-lite-sheet-snap', snap);
      await expect(panel).toHaveScreenshot(
        'apps-density-' + theme + '-mobile-' + snap + '.png', { animations: 'disabled' },
      );
    });
  }
  test('Apps density nested Details and photo backup ' + theme, async ({ page }) => {
    await setup(page, theme, 390, 'photo-backup-completed');
    const panel = await manage(page);
    const photoTab = panel.getByRole('tab', { name: 'Photos', exact: true });
    if (await photoTab.count()) await photoTab.click();
    await expect(panel).toHaveScreenshot(
      'apps-density-' + theme + '-photo-backup.png', { animations: 'disabled' },
    );
    await panel.getByRole('region', { name: 'Photo workflow' })
      .getByRole('button', { name: 'View details' }).click();
    const nested = page.locator('.lite-details-overlay-layer .lite-details-panel');
    await expect(nested).toBeVisible();
    await expect(nested).toHaveScreenshot(
      'apps-density-' + theme + '-nested-details.png', { animations: 'disabled' },
    );
  });
  test('Apps density unavailable destination and failed action ' + theme, async ({ page }) => {
    for (const scenario of ['photo-backup-remote-unavailable', 'app-action-failed']) {
      await setup(page, theme, 390, scenario);
      const panel = await manage(page);
      await expect(panel).toHaveScreenshot(
        'apps-density-' + theme + '-' + scenario + '.png', { animations: 'disabled' },
      );
      await panel.getByRole('button', { name: 'Close app actions' }).click();
    }
  });
}
