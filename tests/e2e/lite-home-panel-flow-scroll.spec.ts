import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// PR #606 Home activity and PR #623 portal scroll ownership, adapted to
// PR #637 native grouped-navigation treatment. AUTHORED — NOT RUN.
type Panel='workspace'|'activity';
async function openPanel(page:Page, kind:Panel,appearance='dark',scenario='healthy') {
  await page.addInitScript((value)=>localStorage.setItem('pocketlab:appearance',value),appearance);
  await installScenario(page,scenario);
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page,'home');
  const title=kind==='workspace'?'Workspace details':'Recent activity';
  const opener=page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View all activity'});
  await opener.click();
  const dialog=page.getByRole('dialog',{name:title});
  await expect(dialog).toBeVisible();
  return {dialog,opener};
}
async function scrollFixture(dialog:Locator) {
  const scroll=dialog.locator('.lite-home-panel-scroll');
  await scroll.evaluate((node)=>{
    const filler=document.createElement('section');
    filler.dataset.homeScrollFixture='true';
    filler.setAttribute('aria-hidden','true');
    filler.style.cssText='min-height:1400px;pointer-events:none;contain:layout';
    node.append(filler);
  });
  await expect.poll(()=>scroll.evaluate((node)=>node.scrollHeight-node.clientHeight)).toBeGreaterThan(300);
  return scroll;
}
for(const kind of ['workspace','activity'] as const) {
  test(kind+' native grouped panel: one scroll owner, nested detail and clean reopen',async ({page})=>{
    await page.setViewportSize({width:390,height:780});
    const {dialog,opener}=await openPanel(page,kind);
    const label=kind==='workspace'?'Service health':'History';
    await dialog.getByRole('button',{name:label}).click();
    await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
    const scroll=await scrollFixture(dialog);
    await scroll.evaluate((node)=>node.scrollTo({top:240,behavior:'instant'}));
    await expect.poll(()=>scroll.evaluate((node)=>node.scrollTop)).toBeGreaterThan(200);
    await scroll.evaluate((node)=>{
      const nested=document.createElement('div');
      nested.style.cssText='height:110px;overflow:auto;overscroll-behavior:contain';
      const child=document.createElement('div');
      child.style.height='500px';nested.append(child);node.append(nested);
      nested.scrollTop=160;
    });
    await expect.poll(()=>scroll.evaluate((node)=>node.scrollTop)).toBeGreaterThan(200);
    await dialog.getByRole('button',{name:kind==='workspace'?/All workspace details sections/:/All activity sections/}).click();
    await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
    await expect(scroll).toHaveJSProperty('scrollTop',0);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(opener).toBeFocused();
    await opener.click();
    await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
    await expect(dialog.locator('.lite-home-panel-scroll')).toHaveJSProperty('scrollTop',0);
  });
  for(const width of [390,1280]) for(const appearance of ['light','dark'] as const) {
    test(kind+' '+width+'px '+appearance+': actual panel width controls grouped layout',async ({page})=>{
      await page.setViewportSize({width,height:800});
      const {dialog}=await openPanel(page,kind,appearance);
      const nav=dialog.getByRole('navigation',{name:kind==='workspace'?'Workspace details sections':'Activity sections'});
      await expect(nav).toBeVisible();
      const target=kind==='workspace'?'Service health':'Running';
      await nav.getByRole('button',{name:target}).click();
      if (width <= 600) {
        // The native mobile contract replaces the persistent desktop rail
        // with a grouped-settings root and an explicit Back control.
        await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
        await expect(dialog.getByRole('button',{name:kind==='workspace'?/All workspace details sections/:/All activity sections/})).toBeVisible();
      } else {
        await expect(nav.getByRole('button',{name:target})).toHaveAttribute('aria-current','page');
      }
      await expect(dialog.locator('.lite-home-settings-detail-heading')).toBeVisible();
      const scroll=await scrollFixture(dialog);
      await scroll.evaluate((node)=>node.scrollTo({top:160,behavior:'instant'}));
      await expect.poll(()=>scroll.evaluate((node)=>node.scrollTop)).toBeGreaterThan(120);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
    });
  }
  test(kind+' system theme retains selection and review state',async ({page})=>{
    await page.setViewportSize({width:390,height:780});
    await page.emulateMedia({colorScheme:'dark'});
    const {dialog}=await openPanel(page,kind,'system');
    const selected=kind==='workspace'?'Service health':'History';
    await dialog.getByRole('button',{name:selected}).click();
    await page.emulateMedia({colorScheme:'light'});
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme','light');
    await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
    await expect(dialog.getByRole('button',{name:kind==='workspace'?/All workspace details sections/:/All activity sections/})).toBeVisible();
  });
  test(kind+' accessible Black panel preserves grouped focusable controls',async ({page})=>{
    await page.setViewportSize({width:360,height:760});
    await page.emulateMedia({reducedMotion:'reduce'});
    const {dialog}=await openPanel(page,kind,'dark');
    const results=await new AxeBuilder({page}).include('[role="dialog"]')
      .withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
    expect(results.violations.filter((issue)=>['serious','critical'].includes(issue.impact||''))).toEqual([]);
    await expect(dialog.getByRole('button',{name:/Close Home details/})).toBeVisible();
  });
}

for(const width of [320,360,375,390,430]) {
  test('Service flow '+width+'px Black: four readable stages and no overflow',async ({page})=>{
    await page.setViewportSize({width,height:780});
    const {dialog}=await openPanel(page,'workspace','dark');
    await dialog.getByRole('button',{name:'Service health'}).click();
    const flow=dialog.locator('.lite-home-workflow');
    await expect(flow.getByRole('listitem')).toHaveCount(4);
    await expect(flow.locator('.lite-home-workflow-line')).toHaveCount(3);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
  });
}
test('Narrow desktop resize retains flow without leaking page scroll',async ({page})=>{
  await page.setViewportSize({width:1024,height:800});
  const {dialog}=await openPanel(page,'workspace','dark');
  await dialog.getByRole('button',{name:'Resize Workspace details panel'}).focus();
  for(let n=0;n<14;n+=1) await page.keyboard.press('ArrowLeft');
  await dialog.getByRole('button',{name:'Service health'}).click();
  await expect(dialog.locator('.lite-home-workflow-visual')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
  await dialog.getByRole('button',{name:'Reset Workspace details position and size'}).click();
});
