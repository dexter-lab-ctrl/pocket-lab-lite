import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Mock-only: no NATS, shell, destructive operation or real device mutation.
async function openHome(page: import('@playwright/test').Page, preference: string, scenario = 'healthy') {
  await page.addInitScript((value) => {
    if (!localStorage.getItem('pocketlab:appearance')) localStorage.setItem('pocketlab:appearance', value);
  }, preference);
  await installScenario(page, scenario);
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
}

for (const width of [320, 360, 375, 390, 430, 768, 1024, 1440]) {
  for (const preference of ['light','dark'] as const) {
    test(`Azure Home ${width}px / ${preference}: responsive and truthful`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 500 ? 780 : 950 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await openHome(page, preference);
      await expect(page.locator('html')).toHaveAttribute('data-lite-theme', preference);
      await expect(page.locator('[data-azure-horizon-home="true"]')).toBeVisible();
      for (const area of ['Apps','Devices','Safety','Backups']) {
        await expect(page.getByRole('button', { name: 'Open ' + area })).toBeVisible();
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2);
      expect(overflow, `${width}px horizontal document overflow`).toBe(false);
    });
  }
}

test('Azure Light/Dark/System persists and tracks live OS changes', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await openHome(page, 'system');
  await expect(page.locator('html')).toHaveAttribute('data-lite-theme', 'dark');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).toHaveAttribute('data-lite-theme', 'light');
  await page.getByRole('combobox', { name: 'Appearance' }).selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-lite-theme', 'dark');
  await page.reload();
  await waitForLiteScreenToSettle(page, 'home');
  await expect(page.locator('html')).toHaveAttribute('data-lite-theme', 'dark');
  expect(await page.evaluate(() => localStorage.getItem('pocketlab:appearance'))).toBe('dark');
  expect(await page.locator('html').evaluate((node) => getComputedStyle(node).colorScheme)).toBe('dark');
});

test('Azure theme reaches portal dialogs and returns focus', async ({ page }) => {
  await openHome(page, 'dark');
  const launcher = page.getByRole('button', { name: 'Workspace details' });
  await launcher.focus();
  await launcher.click();
  const details = page.getByRole('dialog', { name: 'Workspace details' });
  await expect(details).toBeVisible();
  await expect(page.locator('[data-lite-overlay-portal]')).not.toHaveClass(/theme-pocket-lite-daylight/);
  for (const section of ['Overview','Service health','Updates','Diagnostics']) {
    await details.getByRole('button', { name: section, exact: true }).click();
    await expect(details.getByRole('button', { name: section, exact: true })).toHaveAttribute('aria-current', 'page');
  }
  await page.keyboard.press('Escape');
  await expect(details).toHaveCount(0);
  await expect(launcher).toBeFocused();
});

test('Azure recent activity keeps backend review action on demand', async ({ page }) => {
  await openHome(page, 'light');
  await page.getByRole('button', { name: /View activity/i }).click();
  const details = page.getByRole('dialog', { name: 'Recent activity' });
  await expect(details).toBeVisible();
  await details.getByRole('button', { name: 'History', exact: true }).click();
  await expect(details.getByText(/Marking history reviewed changes only your private review position/i)).toBeVisible();
});

test('Azure saved and unavailable states do not report fabricated live counts', async ({ page }) => {
  await openHome(page, 'dark', 'offline-saved');
  await expect(page.locator('[data-azure-horizon-home]')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Open Backups' })).toBeVisible();
  await expect(page.getByText('6 apps')).toHaveCount(0);
  await expect(page.getByText('4 devices')).toHaveCount(0);
});

for (const theme of ['light','dark'] as const) {
  test(`Azure WCAG AA ${theme}: Home, primary navigation and Details`, async ({ page }) => {
    await openHome(page, theme);
    let results = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
    expect(results.violations, JSON.stringify(results.violations)).toEqual([]);
    await page.getByRole('button', { name: 'Workspace details' }).click();
    results = await new AxeBuilder({ page }).include('[role="dialog"]').withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
    expect(results.violations, JSON.stringify(results.violations)).toEqual([]);
  });
}

test('Azure 200% text and reduced motion keep mobile details usable', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openHome(page, 'dark');
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
  await page.getByRole('button', { name: 'Workspace details' }).click();
  const details = page.getByRole('dialog', { name: 'Workspace details' });
  await expect(details).toBeVisible();
  const rect = await details.boundingBox();
  expect(rect).not.toBeNull();
  if (rect) {
    expect(rect.x).toBeGreaterThanOrEqual(-2);
    expect(rect.x + rect.width).toBeLessThanOrEqual(322);
  }
});
