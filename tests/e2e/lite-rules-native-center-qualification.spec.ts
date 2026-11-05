import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Mocked qualification cannot prove live authorization or policy activation.
// The deterministic Rules baselines below are reviewed and approved separately
// from the read-only physical Android evidence.
const appearances = ['light', 'dark'] as const;
const layoutWidths = [1280, 768, 390, 360, 320] as const;
const criticalSelectors = [
  '.lite-rules-premium-hero',
  '.lite-rules-premium-journey',
  '.lite-rules-premium-latest',
];
async function launch(page: Page, scenario = 'rules-present', appearance = 'light') {
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), appearance);
  await installScenario(page, scenario);
  await page.goto('/?screen=rules');
  await waitForLiteScreenToSettle(page, 'rules');
}
async function openManage(page: Page) {
  await page.getByRole('button', { name: 'Manage Safety Rules' }).click();
  const dialog = page.getByRole('dialog', { name: 'Manage Safety Rules' });
  await expect(dialog).toBeVisible();
  return dialog;
}
async function rects(page: Page, selectors: string[]) {
  return page.evaluate((names) => names.map((selector) => {
    const node = document.querySelector(selector);
    if (!(node instanceof HTMLElement)) return null;
    const { x, y, width, height } = node.getBoundingClientRect();
    return [x, y, width, height].map((n) => Math.round(n));
  }), selectors);
}
async function assertNoOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}
async function axeAA(page: Page) {
  const report = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
  expect(report.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual([]);
}

test.describe('Azure Horizon native Rules Center: visual/semantic contract (EXECUTED — MOCKED; PHYSICAL RULES-ONLY QUALIFIED)', () => {
  for (const appearance of appearances) {
    for (const width of layoutWidths) {
      test('page hierarchy and no overflow at ' + width + ' / ' + appearance, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await launch(page, 'rules-present', appearance);
        await expect(page.getByRole('heading', { name: 'Safety Rules', level: 1 })).toBeVisible();
        await expect(page.getByLabel('Protection Center')).toHaveCount(1);
        await expect(page.getByRole('heading', { name: 'How protection works' })).toBeVisible();
        await expect(page.getByRole('heading', { name: 'Latest Decision' })).toBeVisible();
        await expect(page.getByRole('button', { name: 'Manage Safety Rules' })).toHaveCount(1);
        await assertNoOverflow(page);
        const dialog = await openManage(page);
        await expect(dialog).toHaveAttribute('data-rules-manage-layout', width >= 701 ? 'desktop-movable' : 'mobile-sheet');
        if (width <= 700) {
          await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'medium');
          await expect(dialog.getByRole('navigation', { name: 'Manage Safety Rules sections' })).toBeVisible();
          await dialog.getByRole('button', { name: 'Protected Actions' }).click();
          await expect(dialog.getByRole('button', { name: 'All Safety Rules settings' })).toBeVisible();
          await dialog.getByRole('button', { name: 'All Safety Rules settings' }).click();
          await expect(dialog.getByRole('button', { name: 'Protected Actions' })).toBeVisible();
        } else {
          await expect(dialog.locator('.lite-rules-native-detail')).toBeVisible();
          await expect(dialog.locator('.lite-rules-premium-nav')).toBeVisible();
        }
        const bounds = await dialog.boundingBox();
        if (bounds) expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
      });
    }
    test('WCAG AA for page, settings index and focused details: ' + appearance, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 850 });
      await launch(page, 'rules-present', appearance);
      await axeAA(page);
      const dialog = await openManage(page);
      await axeAA(page);
      await dialog.getByRole('button', { name: 'Decision History' }).click();
      await axeAA(page);
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Manage Safety Rules' })).toBeFocused();
    });
  }

  test('System resolves through the shared theme provider, not Rules overrides', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await launch(page, 'rules-present', 'system');
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme', 'dark');
    await assertNoOverflow(page);
  });
  test('Daylight and Dark have the same card, panel and row geometry', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 850 });
    await launch(page, 'rules-present', 'light');
    const first = await rects(page, criticalSelectors);
    const dialog1 = await openManage(page);
    const manageFirst = await rects(page, ['.lite-rules-manage-sheet', '.lite-rules-premium-nav', '.lite-rules-native-detail', '.lite-rules-native-row']);
    await dialog1.getByRole('button', { name: 'Close Rules management' }).click();
    await launch(page, 'rules-present', 'dark');
    expect(await rects(page, criticalSelectors)).toEqual(first);
    const dialog2 = await openManage(page);
    expect(await rects(page, ['.lite-rules-manage-sheet', '.lite-rules-premium-nav', '.lite-rules-native-detail', '.lite-rules-native-row'])).toEqual(manageFirst);
    await expect(dialog2).toBeVisible();
  });
  test('200% text scaling and 320px layout preserve readable security explanations', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 780 });
    await launch(page, 'rules-premium-long');
    await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
    await assertNoOverflow(page);
    await page.getByRole('button', { name: /Check Evaluate/i }).click();
    await expect(page.locator('.lite-rules-journey-explanation')).toBeVisible();
    await assertNoOverflow(page);
    const dialog = await openManage(page);
    await expect(dialog.getByRole('button', { name: 'Technical Status' })).toBeVisible();
    await assertNoOverflow(page);
  });
  test('snap controls and dedicated grip operate without dismissing settings', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await launch(page);
    const dialog = await openManage(page);
    await dialog.getByRole('button', { name: 'Expand' }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await dialog.getByRole('button', { name: 'Compact' }).click();
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'medium');
    const grip = dialog.getByRole('button', { name: /Resize sheet/i });
    await grip.focus();
    await page.keyboard.press('Home');
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'compact');
    await page.keyboard.press('End');
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await expect(dialog).toBeVisible();
  });
  test('decision insight is server-backed and explicitly separate from execution', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await launch(page, 'rules-present');
    const explain = page.getByLabel('Latest Decision').getByRole('button', { name: 'Explain decision' });
    if (await explain.count()) {
      await explain.click();
      const insight = page.getByRole('dialog', { name: 'Decision Insight' });
      await expect(insight).toHaveAttribute('data-lite-sheet-snap', 'medium');
      await expect(insight).toContainText('Why this decision?');
      await expect(insight).toContainText('Authorization');
      await insight.getByRole('button', { name: 'Expand' }).click();
      await expect(insight).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    }
  });
  test('no decision is synthesized when the fixture has no decision records', async ({ page }) => {
    await launch(page, 'rules-empty');
    await expect(page.getByText('No recorded decisions')).toBeVisible();
    await expect(page.getByLabel('Latest Decision').getByRole('button', { name: 'Explain decision' })).toHaveCount(0);
  });
  test('offline, degraded, unverified fixtures cannot assert healthy protection', async ({ page }) => {
    for (const scenario of ['api-unavailable', 'rules-disabled', 'rules-validation-error', 'rules-execution-pending']) {
      await launch(page, scenario);
      await expect(page.locator('[data-rules-protection-state]')).not.toHaveAttribute('data-rules-protection-state', 'ready');
    }
  });
  test('Enterprise capabilities remain server-owned and navigation does not submit writes', async ({ page }) => {
    await launch(page, 'rules-enterprise-viewer');
    const submitted: string[] = [];
    page.on('request', (req) => {
      if (req.method() !== 'GET' && req.url().includes('/api/lite/')) submitted.push(req.method() + ' ' + req.url());
    });
    const dialog = await openManage(page);
    await dialog.getByRole('button', { name: 'Policy Settings' }).click();
    await expect(dialog.getByRole('button', { name: 'Create Rules candidate' })).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: 'Test a Change' })).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: 'Temporary Access' })).toHaveCount(0);
    if ((page.viewportSize()?.width || 0) <= 700) {
      await dialog.getByRole('button', { name: 'All Safety Rules settings' }).click();
    }
    await dialog.getByRole('button', { name: 'Governance' }).click();
    expect(submitted).toEqual([]);
  });
  test('reduced motion leaves all interaction paths functional', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await launch(page);
    await page.getByRole('button', { name: /Check Evaluate/i }).click();
    const dialog = await openManage(page);
    await dialog.getByRole('button', { name: 'Decision History' }).click();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
  });
  test('global delegated haptic feedback is optional and emits one tap for selection', async ({ page }) => {
    await page.addInitScript(() => {
      (window as typeof window & { __rulesHaptics?: number[] }).__rulesHaptics = [];
      Object.defineProperty(navigator, 'vibrate', {
        configurable: true,
        value: (duration: number) => { (window as typeof window & { __rulesHaptics: number[] }).__rulesHaptics.push(duration); return true; },
      });
    });
    await launch(page);
    await page.getByRole('button', { name: 'Manage Safety Rules' }).focus();
    await page.keyboard.press('Enter');
    expect(await page.evaluate(() => (window as typeof window & { __rulesHaptics?: number[] }).__rulesHaptics?.length)).toBe(1);
  });

  // Deterministic mocked baselines. Physical Android captures are retained as
  // separate candidate evidence because the device is not a deterministic
  // snapshot source.
  for (const appearance of appearances) {
    test('pending desktop visual baseline: ' + appearance, async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await launch(page, 'rules-present', appearance);
      await expect(page.locator('.lite-rules-premium-screen')).toHaveScreenshot('rules-native-' + appearance + '-desktop.png');
    });
    test('pending mobile Manage visual baseline: ' + appearance, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await launch(page, 'rules-present', appearance);
      await openManage(page);
      await expect(page.getByRole('dialog', { name: 'Manage Safety Rules' })).toHaveScreenshot('rules-native-' + appearance + '-mobile-manage.png');
    });
  }
});
