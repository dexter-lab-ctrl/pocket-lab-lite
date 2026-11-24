import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

const widths = [320, 360, 390, 430, 768, 1024, 1280, 1440];
const themes = ['light', 'dark'] as const;

async function applyVisualTheme(page: Page, theme: 'light' | 'dark') {
  await page.evaluate(nextTheme => {
    const root = document.documentElement;
    root.setAttribute('data-lite-theme', nextTheme);
    root.setAttribute('data-pocketlab-lite-theme', nextTheme === 'dark' ? 'dark' : 'daylight');
    root.classList.toggle('theme-pocket-lite-dark', nextTheme === 'dark');
    root.classList.toggle('theme-pocket-lite-daylight', nextTheme === 'light');
    root.style.colorScheme = nextTheme;
  }, theme);
  // The shared Home refinement animates the page shell when the legacy theme
  // class changes. Let that transition settle before asserting cross-theme
  // geometry or capturing a canonical baseline.
  await page.waitForTimeout(500);
}

for (const width of widths) {
  for (const theme of themes) {
    test(`H5 System Health overview ${width}px ${theme} theme`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await installScenario(page, 'system-health-mixed');
      await page.goto('/?screen=system-health');
      await waitForLiteScreenToSettle(page, 'system-health');
      await applyVisualTheme(page, theme);
      await expect(page.locator('[data-system-health-page="true"]')).toHaveScreenshot(
        `system-health-overview-${width}-${theme}.png`, { animations: 'disabled' },
      );
    });
  }
}

for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 900 }]) {
  for (const theme of themes) {
    test(`H5 Manage geometry ${viewport.width}px ${theme} theme`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await installScenario(page, 'system-health-many');
      await page.goto('/?screen=system-health');
      await waitForLiteScreenToSettle(page, 'system-health');
      await applyVisualTheme(page, theme);
      await page.getByRole('button', { name: 'Manage System Health' }).click();
      const dialog = page.getByRole('dialog', { name: /System Health Manage/i });
      await expect(dialog).toBeVisible();
      await expect(dialog).toHaveScreenshot(
        `system-health-manage-${viewport.width}-${theme}.png`, { animations: 'disabled' },
      );
    });
  }
}

// The geometry contract must remain the same when only semantic colors change.
test('light/dark theme switching does not change the overview card geometry', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installScenario(page, 'system-health-mixed');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  const capture = async (theme: 'light' | 'dark') => {
    await applyVisualTheme(page, theme);
    return page.locator('[data-health-overview]').evaluate(element => {
      const { x, y, width, height } = element.getBoundingClientRect();
      return { x, y, width, height };
    });
  };
  expect(await capture('dark')).toEqual(await capture('light'));
});
