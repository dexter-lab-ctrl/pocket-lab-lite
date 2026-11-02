import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

/**
 * CANONICAL HOME VISUAL REFERENCES — reviewed and promoted after candidate
 * capture. Keep this suite in the normal qualification lane; snapshot update
 * is reserved for an explicitly reviewed visual change.
 */
async function setup(page: Page, theme: 'light' | 'dark', scenario: string, width: number) {
  await page.setViewportSize({width,height:width<500?800:900});
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.addInitScript((value)=>localStorage.setItem('pocketlab:appearance',value),theme);
  await installScenario(page,scenario);
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page,'home');
}
for (const theme of ['light','dark'] as const) {
  for (const width of [320,390,1280]) {
    test('Command Home '+theme+' '+width+'px reference candidate',async ({page})=>{
      await setup(page,theme,'healthy',width);
      await expect(page).toHaveScreenshot('home-command-'+theme+'-'+width+'.png',{animations:'disabled'});
    });
  }
  for (const scenario of ['lifecycle-attention','offline-saved'] as const) {
    test('Command Home '+theme+' '+scenario+' state reference candidate',async ({page})=>{
      await setup(page,theme,scenario,390);
      await expect(page).toHaveScreenshot('home-command-'+theme+'-'+scenario+'.png',{animations:'disabled'});
    });
  }
  for (const kind of ['workspace','activity'] as const) {
    for (const width of [390,1280]) {
      test('Command '+kind+' '+theme+' '+width+'px grouped detail candidate',async ({page})=>{
        await setup(page,theme,'healthy',width);
        await page.getByRole('button',{name:kind==='workspace'?'Workspace details':/View all activity/}).click();
        const title=kind==='workspace'?'Workspace details':'Recent activity';
        const dialog=page.getByRole('dialog',{name:title});
        await expect(dialog).toHaveScreenshot('home-command-'+kind+'-'+theme+'-'+width+'-index.png',
          {animations:'disabled'});
        await dialog.getByRole('button',{name:kind==='workspace'?'Service health':'History'}).click();
        await expect(dialog).toHaveScreenshot('home-command-'+kind+'-'+theme+'-'+width+'-nested.png',
          {animations:'disabled'});
      });
    }
  }
}
test('Command Home desktop resized panel candidate',async ({page})=>{
  await setup(page,'dark','healthy',1280);
  await page.getByRole('button',{name:'Workspace details'}).click();
  const dialog=page.getByRole('dialog',{name:'Workspace details'});
  await dialog.getByRole('button',{name:'Resize Workspace details panel'}).focus();
  for(let i=0;i<6;i++) await page.keyboard.press('ArrowLeft');
  await expect(dialog).toHaveScreenshot('home-command-dark-resized-panel.png',{animations:'disabled'});
});
