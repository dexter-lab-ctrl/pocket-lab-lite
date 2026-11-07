import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Canonical snapshots are reviewed qualification artifacts. The narrow mobile
// light/system-theme tolerances below cover Chromium text rasterization
// variance only; the screenshot assertions still compare the complete surface.
for (const theme of ['light', 'dark', 'system'] as const) {
  for (const width of [320, 360, 390, 430, 768, 1024, 1440]) {
    test('Access Center ' + theme + ' ' + width + 'px overview', async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'identity-summary');
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page, 'identity');
      const screenshotOptions = test.info().project.name === 'mocked-mobile'
        ? { animations: 'disabled' as const, maxDiffPixels: 500 }
        : { animations: 'disabled' as const };
      await expect(page.locator('[data-identity-horizon="account"]')).toHaveScreenshot('access-native-' + theme + '-' + width + '.png', screenshotOptions);
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
      const screenshotOptions = test.info().project.name === 'mocked-mobile'
        ? { animations: 'disabled' as const, maxDiffPixels: 500 }
        : { animations: 'disabled' as const };
      await expect(page.locator('[data-lite-screen-id="identity"]')).toHaveScreenshot('access-native-' + theme + '-' + scenario + '.png', screenshotOptions);
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
      const screenshotOptions = test.info().project.name === 'mocked-mobile' && theme !== 'dark'
        ? { animations: 'disabled' as const, maxDiffPixels: 500 }
        : { animations: 'disabled' as const };
      await expect(dialog).toHaveScreenshot('access-native-' + theme + '-manage-' + section + '.png', screenshotOptions);
    });
  }
  for (const width of [768, 1024, 1440]) {
    test('Access Manage desktop ' + theme + ' ' + width + 'px geometry', async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'identity-premium-multiple');
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page, 'identity');
      await page.getByRole('button', { name: 'Manage Access' }).click();
      const dialog = page.getByRole('dialog', { name: /Manage access/i });
      const screenshotOptions = test.info().project.name === 'mocked-mobile' && theme !== 'dark'
        ? { animations: 'disabled' as const, maxDiffPixels: 1500 }
        : { animations: 'disabled' as const };
      await expect(dialog).toHaveScreenshot('access-native-' + theme + '-manage-desktop-index-' + width + '.png', screenshotOptions);
      await dialog.getByRole('button', { name: 'Sessions', exact: true }).click();
      await expect(dialog).toHaveScreenshot('access-native-' + theme + '-manage-desktop-sessions-' + width + '.png', screenshotOptions);
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
  test('Access nested session details and protected confirmation ' + theme, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
    await installScenario(page, 'identity-premium-multiple');
    await page.goto('/?screen=identity');
    await waitForLiteScreenToSettle(page, 'identity');
    await page.getByRole('button', { name: 'Manage Access' }).click();
    const manage = page.getByRole('dialog', { name: /Manage access/i });
    await manage.getByRole('button', { name: 'Sessions', exact: true }).click();
    await manage.getByRole('button', { name: /^Other session/i }).first().click();
    const detail = page.getByRole('dialog', { name: /Access Details/i });
    await expect(detail).toHaveScreenshot('access-native-' + theme + '-nested-details.png', { animations: 'disabled' });
    await detail.getByRole('button', { name: 'Sign out session' }).click();
    const confirmation = page.getByRole('dialog', { name: /Sign out this session/i });
    const screenshotOptions = test.info().project.name === 'mocked-mobile' && theme !== 'dark'
      ? { animations: 'disabled' as const, maxDiffPixels: 500 }
      : { animations: 'disabled' as const };
    await expect(confirmation).toHaveScreenshot('access-native-' + theme + '-protected-confirmation.png', screenshotOptions);
  });
}
