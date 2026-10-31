import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Browser, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORING ONLY — qualification and browser rendering were explicitly deferred.
// Fractional pixels and browser text metrics justify a 2px geometry tolerance;
// padding, gap, borders and typography must retain equal computed values.
const GEOMETRY_TOLERANCE_PX = 2;
const VIEWPORTS = [320, 360, 375, 390, 430, 768, 1280, 1440] as const;
const STYLES = [
  'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
  'marginTop', 'marginRight', 'marginBottom', 'marginLeft',
  'gap', 'rowGap', 'columnGap', 'fontFamily', 'fontSize', 'lineHeight',
  'letterSpacing', 'fontWeight', 'borderTopWidth', 'minHeight', 'alignItems',
] as const;
type Theme = 'light' | 'dark' | 'system';

async function appsPage(browser: Browser, width: number, theme: Theme, scenario = 'catalog-ready') {
  const context = await browser.newContext({ viewport: { width, height: width <= 430 ? 780 : 900 } });
  const page = await context.newPage();
  await page.emulateMedia({ colorScheme: theme === 'system' ? 'dark' : 'light', reducedMotion: 'reduce' });
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page, 'catalog');
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator('.lite-catalog-app-card').first()).toBeVisible();
  return page;
}

async function openManage(page: Page) {
  await page.locator('.lite-catalog-app-card').first().getByRole('button', { name: 'Manage', exact: true }).click();
  const manage = page.getByRole('dialog', { name: /Manage / }).first();
  await expect(manage).toBeVisible();
  return manage;
}

async function openPhotos(page: Page) {
  const manage = await openManage(page);
  const photos = manage.getByRole('tab', { name: 'Photos', exact: true });
  if (await photos.count()) await photos.click();
  return manage;
}

async function sampled(page: Page, selector: string) {
  const nodes = page.locator(selector);
  if (!(await nodes.count())) return null;
  return nodes.first().evaluate((node, properties) => {
    const computed = getComputedStyle(node);
    const box = node.getBoundingClientRect();
    const style: Record<string, string> = {};
    for (const key of properties) style[key] = computed.getPropertyValue(key.replace(/[A-Z]/g, (char) => '-' + char.toLowerCase())).trim();
    return {
      style,
      rect: { x: box.x, y: box.y, width: box.width, height: box.height },
      scrollWidth: node.scrollWidth,
      clientWidth: node.clientWidth,
    };
  }, STYLES);
}

async function compareGeometry(light: Page, dark: Page, selectors: readonly string[]) {
  for (const selector of selectors) {
    const [a, b] = await Promise.all([sampled(light, selector), sampled(dark, selector)]);
    expect(Boolean(b), selector + ' presence').toBe(Boolean(a));
    if (!a || !b) continue;
    for (const key of STYLES) {
      expect(b.style[key], selector + ' ' + key).toBe(a.style[key]);
    }
    for (const key of ['x', 'y', 'width', 'height'] as const) {
      expect(Math.abs(b.rect[key] - a.rect[key]), selector + ' rect ' + key).toBeLessThanOrEqual(GEOMETRY_TOLERANCE_PX);
    }
  }
}

async function expectContained(page: Page, width: number) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  for (const selector of ['.lite-catalog-app-card', '.lite-catalog-toolbar', '.lite-catalog-manage-sheet', '.lite-details-panel']) {
    const locator = page.locator(selector).first();
    if (!(await locator.count()) || !(await locator.isVisible())) continue;
    const box = await locator.boundingBox();
    expect(box?.x ?? 0, selector + ' left').toBeGreaterThanOrEqual(-2);
    expect((box?.x ?? 0) + (box?.width ?? 0), selector + ' right').toBeLessThanOrEqual(width + 2);
  }
}

async function expectNestedHeaderContained(page: Page, width: number) {
  const header = page.locator('.lite-details-overlay-layer .lite-details-panel .lite-overlay-head').first();
  await expect(header).toBeVisible();
  const boxes = await header.locator(':scope > *').evaluateAll((nodes) => nodes.map((node) => {
    const box = node.getBoundingClientRect();
    return { left: box.left, right: box.right, width: box.width };
  }));
  for (const box of boxes) {
    expect(box.left, 'nested details header child left').toBeGreaterThanOrEqual(-2);
    expect(box.right, 'nested details header child right').toBeLessThanOrEqual(width + 2);
    expect(box.width, 'nested details header child width').toBeGreaterThan(0);
  }
}

test.describe('Apps Azure Horizon balanced density — IMPLEMENTED, QUALIFICATION NOT RUN', () => {
  for (const width of VIEWPORTS) {
    test('Light, Dark and System computed layout parity at ' + width + 'px', async ({ browser }) => {
      const pages: Page[] = [];
      try {
        for (const theme of ['light', 'dark', 'system'] as const) pages.push(await appsPage(browser, width, theme));
        const [light, dark, system] = pages;
        const catalogSelectors = [
          '.lite-catalog-toolbar', '.lite-catalog-search-field', '.lite-catalog-search-control',
          '.lite-catalog-status-filters', '.lite-catalog-grid', '.lite-catalog-app-card',
          '.lite-catalog-card-top', '.lite-catalog-card-title-row', '.lite-catalog-category',
          '.lite-catalog-app-description', '.lite-catalog-status-badge', '.lite-catalog-actions',
          '.lite-catalog-actions > button',
        ];
        await compareGeometry(light, dark, catalogSelectors);
        await compareGeometry(dark, system, catalogSelectors);
        for (const page of pages) await expectContained(page, width);
        for (const page of pages) await openPhotos(page);
        const manageSelectors = [
          '.lite-catalog-manage-sheet', '.lite-catalog-manage-head',
          '.lite-catalog-manage-current-state', '.lite-catalog-manage-scroll',
          '.lite-catalog-manage-section-tabs', '.lite-catalog-manage-section-hint',
          '.lite-app-action-row', '.lite-app-action-row-copy',
          '.lite-catalog-premium-flow', '.lite-catalog-premium-flow-steps',
          '.lite-catalog-premium-flow-step', '.lite-catalog-premium-flow-step small',
          '.lite-catalog-premium-backup', '.lite-catalog-premium-backup-metrics',
        ];
        await compareGeometry(light, dark, manageSelectors);
        await compareGeometry(dark, system, manageSelectors);
        for (const page of pages) {
          await expectContained(page, width);
          await expect(page.locator('.lite-catalog-manage-sheet')).toHaveAttribute(
            'data-lite-apps-manage-layout', width <= 700 ? 'mobile-sheet' : 'desktop-movable',
          );
        }
        for (const page of pages) {
          const flow = page.getByRole('region', { name: 'Photo workflow' });
          await flow.getByRole('button', { name: 'View details' }).click();
          await expect(page.locator('.lite-app-premium-details')).toBeVisible();
        }
        await compareGeometry(light, dark, [
          '.lite-app-premium-details', '.lite-progressive-details',
          '.lite-progressive-details-summary', '.lite-progressive-detail-section',
        ]);
        await compareGeometry(dark, system, [
          '.lite-app-premium-details', '.lite-progressive-details',
          '.lite-progressive-details-summary', '.lite-progressive-detail-section',
        ]);
        for (const page of pages) {
          await expectContained(page, width);
          await expectNestedHeaderContained(page, width);
        }
      } finally {
        await Promise.all(pages.map((page) => page.context().close()));
      }
    });
  }

  test('long app names, paragraphs and wrapped badges do not cause horizontal overflow or tiny targets', async ({ browser }) => {
    const page = await appsPage(browser, 320, 'dark', 'catalog-multi-app');
    try {
      await page.locator('.lite-catalog-app-card h2').first().evaluate((node) => {
        node.textContent = 'Extremely long self-hosted application name with multiple readable words';
      });
      await page.locator('.lite-catalog-app-description').first().evaluate((node) => {
        node.textContent = 'A much longer description that wraps naturally, retains the existing line-clamp contract, and never pushes the action footer off-screen.';
      });
      await expectContained(page, 320);
      const buttons = page.locator('.lite-catalog-app-card').first().locator('button');
      for (const button of await buttons.all()) {
        if (!(await button.isVisible())) continue;
        const box = await button.boundingBox();
        expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
      }
    } finally { await page.context().close(); }
  });

  for (const scenario of ['catalog-ready', 'catalog-install-available', 'app-action-failed', 'offline-saved', 'app-media-not-ready', 'photo-backup-completed', 'photo-backup-remote-unavailable']) {
    test('light/dark operational state containment: ' + scenario, async ({ browser }) => {
      for (const theme of ['light', 'dark'] as const) {
        const page = await appsPage(browser, 390, theme, scenario);
        try {
          await expectContained(page, 390);
          const manageButton = page.locator('.lite-catalog-app-card').first().getByRole('button', { name: 'Manage', exact: true });
          if (await manageButton.count()) {
            const manage = await openManage(page);
            await expectContained(page, 390);
            await expect(manage.getByRole('button', { name: 'Close app actions' })).toBeVisible();
          }
        } finally { await page.context().close(); }
      }
    });
  }

  for (const theme of ['light', 'dark'] as const) {
    test('mobile snap, keyboard, focus and readable content in ' + theme, async ({ browser }) => {
      const page = await appsPage(browser, 390, theme);
      try {
        const manage = await openManage(page);
        await manage.getByRole('button', { name: 'Compact', exact: true }).click();
        await expect(manage).toHaveAttribute('data-lite-sheet-snap', 'compact');
        await expectContained(page, 390);
        await manage.getByRole('button', { name: 'Expand', exact: true }).click();
        await expect(manage).toHaveAttribute('data-lite-sheet-snap', 'medium');
        await expectContained(page, 390);
        await manage.getByRole('button', { name: 'Expand', exact: true }).click();
        await expect(manage).toHaveAttribute('data-lite-sheet-snap', 'expanded');
        await expectContained(page, 390);
        await manage.getByRole('button', { name: 'Compact', exact: true }).click();
        await expect(manage).toHaveAttribute('data-lite-sheet-snap', 'medium');
        await manage.getByRole('button', { name: 'Compact', exact: true }).click();
        await expect(manage).toHaveAttribute('data-lite-sheet-snap', 'compact');
        await manage.getByRole('button', { name: 'Close app actions' }).click();
        await expect(manage).toHaveCount(0);
      } finally { await page.context().close(); }
    });
  }

  test('200% reflow, reduced motion, focus and accessible Manage/Details remain usable', async ({ browser }) => {
    const page = await appsPage(browser, 320, 'dark');
    try {
      await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
      const manage = await openPhotos(page);
      await expectContained(page, 320);
      const flow = manage.getByRole('region', { name: 'Photo workflow' });
      await flow.getByRole('button', { name: 'View details' }).click();
      await expectContained(page, 320);
      const details = page.locator('.lite-app-premium-details');
      await expect(details).toBeVisible();
      expect(await details.evaluate((node) => getComputedStyle(node).animationName)).toBe('none');
      const analysis = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      expect(analysis.violations).toEqual([]);
      await page.keyboard.press('Escape');
      await expect(manage).toBeVisible();
    } finally { await page.context().close(); }
  });
});
