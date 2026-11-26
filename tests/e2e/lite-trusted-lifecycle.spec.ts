import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function openLifecycle(page: Page, scenario = 'system-health-attention') {
  await installScenario(page, scenario);
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  await page.getByRole('button', { name: /Manage System Health/i }).click();
  const dialog = page.getByRole('dialog', { name: /System Health Manage/i });
  await dialog.getByRole('button', { name: 'Updates & protection', exact: true }).click();
  return dialog.locator('section.lite-system-health-manage-section[aria-label="Updates & protection"]');
}
test('historical identity and unknown impact cannot imply installation authority', async ({ page }) => {
  const writes: string[] = [];
  page.on('request', r => { if (r.method() !== 'GET' && r.url().includes('/api/lite/lifecycle/')) writes.push(r.url()); });
  const panel = await openLifecycle(page);
  await expect(panel.getByText('Trust setup required')).toBeVisible();
  await expect(panel.getByText('Impact not confirmed')).toBeVisible();
  await expect(panel.getByText('Not enabled by this foundation')).toBeVisible();
  const report = await new AxeBuilder({ page }).include('[aria-label="Updates & protection"]').analyze();
  expect(report.violations.filter(v => ['critical', 'serious'].includes(v.impact || ''))).toEqual([]);
  expect(writes).toEqual([]);
});
test('preview and cancel do not submit a preference', async ({ page }) => {
  const writes: string[] = [];
  page.on('request', r => { if (r.method() === 'PUT' && r.url().includes('/api/lite/lifecycle/')) writes.push(r.url()); });
  const panel = await openLifecycle(page);
  await panel.getByRole('button', { name: 'Review Recommended' }).click();
  await expect(panel.getByRole('group', { name: 'Review proposed change' })).toBeVisible();
  await panel.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(panel.getByRole('group', { name: 'Review proposed change' })).toHaveCount(0);
  expect(writes).toEqual([]);
});
for (const theme of ['light', 'dark'] as const) {
  test('lifecycle visual reference ' + theme, async ({ page }) => {
    await openLifecycle(page);
    await page.evaluate(t => {
      const root = document.documentElement;
      root.setAttribute('data-lite-theme', t);
      root.setAttribute('data-pocketlab-lite-theme', t === 'dark' ? 'dark' : 'daylight');
      root.classList.toggle('theme-pocket-lite-dark', t === 'dark');
      root.classList.toggle('theme-pocket-lite-daylight', t === 'light');
      root.style.colorScheme = t;
    }, theme);
    // Capture the established System Manage surface, not the full-height
    // scroll content. Element screenshots of the nested section include
    // clipped blank space below the visible sheet and are not a useful visual
    // contract for desktop/mobile review.
    const dialog = page.getByRole('dialog', { name: /System Health Manage/i });
    await expect(dialog).toHaveScreenshot('trusted-lifecycle-' + theme + '.png', { animations: 'disabled' });
  });
}
