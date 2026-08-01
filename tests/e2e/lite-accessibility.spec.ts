import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { installScenario, LITE_TABS, openTab } from './lite-test-helpers';

test('current Lite tabs have no serious or critical Axe violations', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  for (const [label, screenId] of LITE_TABS) {
    await openTab(page, label, screenId);
    const result = await new AxeBuilder({ page })
      .include(`[data-lite-screen-id="${screenId}"]`)
      .disableRules(['color-contrast'])
      .analyze();
    const blocking = result.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''));
    expect(blocking, `${screenId}: ${JSON.stringify(blocking, null, 2)}`).toEqual([]);
  }
});
