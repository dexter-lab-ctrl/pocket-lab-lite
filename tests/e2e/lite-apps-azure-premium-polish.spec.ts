import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORED — NOT EXECUTED — UNVALIDATED. All fixtures are deterministic MSW projections.
async function catalog(page:Page, scenario='catalog-ready', theme:'light'|'dark'|'system'='light', width=1280) {
  await page.setViewportSize({width,height:width<=430?780:900});
  await page.addInitScript(pref=>localStorage.setItem('pocketlab:appearance',pref),theme);
  await installScenario(page,scenario);
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page,'catalog');
}
async function manage(page:Page) {
  await page.locator('.lite-catalog-app-card').getByRole('button',{name:'Manage',exact:true}).first().click();
  const dialog=page.getByRole('dialog',{name:/Manage PhotoPrism/i});
  await expect(dialog).toBeVisible();
  return dialog;
}
async function photos(page:Page) {
  const dialog=await manage(page);
  const tab=dialog.getByRole('tab',{name:'Photos'});
  if(await tab.count()) await tab.click();
  return dialog;
}
async function azureBackgroundMatches(page:Page, selector:string) {
  const colors=await page.locator(selector).first().evaluate(node=>{
    const token=getComputedStyle(document.documentElement).getPropertyValue('--azure-surface').trim();
    const element=getComputedStyle(node).backgroundColor;
    const probe=document.createElement('span');
    probe.style.background=token;
    document.body.appendChild(probe);
    const expected=getComputedStyle(probe).backgroundColor;
    probe.remove();
    return {element,expected};
  });
  expect(colors.element).toBe(colors.expected);
}
test.describe('Azure Apps premium theme and responsive contracts — authored, never executed',()=>{
  for(const theme of ['light','dark'] as const){
    for(const width of [320,375,390,768,1024,1440]){
      test(`${theme} ${width}px: catalog and Manage stay within bounds`,async({page})=>{
        await catalog(page,'catalog-ready',theme,width);
        await expect(page.locator('html')).toHaveAttribute('data-lite-theme',theme);
        await expect(page.getByRole('searchbox',{name:'Search apps'})).toBeVisible();
        const panel=await manage(page);
        const box=await panel.boundingBox();
        expect(box).toBeTruthy();
        expect((box?.x || 0)+(box?.width || 0)).toBeLessThanOrEqual(width+2);
        if(width<=700) {
          await expect(panel).toHaveAttribute('data-lite-apps-manage-layout','mobile-sheet');
          await expect(panel.getByRole('button',{name:/Resize app management panel/})).toHaveCount(0);
          await expect(panel.getByRole('button',{name:/Move app management panel/})).toHaveCount(0);
        } else {
          await expect(panel.getByRole('button',{name:/Resize app management panel/})).toBeVisible();
        }
        expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
      });
    }
    test(`${theme}: nested Details uses resolved Azure surfaces`,async({page})=>{
      await catalog(page,'catalog-ready',theme);
      const panel=await photos(page);
      await azureBackgroundMatches(page,'.lite-catalog-manage-sheet');
      await azureBackgroundMatches(page,'.lite-catalog-manage-scroll');
      await panel.getByRole('region',{name:'Photo workflow'}).getByRole('button',{name:'View details'}).click();
      const details=page.locator('.lite-details-overlay-layer .lite-details-panel');
      await expect(details).toBeVisible();
      await azureBackgroundMatches(page,'.lite-details-overlay-layer .lite-details-panel');
      await azureBackgroundMatches(page,'.lite-apps-premium-details-scroll');
      await expect(details).toContainText(/What happened|What changed/);
      await page.keyboard.press('Escape');
      await expect(details).toHaveCount(0);
      await expect(panel).toBeVisible();
    });
    test(`${theme}: tablist arrows, Home and End preserve selection`,async({page})=>{
      await catalog(page,'catalog-ready',theme);
      const panel=await manage(page);
      const tabs=panel.getByRole('tab');
      await expect(tabs.first()).toHaveAttribute('aria-selected','true');
      await tabs.first().focus();
      await page.keyboard.press('ArrowRight');
      await expect(tabs.nth(1)).toHaveAttribute('aria-selected','true');
      await page.keyboard.press('End');
      await expect(tabs.last()).toHaveAttribute('aria-selected','true');
      await page.keyboard.press('Home');
      await expect(tabs.first()).toHaveAttribute('aria-selected','true');
      await expect(panel.getByRole('tabpanel')).toHaveAttribute('aria-labelledby',await tabs.first().getAttribute('id') || '');
    });
    test(`${theme}: Axe WCAG AA including dialog and action cards`,async({page})=>{
      await catalog(page,'catalog-ready',theme,390);
      const panel=await photos(page);
      await expect(panel.getByRole('region',{name:'Photo backup'})).toBeVisible();
      const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
      expect(axe.violations).toEqual([]);
    });
  }
  test('System appearance follows changes with portal open',async({page})=>{
    await page.emulateMedia({colorScheme:'dark'});
    await catalog(page,'catalog-ready','system');
    const panel=await manage(page);
    await page.emulateMedia({colorScheme:'light'});
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme','light');
    await azureBackgroundMatches(page,'.lite-catalog-manage-sheet');
    await page.emulateMedia({colorScheme:'dark'});
    await expect(panel).toBeVisible();
    await azureBackgroundMatches(page,'.lite-catalog-manage-sheet');
  });
  test('generic non-PhotoPrism app does not inherit photo-only controls',async({page})=>{
    await catalog(page,'catalog-multi-app','light');
    await expect(page.getByText('Example App')).toBeVisible();
    await page.getByRole('searchbox',{name:'Search apps'}).fill('Example');
    await expect(page.locator('.lite-catalog-app-card')).toHaveCount(1);
    const panel=page.getByRole('button',{name:'Manage',exact:true}).first();
    await panel.click();
    const dialog=page.getByRole('dialog',{name:/Manage Example App/i});
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('region',{name:'Photo backup'})).toHaveCount(0);
  });
});
test.describe('premium operational facts and gesture ownership — authored, never executed',()=>{
  for(const scenario of ['photo-backup-completed','photo-backup-remote-unavailable','photo-backup-photoprism-unavailable','photo-backup-malformed','photo-backup-permission-missing']){
    test(`backend-specific photo facts: ${scenario}`,async({page})=>{
      await catalog(page,scenario);
      const panel=await photos(page);
      const card=panel.getByRole('region',{name:'Photo backup'});
      await expect(card).toContainText('Device');
      await expect(card).toContainText('Transfer');
      await expect(card).toContainText('Destination');
      await expect(card).toContainText('Last update');
      await expect(card).not.toContainText(/100% complete/i);
      if(scenario==='photo-backup-malformed') await expect(card).toContainText(/Not reported|Unavailable|Unknown/);
      if(scenario==='photo-backup-remote-unavailable') await expect(card).toContainText(/not ready|attention|unavailable/i);
    });
  }
  test('structured storage, backup guide and actual notices stay readable',async({page})=>{
    await catalog(page,'catalog-ready','dark',390);
    const panel=await photos(page);
    const disclosure=panel.locator('.lite-catalog-premium-storage-details');
    await disclosure.locator('summary').click();
    await expect(disclosure).toContainText('Where this app runs');
    await expect(disclosure).toContainText('Storage devices');
    const guide=panel.getByRole('region',{name:'Photo backup'}).locator('details');
    await guide.locator('summary').click();
    await expect(guide).toContainText('Connect a source');
    await expect(guide).toContainText('app records');
  });
  test('supplemental notices contain reasons but never replace active action status',async({page})=>{
    await catalog(page,'app-media-not-ready','light');
    const panel=await photos(page);
    const notices=panel.locator('.lite-catalog-premium-action-notices');
    if(await notices.count()){
      await notices.locator('summary').click();
      await expect(notices).toHaveAttribute('open','');
      const articles=notices.locator('.lite-catalog-action-reasons article');
      const count=await articles.count();
      for(let i=0;i<count;i++) await expect(articles.nth(i).locator('p').first()).not.toBeEmpty();
    }
  });
  test('pull control is absent on desktop and hidden while idle on touch device',async({page},testInfo)=>{
    await catalog(page,'catalog-ready','light',1280);
    await expect(page.locator('.lite-catalog-touch-pull-zone')).toBeHidden();
    await expect(page.locator('.lite-catalog-pull-refresh')).toHaveAttribute('aria-hidden','true');
    if(testInfo.project.name.includes('mobile')){
      await page.setViewportSize({width:390,height:760});
      await expect(page.locator('.lite-catalog-pull-refresh')).toHaveAttribute('aria-hidden','true');
    }
    await expect(page.getByRole('button',{name:/Refresh/i}).first()).toBeVisible();
  });
  test('desktop Manage move / resize / cancel / viewport clamp / reset',async({page})=>{
    await catalog(page,'catalog-ready','light',1440);
    const panel=await manage(page);
    const move=panel.getByRole('button',{name:'Move app management panel'});
    const initial=await panel.boundingBox();
    const pos=await move.boundingBox();
    if(!initial||!pos) throw new Error('Panel bounds unavailable');
    await page.mouse.move(pos.x+pos.width/2,pos.y+pos.height/2);
    await page.mouse.down();
    await page.mouse.move(pos.x+pos.width/2-80,pos.y+pos.height/2+44,{steps:5});
    await page.mouse.up();
    const moved=await panel.boundingBox();
    expect(moved?.x).toBeLessThan(initial.x);
    const grip=panel.getByRole('button',{name:'Resize app management panel'});
    await grip.focus();
    await page.keyboard.press('Shift+ArrowRight');
    const grown=await panel.boundingBox();
    expect(grown?.width).toBeGreaterThanOrEqual(moved?.width || 0);
    await page.setViewportSize({width:920,height:680});
    const clamped=await panel.boundingBox();
    expect(clamped?.x).toBeGreaterThanOrEqual(0);
    expect((clamped?.x||0)+(clamped?.width||0)).toBeLessThanOrEqual(922);
    await panel.getByRole('button',{name:'Reset app panel position and size'}).click();
    await expect(panel).toBeVisible();
  });
});
