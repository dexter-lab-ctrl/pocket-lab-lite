import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function waitForAzureDevicesStyles(page: Parameters<typeof installScenario>[0]) {
  await page.waitForFunction(() => Array.from(document.styleSheets).some((sheet) => {
    try {
      return Array.from(sheet.cssRules).some((rule) => rule.cssText.includes('html[data-lite-theme] .lite-device-details-panel'));
    } catch (_error) {
      return false;
    }
  }));
}

async function waitForDeviceActionStyles(page: Parameters<typeof installScenario>[0]) {
  await page.waitForFunction(() => {
    const anchor = document.querySelector('.lite-device-details-focus-anchor');
    if (!anchor) return false;
    const style = getComputedStyle(anchor);
    return style.position === 'fixed' && style.overflow === 'auto';
  });
}

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
      await waitForAzureDevicesStyles(page);
      await page.getByRole('button', { name: /Manage Test-Phone-4/i }).first().click();
      const dialog = page.getByRole('dialog', { name: /Manage Test-Phone-4/i });
      await expect(dialog).toBeVisible();
      await waitForDeviceActionStyles(page);
      await expect(dialog.locator('.lite-device-details-panel.is-ready')).toBeVisible();
      await expect(dialog).toHaveScreenshot(`devices-${theme}-manage-${width}.png`, { animations: 'disabled' });
    });
    test(`Azure Devices ${theme} ${width}px Add Device guidance reference`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'devices-online');
      await page.goto('/?screen=devices');
      await waitForLiteScreenToSettle(page, 'devices');
      await waitForAzureDevicesStyles(page);
      await page.getByRole('button', { name: 'Add Device', exact: true }).first().click();
      await expect(page.locator('#lite-devices-onboarding')).toHaveAttribute('open', '');
      // The lazy Devices stylesheet can arrive after the screen has become
      // visible. Wait for its semantic surface rule before capturing so the
      // reference cannot record the pre-stylesheet fallback.
      await page.waitForFunction((expectedBackground) => {
        const card = document.querySelector('#lite-devices-onboarding .lite-devices-add-card');
        if (!card) return false;
        const style = getComputedStyle(card);
        return style.backgroundColor === expectedBackground && style.borderRadius === '20px';
      }, theme === 'light' ? 'rgb(255, 255, 255)' : 'rgb(11, 15, 20)');
      // The fixed shell navigation is outside this element-level reference.
      // Hide it on narrow captures so scrollIntoView does not race its fixed
      // layer into the onboarding baseline at different scroll offsets.
      if (width < 1024) {
        await page.addStyleTag({ content: '.pocket-nav-dock { visibility: hidden !important; }' });
      }
      const onboarding = page.locator('#lite-devices-onboarding');
      const screenshot = await onboarding.screenshot({
        animations: 'disabled',
        mask: [page.locator('.lite-invite-command code')],
        scale: 'css',
      });
      await expect(screenshot).toMatchSnapshot(`devices-${theme}-onboarding-${width}.png`);
    });
  }
}
