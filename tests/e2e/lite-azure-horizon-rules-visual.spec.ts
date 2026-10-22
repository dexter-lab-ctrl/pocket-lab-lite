import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
// DEFINED — CAPTURE AND APPROVAL DEFERRED. Baselines intentionally not generated.
async function open(page:Page, scenario:string, theme:string){
  await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
  await installScenario(page,scenario);
  await page.goto('/?screen=rules');
  await waitForLiteScreenToSettle(page,'rules');
}
for(const theme of ['light','dark','system']) {
  for(const scenario of ['rules-enabled','rules-validation-error','rules-present','rules-execution-pending','rules-enterprise-owner','rules-enterprise-viewer']) {
    test('Azure Rules desktop '+theme+' '+scenario,async({page})=>{
      await page.setViewportSize({width:1440,height:900});
      await open(page,scenario,theme);
      await expect(page).toHaveScreenshot('azure-rules-'+theme+'-'+scenario+'.png',{animations:'disabled'});
    });
  }
  for(const width of [320,360,375,390,430,768]) {
    test('Azure Rules mobile '+theme+' '+width,async({page})=>{
      await page.setViewportSize({width,height:844});
      await open(page,'rules-premium-long',theme);
      await expect(page).toHaveScreenshot('azure-rules-'+theme+'-width-'+width+'.png',{animations:'disabled'});
    });
  }
  for(const section of ['Policies','Test a Change','Requests','Temporary Access','Revision & Recovery']) {
    test('Azure Rules Enterprise Manage '+theme+' '+section,async({page})=>{
      await page.setViewportSize({width:1280,height:900});
      await open(page,'rules-enterprise-owner',theme);
      await page.getByRole('button',{name:'Manage Safety Rules'}).click();
      await page.getByRole('dialog',{name:'Manage Safety Rules'}).getByRole('button',{name:section,exact:true}).click();
      await expect(page).toHaveScreenshot('azure-rules-'+theme+'-'+section.toLowerCase().replaceAll(' ','-').replaceAll('&','and')+'.png',{animations:'disabled'});
    });
  }
}
test('Azure Rules desktop resized Manage',async({page})=>{
  await page.setViewportSize({width:1280,height:900});
  await open(page,'rules-enabled','dark');
  await page.getByRole('button',{name:'Manage Safety Rules'}).click();
  const dialog=page.getByRole('dialog',{name:'Manage Safety Rules'});
  await dialog.getByRole('button',{name:'Resize Safety Rules panel'}).focus();
  await page.keyboard.press('ArrowLeft');
  await expect(page).toHaveScreenshot('azure-rules-resized-manage.png',{animations:'disabled'});
});
test('Azure Rules Decision Insight',async({page})=>{
  await open(page,'rules-present','dark');
  const explain=page.getByLabel('Latest Decision').getByRole('button',{name:'Explain this'});
  if(await explain.count()){await explain.click();await expect(page).toHaveScreenshot('azure-rules-decision-insight.png',{animations:'disabled'});}
});
