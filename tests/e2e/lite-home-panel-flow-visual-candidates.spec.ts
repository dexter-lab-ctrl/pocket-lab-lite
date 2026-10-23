import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// UNAPPROVED candidate cases. Existing 40 canonical PNGs must NOT be replaced
// without an explicit human review in a later qualification session.
test.skip(process.env.LITE_HOME_VISUAL_CANDIDATES !== '1',
  'Source authored; only enable with LITE_HOME_VISUAL_CANDIDATES=1 during baseline review.');
const cases = [
  { name:'ready', scenario:'healthy', theme:'light' },
  { name:'black', scenario:'healthy', theme:'dark' },
  { name:'review', scenario:'lifecycle-attention', theme:'dark' },
  { name:'saved', scenario:'offline-saved', theme:'dark' },
  { name:'unavailable', scenario:'api-unavailable', theme:'dark' },
] as const;
for (const kind of ['workspace', 'activity'] as const) {
  for (const item of cases) for (const width of [320, 390, 1440]) {
    test(`${kind}: ${item.name} ${width}px candidate, Daylight/Black card and text geometry`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 500 ? 780 : 900 });
      await page.emulateMedia({ reducedMotion:'reduce' });
      await page.addInitScript((theme) => localStorage.setItem('pocketlab:appearance', theme), item.theme);
      await installScenario(page, item.scenario);
      await page.goto('/?screen=home');
      await waitForLiteScreenToSettle(page, 'home');
      await page.getByRole('button', { name: kind === 'workspace' ? 'Workspace details' : 'View activity' }).click();
      const dialog = page.getByRole('dialog', { name: kind === 'workspace' ? 'Workspace details' : 'Recent activity' });
      if (kind === 'workspace') await dialog.getByRole('button', { name:'Service health' }).click();
      await expect(dialog).toHaveScreenshot(`home-flow-${kind}-${item.name}-${width}.png`, {
        animations:'disabled', caret:'hide', maxDiffPixelRatio:.02,
      });
    });
  }
}
for (const kind of ['workspace','activity'] as const) {
  for (const hidden of [false,true]) {
    test(`${kind}: scroll strip ${hidden?'retracted':'visible'} candidate`,async({page})=>{
      await page.setViewportSize({width:390,height:780});
      await page.addInitScript(()=>localStorage.setItem('pocketlab:appearance','dark'));
      await installScenario(page,'healthy');
      await page.goto('/?screen=home');
      await waitForLiteScreenToSettle(page,'home');
      await page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View activity'}).click();
      const dialog=page.getByRole('dialog',{name:kind==='workspace'?'Workspace details':'Recent activity'});
      const scroll=dialog.locator('.lite-home-panel-scroll');
      if(hidden){
        await scroll.evaluate((node)=>{
          const filler=document.createElement('div');filler.style.height='1400px';filler.setAttribute('aria-hidden','true');
          node.append(filler);node.scrollTo({top:220,behavior:'instant'});
        });
        await expect(dialog.locator('.lite-home-details-nav')).toHaveAttribute('data-tabs-hidden','true');
      }
      await expect(dialog).toHaveScreenshot(`home-flow-${kind}-navigation-${hidden?'hidden':'visible'}.png`,{
        animations:'disabled',caret:'hide',maxDiffPixelRatio:.02,
      });
    });
  }
}
