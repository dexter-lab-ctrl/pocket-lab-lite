import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Supplemental PR #588 interaction samples — NOT RUN. Existing frame/budget gate stays authoritative.
// This adds evidence fields; it does not relax or replace existing 60 FPS checks.
for (const theme of ['light','dark'] as const) {
  for (const width of [390,1280]) {
    test(`Apps premium interaction performance ${theme} ${width}`,async({page})=>{
      await page.setViewportSize({width,height:850});
      await page.addInitScript(pref=>localStorage.setItem('pocketlab:appearance',pref),theme);
      await installScenario(page,'catalog-ready');
      await page.goto('/?screen=catalog');
      await waitForLiteScreenToSettle(page,'catalog');
      const result=await page.evaluate(async()=>{
        const samples:number[]=[];
        await new Promise<void>((resolve)=>{
          let previous:number|undefined;let frames=0;
          const sample=(timestamp:number)=>{
            if(previous!==undefined)samples.push(timestamp-previous);
            previous=timestamp;frames++;
            if(frames<42) requestAnimationFrame(sample);else resolve();
          };
          requestAnimationFrame(sample);
        });
        return {frameCount:samples.length,over16_7ms:samples.filter(v=>v>16.7).length,
          p95Ms:[...samples].sort((a,b)=>a-b)[Math.max(0,Math.floor(samples.length*.95)-1)]||0};
      });
      const started=Date.now();
      const manageButton=page.locator('.lite-catalog-app-card').getByRole('button',{name:'Manage',exact:true}).first();
      await manageButton.click();
      const panel=page.getByRole('dialog',{name:/Manage PhotoPrism/i});
      await expect(panel).toBeVisible();
      const manageOpenMs=Date.now()-started;
      if(width>=701){
        const move=panel.getByRole('button',{name:'Move app management panel'});
        await move.focus();await page.keyboard.press('ArrowLeft');
        const grip=panel.getByRole('button',{name:'Resize app management panel'});
        await grip.focus();await page.keyboard.press('ArrowDown');
      }
      expect(result.frameCount).toBeGreaterThan(0);
      test.info().annotations.push({type:'azure-apps-polish-perf-evidence',description:JSON.stringify({theme,width,manageOpenMs,...result})});
    });
  }
}
