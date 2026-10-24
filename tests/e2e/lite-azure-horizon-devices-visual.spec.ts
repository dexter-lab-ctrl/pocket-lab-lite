import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// DEFINED — CAPTURE AND APPROVAL DEFERRED. Do not auto-approve baselines.
for (const theme of ['light','dark'] as const) {
  for (const width of [320,360,375,390,430,768,1024,1440]) {
    for (const scenario of ['devices-online','devices-offline','devices-repairing','devices-remote-not-ready','devices-invite-ready']) {
      test(`Azure Devices ${theme} ${width} ${scenario} screenshot reference`,async({page})=>{
        await page.setViewportSize({width,height:width<500?844:900});
        await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
        await installScenario(page,scenario);
        await page.goto('/?screen=devices');
        await waitForLiteScreenToSettle(page,'devices');
        await expect(page.locator('.lite-device-relationship-map')).toHaveScreenshot(`devices-${theme}-${width}-${scenario}.png`,{animations:'disabled'});
      });
    }
  }
}


/** DEFINED — CAPTURE AND APPROVAL DEFERRED.
 * Private bootstrap commands must never appear unmasked in screenshot artifacts.
 */
for (const theme of ['light', 'dark'] as const) {
  for (const width of [320, 390, 768, 1440]) {
    test(`Azure Devices ${theme} ${width}px Manage visual reference`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'devices-online');
      await page.goto('/?screen=devices');
      await waitForLiteScreenToSettle(page, 'devices');
      await page.getByRole('button', { name: /Manage Test-Phone-4/i }).first().click();
      const dialog = page.getByRole('dialog', { name: /Manage Test-Phone-4/i });
      await expect(dialog).toBeVisible();
      await expect(dialog).toHaveScreenshot(`devices-${theme}-manage-${width}.png`, { animations: 'disabled' });
    });
    test(`Azure Devices ${theme} ${width}px Add Device guidance reference`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'devices-online');
      await page.goto('/?screen=devices');
      await waitForLiteScreenToSettle(page, 'devices');
      await page.getByRole('button', { name: 'Add Device', exact: true }).first().click();
      await expect(page.locator('#lite-devices-onboarding')).toHaveAttribute('open', '');
      await expect(page.locator('#lite-devices-onboarding')).toHaveScreenshot(
        `devices-${theme}-onboarding-${width}.png`, {
          animations: 'disabled',
          mask: [page.locator('.lite-invite-command code')],
        },
      );
    });
  }
}
