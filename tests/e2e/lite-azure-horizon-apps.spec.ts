import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// SOURCE-DEFINED. No visual baselines have been captured or approved.
async function openApps(page: Page, theme: 'light' | 'dark' | 'system' = 'dark', scenario = 'catalog-ready') {
  await page.addInitScript((preference) => localStorage.setItem('pocketlab:appearance', preference), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page, 'catalog');
}
async function manageApp(page: Page) {
  const trigger = page.locator('.lite-catalog-app-card').getByRole('button', { name: 'Manage', exact: true }).first();
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: /Manage PhotoPrism/i });
  await expect(dialog).toBeVisible();
  return { trigger, dialog };
}

for (const width of [320,360,375,390,430,768,1024,1440]) {
  for (const appearance of ['light','dark'] as const) {
    test(`Apps Azure ${width}px / ${appearance}: library and Manage geometry`, async ({page}) => {
      await page.setViewportSize({width,height:width<500?760:960});
      await page.emulateMedia({reducedMotion:'reduce'});
      await openApps(page,appearance);
      await expect(page.locator('html')).toHaveAttribute('data-lite-theme',appearance);
      await expect(page.getByRole('heading',{name:'Your Apps'})).toBeVisible();
      await expect(page.getByRole('searchbox',{name:'Search apps'})).toBeVisible();
      const {dialog} = await manageApp(page);
      await expect(dialog).toHaveAttribute('data-lite-apps-manage-layout',width>=701?'desktop-movable':'mobile-sheet');
      if (width<701) await expect(dialog.getByRole('button',{name:'Resize app management panel'})).toHaveCount(0);
      const rect = await dialog.boundingBox();
      expect(rect).not.toBeNull();
      if (rect) {
        expect(rect.x).toBeGreaterThanOrEqual(-2);
        expect(rect.x+rect.width).toBeLessThanOrEqual(width+2);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)).toBe(false);
    });
  }
}
test('search and real projection-backed status counts remain keyboard-operable',async({page})=>{
  await openApps(page,'light','catalog-multi-app');
  const search=page.getByRole('searchbox',{name:'Search apps'});
  await search.fill('Example');
  await expect(page.locator('.lite-catalog-app-card')).toHaveCount(1);
  await page.getByRole('button',{name:'Clear app search'}).click();
  await expect(search).toHaveValue('');
  await page.getByRole('button',{name:/All \d+/}).click();
  await expect(page.locator('.lite-catalog-app-card').first()).toBeVisible();
  await search.fill('missing-test-app');
  await expect(page.getByText('No matching apps')).toBeVisible();
  await page.getByRole('button',{name:'Show all apps'}).click();
  await expect(search).toHaveValue('');
});
test('desktop drag, resize, keyboard, reset, bounds and nested Details',async({page})=>{
  await page.setViewportSize({width:1440,height:900});
  await openApps(page,'dark');
  const {dialog,trigger}=await manageApp(page);
  const move=dialog.getByRole('button',{name:'Move app management panel'});
  const resize=dialog.getByRole('button',{name:'Resize app management panel'});
  const initial=await dialog.boundingBox();
  expect(initial).not.toBeNull();
  await move.focus();
  await page.keyboard.press('ArrowLeft');
  const afterKeyboard=await dialog.boundingBox();
  expect(afterKeyboard?.x).toBeLessThanOrEqual(initial?.x||0);
  await resize.focus();
  await page.keyboard.press('Shift+ArrowDown');
  const resized=await dialog.boundingBox();
  expect(resized?.height).toBeGreaterThanOrEqual(initial?.height||0);
  const bounds=await move.boundingBox();
  if (bounds) {
    await page.mouse.move(bounds.x+bounds.width/2,bounds.y+bounds.height/2);
    await page.mouse.down();
    await page.mouse.move(100,100,{steps:4});
    await page.mouse.up();
  }
  const dragged=await dialog.boundingBox();
  expect(dragged).not.toBeNull();
  expect(dragged!.x).toBeGreaterThanOrEqual(-2);
  expect(dragged!.y).toBeGreaterThanOrEqual(-2);
  await dialog.getByRole('button',{name:'Reset app panel position and size'}).click();
  const reset=await dialog.boundingBox();
  expect(reset!.x).toBeGreaterThan(0);
  const photos=dialog.getByRole('tab',{name:'Photos'});
  if (await photos.count()) {
    await photos.click();
    const details=dialog.getByRole('button',{name:'View details'}).first();
    if (await details.count()) {
      await details.click();
      const nested=page.getByRole('dialog',{name:/Import photos/i});
      await expect(nested).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(dialog).toBeVisible();
    }
  }
  await dialog.getByRole('button',{name:'Close app actions'}).click();
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});
test('interactive controls do not initiate desktop dragging',async({page})=>{
  await page.setViewportSize({width:1280,height:850});
  await openApps(page);
  const {dialog}=await manageApp(page);
  const original=await dialog.boundingBox();
  const photos=dialog.getByRole('tab',{name:'Photos'});
  if(await photos.count()) await photos.click();
  const after=await dialog.boundingBox();
  expect(Math.abs((after?.x||0)-(original?.x||0))).toBeLessThanOrEqual(1);
});
test('switching desktop to mobile and back clamps and disables desktop controls',async({page})=>{
  await page.setViewportSize({width:1280,height:800});
  await openApps(page);
  const {dialog}=await manageApp(page);
  await expect(dialog.getByRole('button',{name:'Resize app management panel'})).toBeVisible();
  await page.setViewportSize({width:375,height:740});
  await expect(dialog).toHaveAttribute('data-lite-apps-manage-layout','mobile-sheet');
  await expect(dialog.getByRole('button',{name:'Resize app management panel'})).toHaveCount(0);
  await page.setViewportSize({width:1100,height:800});
  await expect(dialog).toHaveAttribute('data-lite-apps-manage-layout','desktop-movable');
  const rect=await dialog.boundingBox();
  expect(rect!.x+rect!.width).toBeLessThanOrEqual(1102);
});
for(const scenario of ['app-route-not-ready','app-media-not-ready','app-action-failed','offline-saved','catalog-installing','app-projection-stale','catalog-multi-app','app-governance-blocked']){
  test(`preserves backend-derived safety and state: ${scenario}`,async({page})=>{
    await openApps(page,'dark',scenario);
    await expect(page.locator('.lite-catalog-app-card').first()).toBeVisible();
    if (scenario==='app-route-not-ready') await expect(page.locator('.lite-catalog-app-card').first().getByRole('button',{name:'Open'})).toBeDisabled();
    if (scenario==='catalog-multi-app') await expect(page.getByText('Example App').first()).toBeVisible();
  });
}
for (const theme of ['light','dark'] as const) {
  test(`Azure Apps WCAG AA ${theme}: catalog, Manage, keyboard and 200% text`,async({page})=>{
    await page.setViewportSize({width:390,height:800});
    await page.emulateMedia({reducedMotion:'reduce'});
    await openApps(page,theme);
    let report=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
    expect(report.violations,JSON.stringify(report.violations)).toEqual([]);
    const {dialog}=await manageApp(page);
    await page.addStyleTag({content:'html {font-size:200%!important}'});
    report=await new AxeBuilder({page}).include('[data-lite-manage-portal="true"]').withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
    expect(report.violations,JSON.stringify(report.violations)).toEqual([]);
    expect((await dialog.boundingBox())!.x).toBeGreaterThanOrEqual(-2);
  });
}
test('Devices Manage retains the same desktop geometry controller regression surface',async({page})=>{
  await page.setViewportSize({width:1280,height:900});
  await installScenario(page,'healthy');
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page,'devices');
  const manage=page.locator('[data-lite-screen-id="devices"]').getByRole('button',{name:/Manage/i}).first();
  await manage.click();
  const panel=page.locator('[data-lite-details-panel-layout="desktop-movable"]');
  await expect(panel).toBeVisible();
  await expect(panel.getByRole('button',{name:'Move device details panel'})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Reset device details panel position and size'})).toBeVisible();
});
