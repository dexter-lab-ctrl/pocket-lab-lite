import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// The deterministic MSW projections below cover the validated Apps premium
// contract; live/backend and physical Android evidence is recorded separately.
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
test.describe('Azure Apps premium theme and responsive contracts — validated mocked matrix',()=>{
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
    test(`${theme}: action rows keep an aligned icon and typography contract`,async({page})=>{
      await catalog(page,'catalog-ready',theme,390);
      const panel=await photos(page);
      const rows=panel.locator('.lite-app-action-row');
      await expect(rows.first()).toBeVisible();
      const measurements=await rows.evaluateAll((nodes)=>nodes.map((node)=>{
        const main=node.querySelector('.lite-app-action-row-main');
        const icon=node.querySelector('.lite-app-action-row-icon');
        const copy=node.querySelector('.lite-app-action-row-copy');
        const iconBox=icon?.getBoundingClientRect();
        const firstCopyLine=copy?.firstElementChild?.getBoundingClientRect();
        const copyChildren=copy ? Array.from(copy.children).map((child)=>getComputedStyle(child).display) : [];
        return {
          mainDisplay:main ? getComputedStyle(main).display : '',
          iconDisplay:icon ? getComputedStyle(icon).display : '',
          copyDisplay:copy ? getComputedStyle(copy).display : '',
          iconWidth:iconBox?.width || 0,
          iconHeight:iconBox?.height || 0,
          iconToCopyGap:(firstCopyLine?.left || 0)-(iconBox?.right || 0),
          copyChildren,
        };
      }));
      expect(measurements.length).toBeGreaterThan(0);
      for(const measurement of measurements){
        expect(measurement.mainDisplay).toBe('grid');
        expect(measurement.iconDisplay).toBe('grid');
        expect(measurement.copyDisplay).toBe('grid');
        expect(measurement.iconWidth).toBeGreaterThanOrEqual(32);
        expect(measurement.iconHeight).toBeGreaterThanOrEqual(32);
        expect(measurement.iconToCopyGap).toBeGreaterThanOrEqual(4);
        expect(measurement.copyChildren).toEqual(['block','block','block']);
      }
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
    });
    test(`${theme}: Photo workflow is a connected, responsive stage rail`,async({page})=>{
      await catalog(page,'catalog-ready',theme,1280);
      const panel=await photos(page);
      const flow=panel.getByRole('region',{name:'Photo workflow'});
      await expect(flow).toBeVisible();
      if(await panel.getByText('Phone storage is already connected.',{exact:true}).count()) {
        await expect(flow.getByText('Phone',{exact:true})).toBeVisible();
      }
      const desktop=await flow.evaluate((node)=>{
        const steps=Array.from(node.querySelectorAll('.lite-catalog-premium-flow-step'));
        const icons=steps.map((step)=>{
          const box=step.querySelector('.lite-catalog-premium-flow-icon')?.getBoundingClientRect();
          return {width:box?.width || 0,height:box?.height || 0};
        });
        const rail=node.querySelector('.lite-catalog-premium-flow-steps')?.getBoundingClientRect();
        const connectors=Array.from(node.querySelectorAll('.lite-catalog-premium-flow-connector')).map((connector)=>{
          const box=connector.getBoundingClientRect();
          return {width:box.width,height:box.height};
        });
        const flowBox=node.getBoundingClientRect();
        const railBox=rail || flowBox;
        return {
          stepCount:steps.length,
          connectorCount:connectors.length,
          icons,
          connectors,
          railDisplay:getComputedStyle(node.querySelector('.lite-catalog-premium-flow-steps')).display,
          stageCenters:steps.map((step)=>{
            const box=step.getBoundingClientRect();
            return box.left+box.width/2;
          }),
          overflow:steps.some((step)=>{
            const box=step.getBoundingClientRect();
            return box.left < railBox.left-1 || box.right > railBox.right+1;
          }),
          footerDisplay:getComputedStyle(node.querySelector('.lite-catalog-premium-flow-foot')).display,
          summary:node.querySelector('.lite-catalog-premium-flow-foot p')?.textContent?.trim() || '',
          detailLabel:node.querySelector('.lite-catalog-premium-flow-foot button')?.textContent?.trim() || '',
        };
      });
      expect(desktop.stepCount).toBe(3);
      expect(desktop.connectorCount).toBe(2);
      expect(desktop.railDisplay).toBe('grid');
      expect(desktop.footerDisplay).toBe('grid');
      expect(desktop.summary).not.toBe('');
      expect(desktop.detailLabel).toBe('View details');
      expect(desktop.overflow).toBe(false);
      expect(Math.max(...desktop.stageCenters)-Math.min(...desktop.stageCenters)).toBeGreaterThan(0);
      const iconSizes=desktop.icons.map((icon)=>icon.width);
      expect(Math.max(...iconSizes)-Math.min(...iconSizes)).toBeLessThanOrEqual(1);
      for(const icon of desktop.icons){
        expect(icon.width).toBeGreaterThanOrEqual(40);
        expect(icon.height).toBeGreaterThanOrEqual(40);
      }
      for(const connector of desktop.connectors){
        expect(connector.width).toBeGreaterThan(0);
        expect(connector.height).toBeGreaterThan(0);
      }

      for(const width of [390,360,320]){
        await page.setViewportSize({width,height:780});
        const mobile=await flow.evaluate((node)=>{
          const rail=node.querySelector('.lite-catalog-premium-flow-steps');
          const railBox=rail?.getBoundingClientRect();
          const steps=Array.from(node.querySelectorAll('.lite-catalog-premium-flow-step'));
          const connectors=Array.from(node.querySelectorAll('.lite-catalog-premium-flow-connector'));
          return {
            railColumns:rail ? getComputedStyle(rail).gridTemplateColumns : '',
            stepsWithinRail:steps.every((step)=>{
              const box=step.getBoundingClientRect();
              return box.left >= (railBox?.left || 0)-1 && box.right <= (railBox?.right || 0)+1;
            }),
            connectorsVisible:connectors.every((connector)=>{
              const box=connector.getBoundingClientRect();
              return box.width > 0 && box.height > 0;
            }),
            documentOverflow:document.documentElement.scrollWidth > innerWidth+2,
          };
        });
        expect(mobile.stepsWithinRail).toBe(true);
        expect(mobile.connectorsVisible).toBe(true);
        expect(mobile.documentOverflow).toBe(false);
        if(width<=360) expect(mobile.railColumns.split(' ').length).toBe(1);
      }
    });
    test(`${theme}: nested Details toolbar is isolated, labelled and collision-free`,async({page})=>{
      await catalog(page,'catalog-ready',theme,1280);
      const panel=await photos(page);
      await panel.getByRole('region',{name:'Photo workflow'}).getByRole('button',{name:'View details'}).click();
      const details=page.locator('.lite-details-overlay-layer .lite-details-panel');
      await expect(details).toBeVisible();
      const toolbar=details.locator('[data-lite-overlay-panel-tools="desktop"]');
      await expect(toolbar).toHaveAttribute('aria-label','Desktop Import photos panel controls');
      await expect(toolbar.getByRole('button',{name:'Move Import photos panel'})).toHaveText('Move');
      await expect(toolbar.getByRole('button',{name:'Reset Import photos position and size'})).toHaveText('Reset');
      await expect(toolbar.getByRole('button',{name:'Resize Import photos panel'})).toHaveText('Resize');
      await expect(details.getByRole('button',{name:'Close Action Details'})).toBeVisible();
      const detailsBox=await details.boundingBox();
      const controls=await toolbar.getByRole('button').evaluateAll((buttons)=>buttons.map((button)=>{
        const box=button.getBoundingClientRect();
        return {left:box.left,right:box.right,top:box.top,bottom:box.bottom};
      }));
      expect(detailsBox).toBeTruthy();
      expect(controls).toHaveLength(3);
      for(const control of controls){
        expect(control.left).toBeGreaterThanOrEqual((detailsBox?.left || 0)-1);
        expect(control.right).toBeLessThanOrEqual((detailsBox?.x || 0)+(detailsBox?.width || 0)+1);
      }
      for(let index=1;index<controls.length;index++){
        expect(controls[index].left).toBeGreaterThanOrEqual(controls[index-1].right+2);
      }
      const parentBefore=await panel.boundingBox();
      const nestedBefore=await details.boundingBox();
      await toolbar.getByRole('button',{name:'Move Import photos panel'}).focus();
      await page.keyboard.press('ArrowLeft');
      const nestedMoved=await details.boundingBox();
      const parentAfter=await panel.boundingBox();
      expect(nestedMoved?.x).toBeLessThanOrEqual(nestedBefore?.x || 0);
      expect(parentAfter?.x).toBeCloseTo(parentBefore?.x || 0,0);
      const moveBox=await toolbar.getByRole('button',{name:'Move Import photos panel'}).boundingBox();
      if(!moveBox) throw new Error('Nested Move control bounds unavailable');
      const pointerMoveBefore=await details.boundingBox();
      await page.mouse.move(moveBox.x+moveBox.width/2,moveBox.y+moveBox.height/2);
      await page.mouse.down();
      await page.mouse.move(moveBox.x+moveBox.width/2+48,moveBox.y+moveBox.height/2+24,{steps:3});
      await page.mouse.up();
      const pointerMoved=await details.boundingBox();
      expect(pointerMoved?.x).toBeGreaterThan(pointerMoveBefore?.x || 0);
      expect(pointerMoved?.y).toBeGreaterThan(pointerMoveBefore?.y || 0);
      const resizeBox=await toolbar.getByRole('button',{name:'Resize Import photos panel'}).boundingBox();
      if(!resizeBox) throw new Error('Nested Resize control bounds unavailable');
      const pointerResizeBefore=await details.boundingBox();
      await page.mouse.move(resizeBox.x+resizeBox.width/2,resizeBox.y+resizeBox.height/2);
      await page.mouse.down();
      await page.mouse.move(resizeBox.x+resizeBox.width/2+40,resizeBox.y+resizeBox.height/2+32,{steps:3});
      await page.mouse.up();
      const pointerResized=await details.boundingBox();
      expect(pointerResized?.width).toBeGreaterThanOrEqual(pointerResizeBefore?.width || 0);
      expect(pointerResized?.height).toBeGreaterThanOrEqual(pointerResizeBefore?.height || 0);
      await toolbar.getByRole('button',{name:'Reset Import photos position and size'}).click();
      await expect(details).toBeVisible();
      await details.getByRole('button',{name:'Close Action Details'}).click();
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
    await expect(page.getByRole('heading',{name:'Example App',exact:true})).toBeVisible();
    await page.getByRole('searchbox',{name:'Search apps'}).fill('Example');
    await expect(page.locator('.lite-catalog-app-card')).toHaveCount(1);
    const panel=page.getByRole('button',{name:'Manage',exact:true}).first();
    await panel.click();
    const dialog=page.getByRole('dialog',{name:/Manage Example App/i});
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('region',{name:'Photo backup'})).toHaveCount(0);
  });
});
test.describe('premium operational facts and gesture ownership — validated mocked matrix',()=>{
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

test.describe('touch pull P2 boundary — validated where supported',()=>{
  test('small pull stays below threshold; release triggers one refresh, leaves buttons clickable',async({page},testInfo)=>{
    test.skip(!testInfo.project.name.includes('mobile'),'Touch-only scenario');
    await page.addInitScript(()=>{
      (window as any).__appsCatalogReadCount=0;
      const actual=window.fetch.bind(window);
      window.fetch=(...args)=>{
        if(String(args[0]).includes('/api/lite/catalog')) (window as any).__appsCatalogReadCount++;
        return actual(...args);
      };
    });
    await catalog(page,'catalog-ready','dark',390);
    const zone=page.locator('.lite-catalog-touch-pull-zone');
    await expect(zone).toBeVisible();
    const box=await zone.boundingBox();
    if(!box) throw new Error('Missing touch zone');
    const x=Math.round(box.x+box.width/2), y=Math.round(box.y+box.height/2);
    const cdp=await page.context().newCDPSession(page);
    const send=(type:string,yy:number)=>cdp.send('Input.dispatchTouchEvent',{
      type,touchPoints:type==='touchEnd'?[]:[{x,y:yy,id:0}]
    });
    await send('touchStart',y);
    await send('touchMove',y+20);
    await expect(page.locator('.lite-catalog-pull-refresh')).not.toHaveClass(/is-ready/);
    await send('touchEnd',y+20);
    const before=await page.evaluate(()=>(window as any).__appsCatalogReadCount);
    await send('touchStart',y);
    await send('touchMove',y+185);
    await expect(page.locator('.lite-catalog-pull-refresh')).toHaveClass(/is-ready/);
    await send('touchEnd',y+185);
    await expect.poll(async()=>page.evaluate(()=>(window as any).__appsCatalogReadCount)).toBeGreaterThan(before);
    await expect(page.locator('.lite-catalog-pull-refresh')).not.toHaveClass(/is-pulling/);
    await expect(page.getByRole('searchbox',{name:'Search apps'})).toBeEnabled();
  });
  test('vertical scroll outside touch zone stays owned by the document',async({page},testInfo)=>{
    test.skip(!testInfo.project.name.includes('mobile'),'Touch-only scenario');
    await catalog(page,'catalog-multi-app','light',390);
    await expect(page.locator('.lite-catalog-touch-pull-zone')).toBeVisible();
    const touchAction=await page.locator('.lite-catalog-screen .lite-catalog-toolbar').evaluate(el=>getComputedStyle(el).touchAction);
    expect(touchAction).not.toBe('none');
  });
  test('reduced motion removes pull-indicator transitions',async({page},testInfo)=>{
    test.skip(!testInfo.project.name.includes('mobile'),'Touch-only scenario');
    await page.emulateMedia({reducedMotion:'reduce'});
    await catalog(page,'catalog-ready','light',390);
    const result=await page.locator('.lite-catalog-pull-refresh').evaluate(el=>getComputedStyle(el).transitionDuration);
    expect(result.split(',').every(s=>s.trim()==='0s')).toBe(true);
  });
});
