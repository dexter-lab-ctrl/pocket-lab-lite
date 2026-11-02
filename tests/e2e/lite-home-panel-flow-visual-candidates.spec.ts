import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// UNAPPROVED P0/P1 native grouped settings visual candidates. No screenshots
// generated or evaluated in this implementation-only session. Do not
// overwrite existing canonical PNGs without later explicit human approval.
test.skip(process.env.LITE_HOME_VISUAL_CANDIDATES !== '1',
  'Source authored; enable only in a separately authorized baseline-review session.');
const cases = [
  { name:'ready', scenario:'healthy', theme:'light' },
  { name:'black', scenario:'healthy', theme:'dark' },
  { name:'review', scenario:'lifecycle-attention', theme:'dark' },
  { name:'saved', scenario:'offline-saved', theme:'dark' },
  { name:'unavailable', scenario:'api-unavailable', theme:'dark' },
] as const;
for(const kind of ['workspace','activity'] as const) {
  for(const item of cases) for(const width of [320,390,1440]) {
    test(kind+' '+item.name+' '+width+'px grouped navigation candidate',async ({page})=>{
      await page.setViewportSize({width,height:width<500?780:900});
      await page.emulateMedia({reducedMotion:'reduce'});
      await page.addInitScript((value)=>localStorage.setItem('pocketlab:appearance',value),item.theme);
      await installScenario(page,item.scenario);
      await page.goto('/?screen=home');
      await waitForLiteScreenToSettle(page,'home');
      await page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View all activity'}).click();
      const dialog=page.getByRole('dialog',{name:kind==='workspace'?'Workspace details':'Recent activity'});
      await expect(dialog).toHaveScreenshot('home-command-'+kind+'-'+item.name+'-'+width+'-index.png',{
        animations:'disabled',caret:'hide',maxDiffPixelRatio:.02,
      });
      await dialog.getByRole('button',{name:kind==='workspace'?'Service health':'History'}).click();
      await expect(dialog).toHaveScreenshot('home-command-'+kind+'-'+item.name+'-'+width+'-detail.png',{
        animations:'disabled',caret:'hide',maxDiffPixelRatio:.02,
      });
    });
  }
}
for(const kind of ['workspace','activity'] as const) {
  test(kind+' native long-scroll nested detail reference candidate',async ({page})=>{
    await page.setViewportSize({width:390,height:780});
    await page.addInitScript(()=>localStorage.setItem('pocketlab:appearance','dark'));
    await installScenario(page,'healthy');
    await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page,'home');
    await page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View all activity'}).click();
    const dialog=page.getByRole('dialog',{name:kind==='workspace'?'Workspace details':'Recent activity'});
    await dialog.getByRole('button',{name:kind==='workspace'?'Service health':'History'}).click();
    const scroll=dialog.locator('.lite-home-panel-scroll');
    await scroll.evaluate((node)=>{
      const filler=document.createElement('div');
      filler.style.height='1400px';filler.setAttribute('aria-hidden','true');
      node.append(filler);node.scrollTo({top:220,behavior:'instant'});
    });
    await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
    await expect(dialog).toHaveScreenshot('home-command-'+kind+'-nested-scroll.png',{
      animations:'disabled',caret:'hide',maxDiffPixelRatio:.02,
    });
  });
}
