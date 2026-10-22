import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
// Supplemental samples only. PR #588's established limits remain authoritative and unchanged.
for(const theme of ['light','dark'] as const) {
  for(const scenario of ['identity-summary','identity-premium-multiple','identity-enterprise-owner']) {
    test(`Identity interaction samples: ${theme} ${scenario}`,async({page})=>{
      await page.setViewportSize({width:1280,height:900});
      await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
      await installScenario(page,scenario);
      const start=Date.now();
      await page.goto('/?screen=identity');
      await waitForLiteScreenToSettle(page,'identity');
      const firstPaintMs=Date.now()-start;
      const openStart=Date.now();
      await page.getByRole('button',{name:/^Manage Access$/i}).first().click();
      const panel=page.getByRole('dialog',{name:/Manage access/i});
      await expect(panel).toBeVisible();
      const manageOpenMs=Date.now()-openStart;
      const switchStart=Date.now();
      await panel.getByRole('button',{name:'Passkeys',exact:true}).click();
      await panel.getByRole('button',{name:'Sessions',exact:true}).click();
      await panel.getByRole('button',{name:'Activity',exact:true}).click();
      const sectionSwitchMs=Date.now()-switchStart;
      const movementStart=Date.now();
      const move=panel.getByRole('button',{name:'Move access panel'});
      await move.focus();
      await page.keyboard.press('ArrowLeft');
      const moveMs=Date.now()-movementStart;
      const measurements={firstPaintMs,manageOpenMs,sectionSwitchMs,moveMs};
      expect(Object.values(measurements).every(n=>Number.isFinite(n)&&n>=0)).toBe(true);
      test.info().annotations.push({type:'identity-horizon-performance-sample',description:JSON.stringify(measurements)});
    });
  }
}
