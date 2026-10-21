import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// DEFINED — CAPTURE AND HUMAN REVIEW DEFERRED.
// These intentionally have no new approved *.png snapshot baselines.
for (const theme of ['light','dark'] as const) {
  for (const width of [320,390,768,1280]) {
    test(`Azure Apps ${theme} ${width}px catalog reference`,async({page})=>{
      await page.setViewportSize({width,height:width<=390?800:900});
      await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
      await installScenario(page,'catalog-multi-app');
      await page.goto('/?screen=catalog');
      await waitForLiteScreenToSettle(page,'catalog');
      await expect(page.locator('.lite-catalog-screen')).toHaveScreenshot(`apps-${theme}-catalog-${width}.png`,{animations:'disabled'});
    });
    test(`Azure Apps ${theme} ${width}px Manage reference`,async({page})=>{
      await page.setViewportSize({width,height:width<=390?800:900});
      await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
      await installScenario(page,'catalog-ready');
      await page.goto('/?screen=catalog');
      await waitForLiteScreenToSettle(page,'catalog');
      await page.locator('.lite-catalog-app-card').getByRole('button',{name:'Manage'}).first().click();
      const manage=page.getByRole('dialog',{name:/Manage PhotoPrism/i});
      await expect(manage).toBeVisible();
      await expect(manage).toHaveScreenshot(`apps-${theme}-manage-${width}.png`,{animations:'disabled'});
    });
  }
}
