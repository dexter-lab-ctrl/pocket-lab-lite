import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// P6: AUTHORED — NOT EXECUTED. Mocked only; no Server Phone involved.
async function openHome(page: Page, scenario = 'healthy', theme = 'light') {
  await page.addInitScript((appearance) => localStorage.setItem('pocketlab:appearance', appearance), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
}

async function dimensions(page: Page, selectors: string[]) {
  return page.evaluate((items) => items.map((selector) => {
    const element = document.querySelector(selector);
    if (!element) throw Error('Missing Home geometry: ' + selector);
    const { x, y, width, height } = element.getBoundingClientRect();
    return { x, y, width, height };
  }), selectors);
}

test.describe('Azure Horizon Home premium refinement — mocked qualification deferred', () => {
  for (const width of [320, 390, 768, 1280, 1440]) {
    test(`Home geometry is readable at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 820 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await openHome(page);
      await expect(page.locator('[data-home-destination]')).toHaveCount(4);
      await expect(page.locator('[data-home-hero-state]')).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)).toBe(false);
      if (width <= 390) {
        const columns = await page.locator('.lite-home-overview-grid').evaluate((el) =>
          getComputedStyle(el).gridTemplateColumns.split(' ').length);
        expect(columns).toBe(2);
      }
    });
  }

  test('Light, Dark and System share page and nested panel geometry', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 880 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await openHome(page, 'healthy', 'system');
    const targets = ['.lite-home-command-hero', '.lite-home-overview-grid',
      '.lite-home-overview-tile', '.lite-home-activity-preview'];
    const light = await dimensions(page, targets);
    await page.emulateMedia({ colorScheme: 'dark' });
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme', 'dark');
    const dark = await dimensions(page, targets);
    light.forEach((item, index) => {
      for (const key of ['x','y','width','height'] as const) {
        expect(Math.abs(item[key] - dark[index][key])).toBeLessThanOrEqual(1.5);
      }
    });
    await page.getByRole('button', { name: 'Workspace details' }).click();
    const panel = page.getByRole('dialog', { name: 'Workspace details' });
    const panelSelectors = ['.lite-home-details-panel', '.lite-home-settings-row',
      '.lite-home-settings-detail', '.lite-home-panel-scroll'];
    const darkPanel = await dimensions(page, panelSelectors);
    await page.emulateMedia({ colorScheme: 'light' });
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme', 'light');
    const lightPanel = await dimensions(page, panelSelectors);
    darkPanel.forEach((item, index) => {
      for (const key of ['width','height'] as const)
        expect(Math.abs(item[key] - lightPanel[index][key])).toBeLessThanOrEqual(1.5);
    });
  });

  test('Authoritative device attention navigates only to Devices', async ({ page }) => {
    await openHome(page, 'lifecycle-attention');
    await expect(page.locator('[data-home-destination="devices"]')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Restart Tailscale' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Open Devices' }).click();
    await expect(page.getByRole('heading', { name: 'Devices', exact: true })).toBeVisible();
  });

  test('Responsive workspace navigation retains Back, focus and shared snap controls', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await openHome(page, 'healthy', 'dark');
    const opener = page.getByRole('button', { name: 'Workspace details' });
    await opener.focus();
    await opener.click();
    const panel = page.getByRole('dialog', { name: 'Workspace details' });
    await expect(panel).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await panel.getByRole('button', { name: 'Compact' }).click();
    await expect(panel).toHaveAttribute('data-lite-sheet-snap', 'compact');
    await panel.getByRole('button', { name: 'Expand' }).click();
    await expect(panel).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await panel.getByRole('button', { name: 'Diagnostics' }).click();
    await expect(panel.getByRole('region', { name: 'Diagnostics' })).toBeVisible();
    await panel.getByRole('button', { name: /All workspace details sections/ }).click();
    await expect(panel.getByRole('button', { name: 'Diagnostics' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(opener).toBeFocused();
  });

  test('Desktop Move, Resize, Reset and grouped index remain keyboard usable', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openHome(page, 'healthy', 'light');
    await page.getByRole('button', { name: 'Workspace details' }).click();
    const panel = page.getByRole('dialog', { name: 'Workspace details' });
    await panel.getByRole('button', { name: 'Move Workspace details panel' }).focus();
    await page.keyboard.press('ArrowRight');
    await panel.getByRole('button', { name: 'Resize Workspace details panel' }).focus();
    await page.keyboard.press('ArrowLeft');
    await panel.getByRole('button', { name: /Reset Workspace details position and size/ }).click();
    await panel.getByRole('button', { name: 'Service health' }).click();
    await expect(panel.getByRole('region', { name: 'Service health' })).toBeVisible();
    expect(await panel.evaluate((node) => node.scrollWidth > node.clientWidth + 2)).toBe(false);
  });

  test('Activity history, saved mode and review remain backend-owned', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await openHome(page, 'offline-saved', 'dark');
    await expect(page.locator('[data-home-hero-state]')).not.toHaveAttribute('data-home-hero-state', 'ready');
    await page.getByRole('button', { name: /View all activity/ }).click();
    const panel = page.getByRole('dialog', { name: 'Recent activity' });
    await panel.getByRole('button', { name: 'History' }).click();
    await expect(panel.getByText(/Reconnect to confirm a new review position/)).toBeVisible();
  });

  test('Home, nested workspace and activity surfaces have no serious WCAG violations', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await openHome(page, 'healthy', 'dark');
    let result = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
    expect(result.violations.filter((v) => ['critical','serious'].includes(v.impact || ''))).toEqual([]);
    for (const name of ['Workspace details','View all activity']) {
      await page.getByRole('button', { name }).click();
      result = await new AxeBuilder({ page }).include('[role="dialog"]')
        .withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
      expect(result.violations.filter((v) => ['critical','serious'].includes(v.impact || ''))).toEqual([]);
      await page.keyboard.press('Escape');
    }
  });

  // Baselines will be captured and reviewed in the separate qualification session.
  for (const theme of ['light','dark'] as const) {
    test.skip(`PENDING baseline: Home hero, four cards, workspace/activity nested views — ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 800 });
      await openHome(page, 'healthy', theme);
      await expect(page.locator('.lite-home-refined')).toHaveScreenshot(`home-premium-${theme}.png`);
    });
  }
});
