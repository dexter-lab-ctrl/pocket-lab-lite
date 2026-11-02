import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import {
  expectLitePerformanceBudget, installLiteFrameSampler,
  measureLiteInteraction, writeLitePerformanceEvidence,
} from './lite-performance-helpers';

// PR #588 original gates retained. Home grouped navigation is the new
// interaction model; the retracting horizontal strip no longer exists.
// AUTHORED — NOT RUN (including physical Android).
test.beforeEach(async ({page})=>{ await installLiteFrameSampler(page); });
for(const kind of ['workspace','activity'] as const) {
  test('[interaction] Azure Home '+kind+' grouped panel open, switch and close',async ({page},info)=>{
    await installScenario(page,'healthy');
    await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page,'home');
    const title=kind==='workspace'?'Workspace details':'Recent activity';
    const open=await measureLiteInteraction(page,info,'azure-home-'+kind+'-premium-open',async ()=>{
      await page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View all activity'}).click();
      await expect(page.getByRole('dialog',{name:title})).toBeVisible();
    },{settleMs:900,mode:'mocked'});
    expectLitePerformanceBudget(open);await writeLitePerformanceEvidence(info,open);
    const dialog=page.getByRole('dialog',{name:title});
    const navigate=await measureLiteInteraction(page,info,'azure-home-'+kind+'-section-switch',async ()=>{
      await dialog.getByRole('button',{name:kind==='workspace'?'Diagnostics':'History'}).click();
      await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
    },{settleMs:900,mode:'mocked'});
    expectLitePerformanceBudget(navigate);await writeLitePerformanceEvidence(info,navigate);
    const close=await measureLiteInteraction(page,info,'azure-home-'+kind+'-close',async ()=>{
      await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);
    },{settleMs:900,mode:'mocked'});
    expectLitePerformanceBudget(close);await writeLitePerformanceEvidence(info,close);
  });
  test('[interaction] Azure Home '+kind+' move, resize and appearance cost',async ({page},info)=>{
    await page.setViewportSize({width:1280,height:900});
    await installScenario(page,'healthy');await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page,'home');
    await page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View all activity'}).click();
    const title=kind==='workspace'?'Workspace details':'Recent activity';
    const dialog=page.getByRole('dialog',{name:title});
    for(const [name,action] of [
      ['move',async()=>{await dialog.getByRole('button',{name:'Move '+title+' panel'}).focus();await page.keyboard.press('ArrowLeft');}],
      ['resize',async()=>{await dialog.getByRole('button',{name:'Resize '+title+' panel'}).focus();await page.keyboard.press('ArrowLeft');}],
      ['theme',async()=>{await page.evaluate(()=>{const root=document.documentElement;root.dataset.liteTheme=root.dataset.liteTheme==='dark'?'light':'dark';});}],
    ] as const){
      const report=await measureLiteInteraction(page,info,'azure-home-'+kind+'-'+name,action,{settleMs:900,mode:'mocked'});
      expectLitePerformanceBudget(report);await writeLitePerformanceEvidence(info,report);
    }
  });
  test('[interaction] Azure Home '+kind+' mobile detail native scroll cost',async ({page},info)=>{
    await page.setViewportSize({width:390,height:780});
    await installScenario(page,'healthy');await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page,'home');
    await page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View all activity'}).click();
    const dialog=page.getByRole('dialog',{name:kind==='workspace'?'Workspace details':'Recent activity'});
    await dialog.getByRole('button',{name:kind==='workspace'?'Service health':'History'}).click();
    const body=dialog.locator('.lite-home-panel-scroll');
    await body.evaluate((node)=>{const el=document.createElement('div');el.style.height='1400px';el.dataset.perfFiller='true';node.append(el);});
    const report=await measureLiteInteraction(page,info,'azure-home-'+kind+'-native-scroll',async ()=>{
      await body.evaluate((node)=>node.scrollTo({top:260,behavior:'instant'}));
      await expect.poll(()=>body.evaluate((node)=>node.scrollTop)).toBeGreaterThan(220);
      await body.evaluate((node)=>node.scrollTo({top:90,behavior:'instant'}));
      await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
    },{settleMs:900,mode:'mocked'});
    expectLitePerformanceBudget(report);await writeLitePerformanceEvidence(info,report);
  });
}
