import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Canonical screenshot references are owner-reviewed qualification artifacts.
// Keep this suite deterministic: mocked data, fixed viewports and reduced motion.
async function setup(page:Page, theme:'light'|'dark', width:number, scenario='catalog-ready') {
  await page.setViewportSize({width,height:width<=430?780:900});
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.addInitScript(pref=>localStorage.setItem('pocketlab:appearance',pref),theme);
  await installScenario(page,scenario);
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page,'catalog');
  await page.evaluate(() => document.fonts.ready);
}
async function manage(page:Page) {
  await page.locator('.lite-catalog-app-card').getByRole('button',{name:'Manage',exact:true}).first().click();
  const dialog=page.getByRole('dialog',{name:/Manage PhotoPrism/i});
  await expect(dialog).toBeVisible();
  return dialog;
}

for(const theme of ['light','dark'] as const) {
  for(const width of [320,360,390,430,768,1280]) {
    test('final Apps catalog '+theme+' '+width,async({page})=>{
      await setup(page,theme,width,'catalog-multi-app');
      await expect(page.locator('.lite-catalog-screen')).toHaveScreenshot('final-'+theme+'-catalog-'+width+'.png',{animations:'disabled'});
    });
    test('final Apps manage '+theme+' '+width,async({page})=>{
      await setup(page,theme,width);
      const panel=await manage(page);
      await expect(panel).toHaveScreenshot('final-'+theme+'-manage-'+width+'.png',{animations:'disabled'});
    });
  }
  for(const snap of ['compact','medium','expanded'] as const) {
    test('final mobile '+theme+' '+snap+' sheet',async({page})=>{
      await setup(page,theme,390);
      const panel=await manage(page);
      if(snap==='compact') await panel.getByRole('button',{name:'Compact',exact:true}).click();
      if(snap==='expanded') await panel.getByRole('button',{name:'Expand',exact:true}).click();
      await expect(panel).toHaveAttribute('data-lite-sheet-snap',snap);
      await expect(panel).toHaveScreenshot('final-'+theme+'-mobile-'+snap+'.png',{animations:'disabled'});
    });
  }
  test('final '+theme+' disclosure stack and nested Details',async({page})=>{
    await setup(page,theme,390);
    const panel=await manage(page);
    const storage=panel.locator('.lite-catalog-premium-storage-details');
    if(await storage.count()) await storage.locator('summary').click();
    const notices=panel.locator('.lite-catalog-premium-action-notices');
    if(await notices.count()) await notices.locator('summary').click();
    await expect(panel).toHaveScreenshot('final-'+theme+'-disclosures.png',{animations:'disabled'});
    const button=panel.getByRole('region',{name:'Photo workflow'}).getByRole('button',{name:'View details'});
    await button.click();
    const nested=page.locator('.lite-details-overlay-layer .lite-details-panel');
    await expect(nested).toBeVisible();
    await expect(nested).toHaveScreenshot('final-'+theme+'-nested-details.png',{animations:'disabled'});
  });
  for(const scenario of ['photo-backup-completed','photo-backup-remote-unavailable','offline-saved','app-action-failed']) {
    test('final '+theme+' scenario '+scenario,async({page})=>{
      await setup(page,theme,390,scenario);
      const panel=await manage(page);
      await expect(panel).toHaveScreenshot('final-'+theme+'-'+scenario+'.png',{animations:'disabled'});
    });
  }
}
