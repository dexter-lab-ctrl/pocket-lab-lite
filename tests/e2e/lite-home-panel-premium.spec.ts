import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORED — NOT RUN. Grouped settings replace the old retracting tab strip.
async function openHome(page:Page,theme:'light'|'dark'|'system'='dark',scenario='healthy') {
  await page.addInitScript((mode)=>localStorage.setItem('pocketlab:appearance',mode),theme);
  await installScenario(page,scenario);
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page,'home');
}
async function panel(page:Page,kind:'workspace'|'activity') {
  await page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View all activity'}).click();
  const dialog=page.getByRole('dialog',{name:kind==='workspace'?'Workspace details':'Recent activity'});
  await expect(dialog).toBeVisible();
  return dialog;
}
for(const width of [320,360,375,390,430,768,1024,1440]) {
  for(const kind of ['workspace','activity'] as const) {
    test('Home '+kind+' grouped sheet bounds and controls at '+width+'px',async ({page})=>{
      await page.setViewportSize({width,height:850});
      await page.emulateMedia({reducedMotion:'reduce'});
      await openHome(page,'light');
      const dialog=await panel(page,kind);
      const rect=await dialog.boundingBox();
      expect(rect).not.toBeNull();
      if(rect) {expect(rect.x).toBeGreaterThanOrEqual(-1);expect(rect.x+rect.width).toBeLessThanOrEqual(width+1);}
      await expect(dialog).toHaveAttribute('data-home-panel-layout',width>=701?'desktop-movable':'mobile-sheet');
      const nav=dialog.getByRole('navigation',{name:kind==='workspace'?'Workspace details sections':'Activity sections'});
      await expect(nav).toBeVisible();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
      if(width<701) {
        await expect(dialog.getByRole('button',{name:/^Move .* panel$/})).toHaveCount(0);
        await expect(dialog.getByRole('button',{name:/^Resize .* panel$/})).toHaveCount(0);
      }
    });
  }
}
for(const kind of ['workspace','activity'] as const) {
  test('Home '+kind+' root, nested detail, Back and return focus',async ({page})=>{
    await page.setViewportSize({width:390,height:780});
    await openHome(page);
    const opener=page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View all activity'});
    const dialog=await panel(page,kind);
    await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
    const name=kind==='workspace'?'Diagnostics':'History';
    await dialog.getByRole('button',{name}).click();
    await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
    await expect(dialog.getByRole('heading',{name})).toBeVisible();
    await dialog.getByRole('button',{name:kind==='workspace'?/All workspace details sections/:/All activity sections/}).click();
    await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(opener).toBeFocused();
  });
  test('Home '+kind+' portal remains themed under live System changes',async ({page})=>{
    await page.emulateMedia({colorScheme:'dark',reducedMotion:'reduce'});
    await openHome(page,'system');
    const dialog=await panel(page,kind);
    const layer=page.locator('.lite-home-panel-layer[data-lite-overlay-portal]');
    await expect(layer).toHaveClass(/theme-pocket-lite-dark/);
    await page.emulateMedia({colorScheme:'light'});
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme','light');
    await expect(layer).toHaveClass(/theme-pocket-lite-daylight/);
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('.lite-home-settings-row[aria-current="page"]')).toHaveCount(1);
  });
  test('Home '+kind+' desktop move, resize, reset and clamp',async ({page})=>{
    await page.setViewportSize({width:1280,height:900});
    await openHome(page,'dark');
    const dialog=await panel(page,kind);
    const title=kind==='workspace'?'Workspace details':'Recent activity';
    const before=await dialog.boundingBox();
    await dialog.getByRole('button',{name:'Move '+title+' panel'}).focus();
    await page.keyboard.press('ArrowLeft');
    const moved=await dialog.boundingBox();
    if(before&&moved) expect(moved.x).toBeLessThan(before.x);
    await dialog.getByRole('button',{name:'Resize '+title+' panel'}).focus();
    await page.keyboard.press('ArrowLeft');
    const resized=await dialog.boundingBox();
    if(resized&&moved) expect(resized.width).toBeLessThanOrEqual(moved.width);
    await dialog.getByRole('button',{name:'Reset '+title+' position and size'}).click();
    await page.setViewportSize({width:780,height:640});
    const clamped=await dialog.boundingBox();
    if(clamped){expect(clamped.x).toBeGreaterThanOrEqual(-1);expect(clamped.x+clamped.width).toBeLessThanOrEqual(781);}
  });
  for(const theme of ['light','dark'] as const) {
    test('Home '+kind+' '+theme+' semantic panel contrast and Axe AA',async ({page})=>{
      await page.setViewportSize({width:390,height:844});
      await openHome(page,theme);
      const dialog=await panel(page,kind);
      const colors=await dialog.evaluate((node)=>{
        const selectors=['.lite-overlay-head','.lite-home-panel-scroll','.lite-home-settings-navigation','.lite-home-settings-row'];
        return selectors.map((selector)=>node.querySelector(selector)).filter(Boolean)
          .map((element)=>({background:getComputedStyle(element!).backgroundColor,color:getComputedStyle(element!).color}));
      });
      expect(colors.length).toBeGreaterThan(3);
      for(const color of colors) {
        if(theme==='dark') expect(color.background).not.toBe('rgb(255, 255, 255)');
        expect(color.color).not.toBe(color.background);
      }
      const result=await new AxeBuilder({page}).include('[role="dialog"]')
        .withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
      expect(result.violations.filter((v)=>['serious','critical'].includes(v.impact||''))).toEqual([]);
    });
  }
}
test('Saved activity review remains private and confirmation is disabled',async ({page})=>{
  await openHome(page,'dark','offline-saved');
  const dialog=await panel(page,'activity');
  await dialog.getByRole('button',{name:'History'}).click();
  await expect(dialog.getByText('Private review position and status',{exact:true})).toBeVisible();
  await expect(dialog.getByRole('button',{name:/Mark activity reviewed/i})).toHaveCount(0);
});
test('Mobile text scaling and reduced motion preserve grouped navigation',async ({page})=>{
  await page.setViewportSize({width:320,height:760});
  await page.emulateMedia({reducedMotion:'reduce'});
  await openHome(page,'dark');
  await page.addStyleTag({content:'html{font-size:200%}'});
  for(const kind of ['workspace','activity'] as const) {
    const dialog=await panel(page,kind);
    await expect(dialog.locator('.lite-home-settings-navigation')).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
    const duration=await dialog.locator('.lite-home-settings-row').first().evaluate((node)=>
      getComputedStyle(node).transitionDuration.split(',').map((x)=>Number.parseFloat(x)||0));
    expect(duration.every((value)=>value<=.001)).toBe(true);
    await page.keyboard.press('Escape');
  }
});
