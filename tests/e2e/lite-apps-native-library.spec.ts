import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORED, NOT EXECUTED. Screenshots below are unbaselined candidates for human review.
async function openLibrary(page: Page, scenario: string, appearance: 'light'|'dark'|'system', width: number, resolved: 'light'|'dark' = 'light') {
  await page.setViewportSize({width,height:width<700?800:900});
  await page.emulateMedia({reducedMotion:'reduce', colorScheme:resolved});
  await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value),appearance);
  await installScenario(page,scenario);
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page,'catalog');
  await page.evaluate(() => document.fonts.ready);
}
async function openManage(page: Page) {
  await page.locator('[data-app-library-card]').first().getByRole('button',{name:'Manage'}).click();
  const dialog=page.getByRole('dialog',{name:/Manage/i}).first();
  await expect(dialog).toBeVisible();
  return dialog;
}
for (const width of [320,390,768,1280]) {
  for (const appearance of ['light','dark','system'] as const) {
    test(`native library multi-app ${appearance} at ${width}px`, async ({page}) => {
      await openLibrary(page,'catalog-multi-app',appearance,width,appearance==='dark'?'dark':'light');
      await expect(page.getByRole('heading',{name:'Your library'})).toBeVisible();
      await expect(page.locator('[data-app-library-card]').first()).toBeVisible();
      await expect(page.locator('.lite-app-library-discovery')).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
      for(const button of await page.locator('[data-app-library-card] .lite-app-library-actions button').all()) {
        const rect=await button.boundingBox();
        expect(rect?.height || 0).toBeGreaterThanOrEqual(44);
      }
      await expect(page.locator('.lite-catalog-screen')).toHaveScreenshot(`native-library-${appearance}-${width}.png`,{animations:'disabled'});
    });
  }
}

for(const appearance of ['light','dark'] as const) {
  for(const width of [390,1280]) {
    test(`native Manage overview and category navigation ${appearance} ${width}`,async({page})=>{
      await openLibrary(page,'catalog-ready',appearance,width,appearance);
      const manage=await openManage(page);
      await expect(manage.getByRole('region',{name:'App overview'})).toBeVisible();
      await expect(manage.getByRole('tab',{name:'Overview'})).toHaveAttribute('aria-selected','true');
      await expect(manage).toHaveScreenshot(`native-manage-overview-${appearance}-${width}.png`,{animations:'disabled'});
      for(const label of ['Photos','Safety','Recovery','App setup','Activity']) {
        const tab=manage.getByRole('tab',{name:label});
        if(await tab.count()) {
          await tab.click();
          await expect(tab).toHaveAttribute('aria-selected','true');
          await expect(manage.locator('#lite-catalog-manage-active-panel')).toBeVisible();
          await expect(manage).toHaveScreenshot(`native-manage-${label.toLowerCase().replace(/\s+/g,'-')}-${appearance}-${width}.png`,{animations:'disabled'});
          if(width<820) await manage.getByRole('button',{name:'All settings'}).click();
        }
      }
    });
  }
}

test('saved-state library is read-only and Manage cannot submit writes',async({page})=>{
  await openLibrary(page,'offline-saved','dark',390,'dark');
  await expect(page.locator('[data-app-library-card]').first().getByRole('button',{name:'Open'})).toBeDisabled();
  const manage=await openManage(page);
  await expect(manage.getByText(/Saved app status|Saved information/).first()).toBeVisible();
  if(await manage.getByRole('tab',{name:'Safety'}).count()) {
    await manage.getByRole('tab',{name:'Safety'}).click();
    await expect(manage.locator('.lite-app-action-row button').first()).toBeDisabled();
  }
});
test('attention state keeps activity truthful without inventing success',async({page})=>{
  await openLibrary(page,'app-route-not-ready','dark',390,'dark');
  const manage=await openManage(page);
  await manage.getByRole('tab',{name:'Activity'}).click();
  await expect(manage.getByRole('region',{name:'Recent app activity'})).toBeVisible();
});
test('Manage keyboard navigation, focus trap, focus return and nested details',async({page})=>{
  await openLibrary(page,'catalog-ready','light',1280);
  const opener=page.locator('[data-app-library-card]').first().getByRole('button',{name:'Manage'});
  await opener.focus();await opener.click();
  const manage=page.getByRole('dialog',{name:/Manage PhotoPrism/i});
  await manage.getByRole('tab',{name:'Photos'}).click();
  const details=manage.getByRole('region',{name:'Photo workflow'}).getByRole('button',{name:/details/i});
  await details.click();
  await expect(page.locator('.lite-details-overlay-layer')).toBeVisible();
  await page.getByRole('button',{name:'Close Action Details'}).click();
  await expect(manage).toBeVisible();
  await manage.getByRole('button',{name:'Close app actions'}).click();
  await expect(opener).toBeFocused();
});
test('WCAG-oriented Apps library and Manage accessibility candidates',async({page})=>{
  await openLibrary(page,'catalog-ready','light',390);
  const library=await new AxeBuilder({page}).include('.lite-catalog-screen').analyze();
  expect(library.violations.filter(item=>['serious','critical'].includes(item.impact||''))).toEqual([]);
  await openManage(page);
  const manage=await new AxeBuilder({page}).include('.lite-catalog-manage-sheet').analyze();
  expect(manage.violations.filter(item=>['serious','critical'].includes(item.impact||''))).toEqual([]);
});
test('light and dark use identical library/Manage spacing and geometry',async({page})=>{
  const sample=async(theme:'light'|'dark')=>{
    await openLibrary(page,'catalog-ready',theme,1280,theme);
    const card=page.locator('[data-app-library-card]').first();
    const cardFacts=await card.evaluate(el=>{
      const cs=getComputedStyle(el);
      return {padding:cs.padding,gap:cs.gap,radius:cs.borderRadius,width:Math.round(el.getBoundingClientRect().width)};
    });
    const manage=await openManage(page);
    const manageFacts=await manage.evaluate(el=>{
      const cs=getComputedStyle(el);
      return {width:Math.round(el.getBoundingClientRect().width),padding:cs.padding,radius:cs.borderRadius};
    });
    return {cardFacts,manageFacts};
  };
  const light=await sample('light'),dark=await sample('dark');
  expect(dark).toEqual(light);
});
