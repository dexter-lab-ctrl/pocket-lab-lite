import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import {
  expectLitePerformanceBudget, installLiteFrameSampler,
  measureLiteInteraction, writeLitePerformanceEvidence,
} from './lite-performance-helpers';

// PR #588 performance thresholds are unchanged. DEV-PC mocked qualification is executed.
// Candidate Android device, A/B/A attribution and physical frame budget remain blocked by CDP transport.
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


// P6: shared PR #634 mobile snap performance. DEV-PC mocked qualification is executed.
// Existing PR #588/#589 budget helpers remain unchanged; physical ARM64 qualification is blocked.
test('[interaction] Command Home mobile Compact → Expand snap interaction', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await page.getByRole('button', { name: 'Workspace details' }).click();
  const dialog = page.getByRole('dialog', { name: 'Workspace details' });
  const compact = await measureLiteInteraction(page, info, 'home-premium-mobile-compact', async () => {
    await dialog.getByRole('button', { name: 'Compact' }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'compact');
  }, { settleMs: 900, mode: 'mocked' });
  expectLitePerformanceBudget(compact);
  await writeLitePerformanceEvidence(info, compact);
  const expanded = await measureLiteInteraction(page, info, 'home-premium-mobile-expanded', async () => {
    await dialog.getByRole('button', { name: 'Expand' }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await dialog.getByRole('button', { name: 'Expand' }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'expanded');
  }, { settleMs: 900, mode: 'mocked' });
  expectLitePerformanceBudget(expanded);
  await writeLitePerformanceEvidence(info, expanded);
});
