import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Authored for later qualification only; no baseline is considered accepted here.
async function showApps(page:Page, scenario='catalog-ready', theme:'light'|'dark'|'system'='light', width=390) {
  await page.setViewportSize({width, height: width <= 430 ? 780 : 900});
  if(theme === 'system') await page.emulateMedia({colorScheme:'dark'});
  await page.addInitScript(pref => localStorage.setItem('pocketlab:appearance', pref), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page,'catalog');
}
async function openManage(page:Page) {
  await page.locator('.lite-catalog-app-card').getByRole('button',{name:'Manage',exact:true}).first().click();
  const panel=page.getByRole('dialog',{name:/Manage /}).first();
  await expect(panel).toBeVisible();
  return panel;
}
async function tokenAndBackground(page:Page, selector:string, token:string) {
  return page.locator(selector).first().evaluate((node, token) => {
    const root=getComputedStyle(document.documentElement);
    const value=root.getPropertyValue(token).trim();
    const probe=document.createElement('span');
    probe.style.backgroundColor=value;
    document.body.appendChild(probe);
    const expected=getComputedStyle(probe).backgroundColor;
    probe.remove();
    return {actual:getComputedStyle(node).backgroundColor, expected};
  },token);
}

test.describe('Apps Azure Horizon final polish — authored, not executed',()=>{
  for(const theme of ['light','dark','system'] as const) {
    for(const width of [320,360,390,430,768,1280]) {
      test(theme+' '+width+': semantic surfaces, no collision and stable action gaps',async({page})=>{
        await showApps(page,'catalog-ready',theme,width);
        const card=page.locator('.lite-catalog-app-card').first();
        await expect(card.getByRole('button',{name:'Open',exact:true})).toBeVisible();
        await expect(card.getByRole('button',{name:'Manage',exact:true})).toBeVisible();
        const buttons=card.locator('.lite-catalog-actions > button');
        const boxes=await buttons.evaluateAll(nodes => nodes.map(node=>{
          const rect=node.getBoundingClientRect();return {left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom};
        }));
        if(boxes.length>=2) expect(
          boxes[1].top >= boxes[0].bottom + 4 || boxes[1].left >= boxes[0].right + 4
        ).toBe(true);
        const dialog=await openManage(page);
        const box=await dialog.boundingBox();
        expect(box).toBeTruthy();
        expect((box?.x || 0)+(box?.width || 0)).toBeLessThanOrEqual(width+2);
        const targets:[
          string,string
        ][]=[
          ['.lite-catalog-manage-sheet','--azure-surface'],
          ['.lite-catalog-manage-scroll','--azure-surface'],
          ['.lite-catalog-manage-section-tabs','--azure-raised'],
        ];
        for(const [selector,token] of targets) {
          const colors=await tokenAndBackground(page,selector,token);
          expect(colors.actual).toBe(colors.expected);
        }
        if(width<=700){
          await expect(dialog).toHaveAttribute('data-lite-apps-manage-layout','mobile-sheet');
          await expect(dialog.getByRole('button',{name:'Close app actions'})).toBeVisible();
          await expect(dialog.getByRole('button',{name:/Resize sheet, currently/})).toBeVisible();
        }else{
          await expect(dialog.getByRole('button',{name:'Move app management panel'})).toBeVisible();
          await expect(dialog.getByRole('button',{name:'Reset app panel position and size'})).toBeVisible();
          await expect(dialog.getByRole('button',{name:'Resize app management panel'})).toBeVisible();
          await expect(dialog.locator('.lite-catalog-manage-resize-grip')).toHaveCount(0);
        }
        expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+2)).toBe(true);
      });
    }
    test(theme+': description is not repeated and status remains truthful',async({page})=>{
      await showApps(page,'catalog-ready',theme,390);
      const card=page.locator('.lite-catalog-app-card').first();
      const description=(await card.locator('.lite-catalog-app-description').innerText()).trim();
      const status=await card.locator('.lite-catalog-premium-app-status').allInnerTexts();
      expect(status.filter(text=>text.trim()===description)).toHaveLength(0);
    });
    test(theme+': tablist and disclosures retain semantics',async({page})=>{
      await showApps(page,'catalog-ready',theme,390);
      const dialog=await openManage(page);
      const tabs=dialog.getByRole('tab');
      await expect(tabs.first()).toHaveAttribute('aria-selected','true');
      await tabs.first().focus();
      await page.keyboard.press('End');
      await expect(tabs.last()).toHaveAttribute('aria-selected','true');
      await page.keyboard.press('Home');
      await expect(tabs.first()).toHaveAttribute('aria-selected','true');
      const storage=dialog.locator('.lite-catalog-premium-storage-details');
      if(await storage.count()){
        await expect(storage).not.toHaveAttribute('open','');
        await storage.locator('summary').click();
        await expect(storage).toHaveAttribute('open','');
        await expect(storage).toContainText('Where this app runs');
        await storage.locator('summary').focus();
        await page.keyboard.press('Enter');
        await expect(storage).not.toHaveAttribute('open','');
      }
      const notices=dialog.locator('.lite-catalog-premium-action-notices');
      if(await notices.count()){
        await notices.locator('summary').click();
        await expect(notices).toHaveAttribute('open','');
        await expect(notices.locator('article').first()).toBeVisible();
      }
      const guide=dialog.getByRole('region',{name:'Photo backup'}).locator('details');
      if(await guide.count()){
        await guide.locator('summary').click();
        await expect(guide).toContainText('Connect a source');
        await expect(guide).toContainText('Check readiness');
        await expect(guide).toContainText('Deliver to PhotoPrism');
      }
    });
    test(theme+': Axe evaluates Manage and nested Action Details',async({page})=>{
      await showApps(page,'catalog-ready',theme,390);
      const dialog=await openManage(page);
      const initial=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
      expect(initial.violations).toEqual([]);
      const detailsButton=dialog.getByRole('region',{name:'Photo workflow'}).getByRole('button',{name:'View details'});
      if(await detailsButton.count()) {
        await detailsButton.click();
        await expect(page.locator('.lite-details-overlay-layer .lite-details-panel')).toBeVisible();
        const nested=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
        expect(nested.violations).toEqual([]);
        await page.keyboard.press('Escape');
        await expect(dialog).toBeVisible();
      }
    });
  }

  test('mobile sheet supports every snap state, explicit close, gesture and keyboard fallback',async({page})=>{
    await showApps(page,'catalog-ready','dark',390);
    const dialog=await openManage(page);
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap','medium');
    await dialog.getByRole('button',{name:'Expand',exact:true}).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap','expanded');
    await dialog.getByRole('button',{name:'Compact',exact:true}).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap','medium');
    const grip=dialog.getByRole('button',{name:/Resize sheet, currently/});
    await grip.focus();
    await page.keyboard.press('Home');
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap','compact');
    await page.keyboard.press('End');
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap','expanded');
    // The snap height is animated; wait for the grip to stop moving before a
    // coordinate-driven pointer sequence so capture starts on the grip itself.
    await page.waitForTimeout(250);
    const rect=await grip.boundingBox();
    if(rect){
      await page.mouse.move(rect.x+rect.width/2,rect.y+rect.height/2);
      await page.mouse.down();
      await page.mouse.move(rect.x+rect.width/2,rect.y+rect.height/2+300,{steps:8});
      await page.mouse.up();
      await expect(dialog).not.toHaveAttribute('data-lite-sheet-snap','expanded');
    }
    await dialog.getByRole('button',{name:'Close app actions'}).click();
    await expect(dialog).toHaveCount(0);
  });

  test('mobile sheet resizes with visual viewport changes and keeps controls outside content scroll',async({page})=>{
    await showApps(page,'catalog-ready','light',320);
    const dialog=await openManage(page);
    await page.setViewportSize({width:320,height:580});
    await expect(dialog).toBeVisible();
    const outer=await dialog.boundingBox();
    expect((outer?.height || 0)).toBeLessThanOrEqual(580);
    await expect(dialog.locator('.lite-catalog-manage-scroll')).toBeVisible();
    await expect(dialog.getByRole('button',{name:'Close app actions'})).toBeVisible();
  });

  test('desktop header tools reuse keyboard geometry; nested panel does not move parent',async({page})=>{
    await showApps(page,'catalog-ready','dark',1280);
    const dialog=await openManage(page);
    const move=dialog.getByRole('button',{name:'Move app management panel'});
    await move.focus();
    const before=await dialog.boundingBox();
    await page.keyboard.press('ArrowLeft');
    const moved=await dialog.boundingBox();
    expect((moved?.x || 0)).toBeLessThanOrEqual(before?.x || 0);
    await dialog.getByRole('button',{name:'Resize app management panel'}).focus();
    await page.keyboard.press('ArrowDown');
    await dialog.getByRole('button',{name:'Reset app panel position and size'}).click();
    await dialog.getByRole('region',{name:'Photo workflow'}).getByRole('button',{name:'View details'}).click();
    const nested=page.locator('.lite-details-overlay-layer .lite-details-panel');
    await expect(nested).toBeVisible();
    await expect(nested.getByRole('button',{name:/Move .* panel/})).toBeVisible();
    await expect(nested.getByRole('button',{name:/Resize .* panel/})).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(dialog).toBeVisible();
  });

  for(const scenario of ['catalog-multi-app','catalog-install-available','app-action-failed','offline-saved','photo-backup-completed','photo-backup-remote-unavailable']){
    test('operational scenario keeps generic and backend-owned facts: '+scenario,async({page})=>{
      await showApps(page,scenario,'dark',390);
      await expect(page.locator('.lite-catalog-screen')).toBeVisible();
      if(scenario==='catalog-multi-app') await expect(page.getByRole('heading',{name:'Example App'})).toBeVisible();
      if(scenario.startsWith('photo-backup')){
        const panel=await openManage(page);
        const backup=panel.getByRole('region',{name:'Photo backup'});
        await expect(backup).toContainText(/app-record backups are separate/i);
      }
    });
  }
});
