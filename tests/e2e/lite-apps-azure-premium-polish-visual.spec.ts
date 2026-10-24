import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORED — NOT EXECUTED — UNVALIDATED. No *.png baselines generated or promoted.
// All reference images require separate human review and explicit authorization.
async function open(page:any, theme:'light'|'dark', scenario:string, width:number) {
  await page.setViewportSize({width,height:width<=390?780:900});
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.addInitScript((pref:string)=>localStorage.setItem('pocketlab:appearance',pref),theme);
  await installScenario(page,scenario);
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page,'catalog');
}
async function manage(page:any){
  await page.locator('.lite-catalog-app-card').getByRole('button',{name:'Manage',exact:true}).first().click();
  const dialog=page.getByRole('dialog',{name:/Manage PhotoPrism/i});
  await expect(dialog).toBeVisible();
  return dialog;
}
for(const theme of ['light','dark'] as const) {
  for(const width of [320,375,390,768,1280]) {
    test(`premium polish ${theme} catalog width ${width}`,async({page})=>{
      await open(page,theme,'catalog-multi-app',width);
      await expect(page.locator('.lite-catalog-screen')).toHaveScreenshot(`premium-${theme}-catalog-${width}.png`,{animations:'disabled'});
    });
    test(`premium polish ${theme} Manage width ${width}`,async({page})=>{
      await open(page,theme,'catalog-ready',width);
      const dialog=await manage(page);
      await expect(dialog).toHaveScreenshot(`premium-${theme}-manage-${width}.png`,{animations:'disabled'});
    });
  }
  for(const scenario of ['photo-backup-completed','photo-backup-remote-unavailable','photo-backup-malformed','offline-saved']) {
    test(`premium ${theme} photo state ${scenario}`,async({page})=>{
      await open(page,theme,scenario,390);
      const dialog=await manage(page);
      const photos=dialog.getByRole('tab',{name:'Photos'});
      if(await photos.count()) await photos.click();
      await expect(dialog).toHaveScreenshot(`premium-${theme}-${scenario}.png`,{animations:'disabled'});
    });
  }
  test(`premium ${theme} Action Details and disclosure expansion`,async({page})=>{
    await open(page,theme,'catalog-ready',1280);
    const dialog=await manage(page);
    await dialog.getByRole('tab',{name:'Photos'}).click();
    const storage=dialog.locator('.lite-catalog-premium-storage-details');
    await storage.locator('summary').click();
    const how=dialog.getByRole('region',{name:'Photo backup'}).locator('details');
    await how.locator('summary').click();
    await expect(dialog).toHaveScreenshot(`premium-${theme}-storage-how-open.png`,{animations:'disabled'});
    await dialog.getByRole('region',{name:'Photo workflow'}).getByRole('button',{name:'View details'}).click();
    await expect(page.locator('.lite-details-overlay-layer .lite-details-panel')).toHaveScreenshot(`premium-${theme}-nested-details.png`,{animations:'disabled'});
  });
  test(`premium ${theme} desktop resized/moved Manage`,async({page})=>{
    await open(page,theme,'catalog-ready',1440);
    const panel=await manage(page);
    const move=panel.getByRole('button',{name:'Move app management panel'});
    await move.focus();await page.keyboard.press('Shift+ArrowLeft');
    const resize=panel.getByRole('button',{name:'Resize app management panel'});
    await resize.focus();await page.keyboard.press('Shift+ArrowDown');
    await expect(panel).toHaveScreenshot(`premium-${theme}-desktop-moved-resized.png`,{animations:'disabled'});
  });
  test(`premium ${theme} 200% zoom and long name safeguard`,async({page})=>{
    await open(page,theme,'catalog-multi-app',390);
    await page.evaluate(()=>{document.documentElement.style.fontSize='200%';});
    await expect(page.locator('.lite-catalog-screen')).toHaveScreenshot(`premium-${theme}-zoom200-longname.png`,{animations:'disabled'});
  });
}
