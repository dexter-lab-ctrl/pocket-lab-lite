import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Supplemental interaction sampling. PR #588's existing budget gate remains
// authoritative; this file neither changes thresholds nor claims qualification.
for (const width of [390,1280]) {
  for (const theme of ['light','dark'] as const) {
    test(`Azure Apps interaction samples: ${width}px ${theme}`,async({page})=>{
      await page.setViewportSize({width,height:850});
      await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
      await installScenario(page,'catalog-ready');
      const started=Date.now();
      await page.goto('/?screen=catalog');
      await waitForLiteScreenToSettle(page,'catalog');
      const firstPaint=Date.now()-started;
      // Native library hides search until it is useful (8+ installed apps).
      // Sample first-card readiness instead; PR #588 remains the hard performance gate.
      const libraryAt=Date.now();
      const card=page.locator('[data-app-library-card]').first();
      await expect(card).toBeVisible();
      const libraryDuration=Date.now()-libraryAt;
      const managedAt=Date.now();
      await page.locator('.lite-catalog-app-card').getByRole('button',{name:'Manage'}).first().click();
      const dialog=page.getByRole('dialog',{name:/Manage PhotoPrism/i});
      await expect(dialog).toBeVisible();
      const manageDuration=Date.now()-managedAt;
      if(width>=701) {
        const control=dialog.getByRole('button',{name:'Move app management panel'});
        await control.focus();
        await page.keyboard.press('ArrowLeft');
      }
      const result={firstPaint,libraryDuration,manageDuration};
      expect(Object.values(result).every(n=>Number.isFinite(n)&&n>=0)).toBe(true);
      test.info().annotations.push({type:'azure-apps-performance-sample',description:JSON.stringify(result)});
    });
  }
}
