import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
// Baseline PNGs intentionally absent. Generate and review during future qualification.
for (const [scenario,name,width] of [
  ['recovery-verified','verified-mobile',390],
  ['recovery-no-backups','first-run-mobile',360],
  ['recovery-restore-blocked','restore-blocked',390],
  ['recovery-projection-too-old','stale',390],
  ['recovery-repository-unavailable','repository-unavailable',390],
  ['recovery-preview-ready','preview-ready-desktop',1440],
] as const) {
  test('Recovery premium screenshot ' + name,async ({page})=>{
    await page.setViewportSize({width,height:880});
    await installScenario(page,scenario);
    await page.goto('/?screen=recovery');
    await waitForLiteScreenToSettle(page,'recovery');
    await expect(page).toHaveScreenshot('recovery-premium-'+name+'.png',{animations:'disabled'});
  });
}
test('Journey selected and Manage Restore visual states',async ({page})=>{
  await installScenario(page,'recovery-preview-ready');
  await page.goto('/?screen=recovery');
  await waitForLiteScreenToSettle(page,'recovery');
  await page.locator('.lite-recovery-premium-stage-grid button').nth(2).click();
  await expect(page).toHaveScreenshot('recovery-premium-journey-expanded.png',{animations:'disabled'});
  await page.getByRole('button',{name:'Manage Recovery'}).click();
  await page.getByRole('dialog',{name:/Manage backups and recovery/i}).getByRole('tab',{name:'Restore'}).click();
  await expect(page).toHaveScreenshot('recovery-premium-restore-manage.png',{animations:'disabled'});
});