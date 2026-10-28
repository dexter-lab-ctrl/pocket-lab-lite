import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// DEFINED — NOT RUN. Snapshot baselines do NOT exist until approved in stabilization.
// Use only MSW fixtures. Never trigger a real Security scan or backend write.
async function showSafety(page: Page, theme: 'light'|'dark'|'system', scenario: string, width: number) {
  await page.setViewportSize({ width, height: width < 701 ? 844 : 900 });
  await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
}
for (const theme of ['light', 'dark', 'system'] as const) {
  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1440]) {
    test(`Safety hero and overview: ${theme} / ${width}px`, async ({ page }) => {
      await showSafety(page, theme, 'security-quick-healthy', width);
      await expect(page.locator('[data-security-phase5-summary-first="true"]')).toHaveScreenshot(
        `safety-azure-${theme}-overview-${width}.png`, { animations: 'disabled' });
      await expect(page.locator('[data-security-horizon-overview="true"]')).toHaveScreenshot(
        `safety-azure-${theme}-insights-${width}.png`, { animations: 'disabled' });
    });
  }
  for (const scenario of [
    'security-quick-healthy', 'security-action-needed', 'security-urgent',
    'security-first-run', 'security-profile-stale', 'security-scanner-unavailable',
    'security-full-running', 'security-app-check-healthy', 'security-unsupported-app-route',
    'offline-saved',
  ]) {
    test(`Safety backend-state variants: ${theme} / ${scenario}`, async ({ page }) => {
      await showSafety(page, theme, scenario, 1280);
      await expect(page.locator('[data-lite-screen-id="security"]')).toHaveScreenshot(
        `safety-azure-${theme}-state-${scenario}.png`, { animations: 'disabled' });
    });
  }
  for (const width of [390, 768, 1280]) {
    for (const section of [
      'Overview', 'Checks', 'Changes', 'Issues', 'Coverage',
      'Check path', 'Evidence', 'History', 'Technical details',
    ]) {
      test(`Safety Manage: ${theme} / ${width}px / ${section}`, async ({ page }) => {
        await showSafety(page, theme, 'security-quick-healthy', width);
        await page.getByRole('button', { name: 'Manage Security details' }).click();
        const dialog = page.getByRole('dialog', { name: 'Manage Safety' });
        await dialog.getByRole('tab', { name: `Open ${section} in Security Manage` }).click();
        await expect(dialog).toHaveScreenshot(
          `safety-azure-${theme}-manage-${width}-${section.toLowerCase().replaceAll(' ', '-')}.png`,
          { animations: 'disabled' });
      });
    }
  }
}
test('Safety protected Full Scan confirmation — synthetic only', async ({ page }) => {
  await showSafety(page, 'dark', 'security-quick-healthy', 1280);
  await page.getByRole('button', { name: 'Run Full Scan' }).click();
  const dialog = page.getByRole('dialog', { name: 'Full Local Check' });
  await expect(dialog).toHaveScreenshot('safety-azure-full-confirmation.png', { animations: 'disabled' });
  await dialog.getByRole('button', { name: 'Cancel' }).click();
});
test('Safety protected App Scan confirmation — synthetic only', async ({ page }) => {
  await showSafety(page, 'light', 'security-quick-healthy', 390);
  await page.getByRole('button', { name: 'Run App Scan' }).click();
  const dialog = page.getByRole('dialog', { name: 'Check PhotoPrism' });
  await expect(dialog).toHaveScreenshot('safety-azure-app-confirmation.png', { animations: 'disabled' });
  await dialog.getByRole('button', { name: 'Cancel' }).click();
});
test('desktop shared geometry after keyboard move and resize', async ({ page }) => {
  await showSafety(page, 'dark', 'security-quick-healthy', 1280);
  await page.getByRole('button', { name: 'Manage Security details' }).click();
  const dialog = page.getByRole('dialog', { name: 'Manage Safety' });
  await dialog.getByRole('button', { name: 'Move Safety panel' }).focus();
  await page.keyboard.press('ArrowLeft');
  await dialog.getByRole('button', { name: 'Resize Safety panel' }).focus();
  await page.keyboard.press('ArrowDown');
  await expect(dialog).toHaveScreenshot('safety-azure-desktop-moved-resized.png', { animations: 'disabled' });
});
test('320px with 200% text and reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await showSafety(page, 'dark', 'security-action-needed', 320);
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
  await expect(page.locator('[data-lite-screen-id="security"]')).toHaveScreenshot(
    'safety-azure-320-zoom200-reduced-motion.png', { animations: 'disabled' });
});
