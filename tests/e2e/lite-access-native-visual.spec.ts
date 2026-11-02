import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORED CANDIDATES ONLY. No screenshots or canonical baselines generated in this session.
// Qualification must review and explicitly approve new baselines before comparison is authoritative.
for (const theme of ['light', 'dark', 'system'] as const) {
  for (const width of [320, 360, 390, 430, 768, 1024, 1440]) {
    test('Access Center ' + theme + ' ' + width + 'px overview', async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'identity-summary');
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page, 'identity');
      await expect(page.locator('[data-identity-horizon="account"]')).toHaveScreenshot('access-native-' + theme + '-' + width + '.png', { animations: 'disabled' });
    });
  }
  for (const scenario of ['identity-premium-multiple','identity-premium-recovery-missing','identity-premium-no-passkeys',
    'identity-premium-signed-out','identity-owner-operation-pending','identity-enterprise-owner',
    'identity-enterprise-admin','identity-enterprise-viewer','identity-owner-operation-offline']) {
    test('Access Center ' + theme + ' ' + scenario, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, scenario);
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page, 'identity');
      await expect(page.locator('[data-lite-screen-id="identity"]')).toHaveScreenshot('access-native-' + theme + '-' + scenario + '.png', { animations: 'disabled' });
    });
  }
  for (const section of ['index','passkeys','sessions','recovery','activity','settings']) {
    test('Access Manage ' + theme + ' ' + section + ' navigation', async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'identity-premium-multiple');
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page, 'identity');
      await page.getByRole('button', { name: 'Manage Access' }).click();
      const dialog = page.getByRole('dialog', { name: /Manage access/i });
      if (section !== 'index') await dialog.getByRole('button', { name: ({ activity: 'Access activity', settings: 'Access settings' } as Record<string,string>)[section] || section[0].toUpperCase() + section.slice(1) }).click();
      await expect(dialog).toHaveScreenshot('access-native-' + theme + '-manage-' + section + '.png', { animations: 'disabled' });
    });
  }
  for (const state of ['compact','medium','expanded']) {
    test('Access mobile snap ' + theme + ' ' + state, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'identity-summary');
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page, 'identity');
      await page.getByRole('button', { name: 'Manage Access' }).click();
      const dialog = page.getByRole('dialog', { name: /Manage access/i });
      await dialog.getByRole('button', { name: /Resize sheet, currently/ }).focus();
      if (state === 'compact') await page.keyboard.press('Home');
      if (state === 'expanded') await page.keyboard.press('End');
      await expect(dialog).toHaveAttribute('data-lite-sheet-snap', state);
      await expect(dialog).toHaveScreenshot('access-native-' + theme + '-snap-' + state + '.png', { animations: 'disabled' });
    });
  }
}
