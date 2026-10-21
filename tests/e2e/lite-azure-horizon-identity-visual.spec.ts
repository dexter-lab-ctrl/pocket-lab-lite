import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
// DEFINED — BASELINE CAPTURE AND APPROVAL DEFERRED. Never use real recovery codes.
const scenarios = ['identity-summary','identity-premium-multiple','identity-premium-recovery-missing',
  'identity-premium-signed-out','identity-premium-first-owner','identity-premium-enrollment',
  'identity-owner-operation-pending','identity-owner-client-pairing-pending','identity-enterprise-owner',
  'identity-enterprise-admin','identity-enterprise-operator','identity-enterprise-auditor','identity-enterprise-viewer'];
for (const theme of ['light','dark'] as const) {
  for (const width of [320,360,375,390,430,768,1024,1440]) {
    test(`Identity ${theme} ${width}px account overview`,async({page})=>{
      await page.setViewportSize({width,height:900});
      await page.emulateMedia({reducedMotion:'reduce'});
      await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
      await installScenario(page,'identity-summary');
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page,'identity');
      await expect(page.locator('[data-identity-horizon="account"]')).toBeVisible();
      await expect(page.locator('[data-lite-screen-id="identity"]')).toHaveScreenshot(`identity-horizon-${theme}-${width}-overview.png`,{animations:'disabled'});
    });
  }
  for(const scenario of scenarios) {
    test(`Identity ${theme} ${scenario} state`,async({page})=>{
      await page.setViewportSize({width:390,height:844});
      await page.emulateMedia({reducedMotion:'reduce'});
      await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
      await installScenario(page,scenario);
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page,'identity');
      await expect(page.locator('[data-lite-screen-id="identity"]')).toHaveScreenshot(`identity-horizon-${theme}-${scenario}.png`,{animations:'disabled'});
    });
  }
  test(`Identity ${theme} Manage and confirmation panels`,async({page})=>{
    await page.setViewportSize({width:1280,height:900});
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
    await installScenario(page,'identity-summary');
    await page.goto('/?screen=identity');
    await waitForLiteScreenToSettle(page,'identity');
    await page.getByRole('button',{name:/^Manage Access$/i}).first().click();
    const dialog=page.getByRole('dialog',{name:/Manage access/i});
    await expect(dialog).toHaveScreenshot(`identity-horizon-${theme}-manage.png`,{animations:'disabled'});
    await dialog.getByRole('button',{name:'Recovery',exact:true}).click();
    await dialog.getByRole('button',{name:/Generate New Codes/i}).click();
    await expect(page.locator('[data-private-ephemeral-result]')).toHaveCount(0);
    await expect(page.getByRole('dialog',{name:/Generate new recovery codes/i})).toHaveScreenshot(`identity-horizon-${theme}-protected-confirmation.png`,{animations:'disabled'});
  });
}
