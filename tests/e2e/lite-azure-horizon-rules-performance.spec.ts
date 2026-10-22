import {expect,test} from '@playwright/test';
import {installScenario,waitForLiteScreenToSettle} from './lite-test-helpers';
// Supplemental instrumentation; PR #588 hard gates unchanged. NOT RUN.
test('samples Rules first paint, Journey, Manage, section, geometry and simulation',async({page},testInfo)=>{
  await page.setViewportSize({width:1280,height:900});
  await installScenario(page,'rules-enterprise-owner');
  const start=Date.now();
  await page.goto('/?screen=rules');
  await waitForLiteScreenToSettle(page,'rules');
  const firstPaintMs=Date.now()-start;
  const sample=async(label:string,op:()=>Promise<unknown>)=>{
    const before=Date.now();await op();return {label,elapsedMs:Date.now()-before};
  };
  const samples=[];
  samples.push(await sample('journey',()=>page.getByRole('button',{name:/Evaluate:/}).click()));
  samples.push(await sample('manage',()=>page.getByRole('button',{name:'Manage Safety Rules'}).click()));
  const dialog=page.getByRole('dialog',{name:'Manage Safety Rules'});
  await expect(dialog).toBeVisible();
  samples.push(await sample('section',()=>dialog.getByRole('button',{name:'Policies',exact:true}).click()));
  samples.push(await sample('move',async()=>{await dialog.getByRole('button',{name:'Move Safety Rules panel'}).focus();await page.keyboard.press('ArrowLeft');}));
  samples.push(await sample('resize',async()=>{await dialog.getByRole('button',{name:'Resize Safety Rules panel'}).focus();await page.keyboard.press('ArrowLeft');}));
  samples.push(await sample('simulation-view',()=>dialog.getByRole('button',{name:'Test a Change'}).click()));
  const requests=await page.evaluate(()=>performance.getEntriesByType('resource').filter(row=>row.name.includes('/api/lite/')).length);
  await testInfo.attach('azure-rules-perf-samples',{body:JSON.stringify({firstPaintMs,samples,requests},null,2),contentType:'application/json'});
  expect(firstPaintMs).toBeGreaterThanOrEqual(0);
});
