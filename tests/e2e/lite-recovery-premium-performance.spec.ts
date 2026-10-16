import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
test('records Recovery first paint, Journey selection, Manage and focused details',async ({page},testInfo)=>{
  await installScenario(page,'recovery-preview-ready');
  const start=Date.now();await page.goto('/?screen=recovery');await waitForLiteScreenToSettle(page,'recovery');
  const firstPaintMs=Date.now()-start;const journeyStart=Date.now();
  await page.locator('.lite-recovery-premium-stage-grid button').first().click();
  const journeyMs=Date.now()-journeyStart;
  const manageStart=Date.now();await page.getByRole('button',{name:'Manage Recovery'}).click();
  await expect(page.getByRole('dialog',{name:/Manage backups and recovery/i})).toBeVisible();
  const manageMs=Date.now()-manageStart;
  const requests=await page.evaluate(()=>performance.getEntriesByType('resource').map(e=>e.name).filter(s=>s.includes('/api/lite/recovery')));
  await testInfo.attach('recovery-premium-timings',{body:JSON.stringify({firstPaintMs,journeyMs,manageMs,requests},null,2),contentType:'application/json'});
  // Measurements only. Existing owner-owned performance limits remain unchanged.
  expect(firstPaintMs).toBeGreaterThanOrEqual(0);
});