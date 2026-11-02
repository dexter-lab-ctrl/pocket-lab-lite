import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import {
  expectLitePerformanceBudget, installLiteFrameSampler,
  measureLiteInteraction, writeLitePerformanceEvidence,
} from './lite-performance-helpers';

// PR #588 performance thresholds are unchanged. AUTHORED — NOT RUN.
// Candidate Android device, A/B/A attribution and physical frame budget remain deferred.
test.beforeEach(async ({page}) => { await installLiteFrameSampler(page); });
for (const kind of ['workspace','activity'] as const) {
  test('[interaction] Command Home '+kind+' grouped settings open, navigate and return',async ({page},info)=>{
    await page.setViewportSize({width:390,height:780});
    await installScenario(page,'healthy');
    await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page,'home');
    const title=kind==='workspace'?'Workspace details':'Recent activity';
    const open = await measureLiteInteraction(page,info,'command-'+kind+'-open',async ()=>{
      await page.getByRole('button',{name:kind==='workspace'?'Workspace details':'View all activity'}).click();
      await expect(page.getByRole('dialog',{name:title})).toBeVisible();
    },{settleMs:900,mode:'mocked'});
    expectLitePerformanceBudget(open);
    await writeLitePerformanceEvidence(info,open);
    const dialog=page.getByRole('dialog',{name:title});
    const nested=await measureLiteInteraction(page,info,'command-'+kind+'-nested',async ()=>{
      await dialog.getByRole('button',{name:kind==='workspace'?'Service health':'History'}).click();
      await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
    },{settleMs:900,mode:'mocked'});
    expectLitePerformanceBudget(nested);
    await writeLitePerformanceEvidence(info,nested);
    const back=await measureLiteInteraction(page,info,'command-'+kind+'-back',async ()=>{
      await dialog.getByRole('button',{name:kind==='workspace'?/All workspace details sections/:/All activity sections/}).click();
      await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
    },{settleMs:900,mode:'mocked'});
    expectLitePerformanceBudget(back);
    await writeLitePerformanceEvidence(info,back);
    const close=await measureLiteInteraction(page,info,'command-'+kind+'-close',async ()=>{
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
    },{settleMs:900,mode:'mocked'});
    expectLitePerformanceBudget(close);
    await writeLitePerformanceEvidence(info,close);
  });
}
