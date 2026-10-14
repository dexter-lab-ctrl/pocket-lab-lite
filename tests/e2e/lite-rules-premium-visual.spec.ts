import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function launch(page: Page, scenario: string) {
  await installScenario(page, scenario);
  await page.goto('/?screen=rules');
  await waitForLiteScreenToSettle(page, 'rules');
}
test.describe('Premium Rules — baseline generation DEFERRED until owner-reviewed render', () => {
  test('mobile summary 390', async ({ page }) => {
    await page.setViewportSize({ width:390, height:844 });
    await launch(page, 'rules-enabled');
    await expect(page).toHaveScreenshot('rules-premium-mobile.png', { animations:'disabled' });
  });
  test('desktop summary 1440', async ({ page }) => {
    await page.setViewportSize({ width:1440, height:900 });
    await launch(page, 'rules-present');
    await expect(page).toHaveScreenshot('rules-premium-desktop.png', { animations:'disabled' });
  });
  test('Journey expanded', async ({ page }) => {
    await launch(page, 'rules-enabled');
    await page.getByRole('button', { name: /Check Evaluate/i }).click();
    await expect(page).toHaveScreenshot('rules-premium-journey-expanded.png', { animations:'disabled' });
  });
  for (const [scenario, filename] of [
    ['rules-validation-error','rules-premium-degraded.png'],
    ['rules-enterprise-owner','rules-premium-enterprise.png'],
    ['rules-execution-pending','rules-premium-activation.png'],
  ]) {
    test('scenario: ' + scenario, async ({ page }) => {
      await launch(page, scenario);
      await expect(page).toHaveScreenshot(filename, { animations:'disabled' });
    });
  }
  test('Manage panel', async ({ page }) => {
    await launch(page, 'rules-enabled');
    await page.getByRole('button', { name:'Manage Safety Rules' }).click();
    await expect(page).toHaveScreenshot('rules-premium-manage.png', { animations:'disabled' });
  });
  test('Decision Insight when backend provides decision', async ({ page }) => {
    await launch(page, 'rules-present');
    const trigger = page.getByLabel('Latest Decision').getByRole('button', { name:'Explain this' });
    if (await trigger.count()) {
      await trigger.click();
      await expect(page).toHaveScreenshot('rules-premium-decision-insight.png', { animations:'disabled' });
    }
  });
  test('long text at narrow width', async ({ page }) => {
    await page.setViewportSize({ width:320, height:850 });
    await launch(page, 'rules-premium-long');
    await page.evaluate(() => { document.documentElement.style.fontSize='200%'; });
    await expect(page).toHaveScreenshot('rules-premium-long-text.png', { animations:'disabled' });
  });
});
