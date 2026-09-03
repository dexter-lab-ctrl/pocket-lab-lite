import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

const STATE_CASES = [
  ['home-attention', 'home', 'lifecycle-attention'],
  ['home-saved-offline', 'home', 'offline-saved'],
  ['apps-install-available', 'catalog', 'catalog-install-available'],
  ['apps-installing', 'catalog', 'catalog-installing'],
  ['apps-action-failed', 'catalog', 'app-action-failed'],
  ['devices-repairing', 'devices', 'devices-repairing'],
  ['devices-agent-stopped', 'devices', 'devices-agent-stopped'],
  ['devices-invite-ready', 'devices', 'devices-invite-ready'],
  ['devices-remote-access-not-ready', 'devices', 'devices-remote-not-ready'],
  ['security-action-needed', 'security', 'security-action-needed'],
  ['security-urgent', 'security', 'security-urgent'],
  ['security-running', 'security', 'security-full-running'],
  ['identity-password-change-required', 'identity', 'identity-password-change-required'],
  ['rules-disabled', 'rules', 'rules-disabled'],
  ['rules-validation-error', 'rules', 'rules-validation-error'],
  ['recovery-backup-running', 'recovery', 'recovery-backup-running'],
  ['recovery-backup-verified', 'recovery', 'recovery-verified'],
  ['recovery-preview-ready', 'recovery', 'recovery-preview-ready'],
  ['recovery-checkpoint-ready', 'recovery', 'recovery-checkpoint-ready'],
  ['recovery-restore-blocked', 'recovery', 'recovery-restore-blocked'],
] as const;

for (const [name, screenId, scenario] of STATE_CASES) {
  test(`${name} critical visual state remains intentional`, async ({ page }) => {
    await installScenario(page, scenario);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(`/?screen=${screenId}`);
    await waitForLiteScreenToSettle(page, screenId);

    const screen = page.locator(`[data-lite-screen-id="${screenId}"]`);
    await expect(screen).toBeVisible();
    await expect(screen).toHaveScreenshot(`${name}.png`, {
      animations: 'disabled',
      caret: 'hide',
      maxDiffPixelRatio: 0.02,
    });
  });
}

test('devices-add-device-open disclosure remains visually stable', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');

  const devices = page.locator('[data-lite-screen-id="devices"]');
  const disclosure = devices.locator('details.lite-devices-add-disclosure');
  await expect(disclosure).toBeVisible();
  await disclosure.locator('summary').click();
  await expect(disclosure).toHaveAttribute('open', '');
  await expect(devices.getByLabel('Device name')).toBeVisible();

  await expect(disclosure).toHaveScreenshot('devices-add-device-open.png', {
    animations: 'disabled',
    caret: 'hide',
    maxDiffPixelRatio: 0.02,
  });
});
