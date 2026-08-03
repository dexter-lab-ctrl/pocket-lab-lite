import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const consoleFailures: string[] = [];
const externalAssetRequests: string[] = [];
const failedRequests: string[] = [];
const DOCS_PREFIX = '/pocket-lab-lite/';
const SURFACE_SELECTOR = '.md-header__inner, .md-tabs__inner, .md-content, .md-footer__inner, .md-banner__inner';
const TRANSIENT_LAYER_SELECTOR = '[data-md-component="search"], .md-sidebar, .md-nav';

test.beforeEach(async ({ page }) => {
  consoleFailures.length = 0;
  externalAssetRequests.length = 0;
  failedRequests.length = 0;
  page.on('console', (message) => {
    if (message.type() === 'error') consoleFailures.push(message.text());
  });
  page.on('pageerror', (error) => consoleFailures.push(`PAGEERROR ${error.message}`));
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) externalAssetRequests.push(request.url());
  });
  page.on('requestfailed', (request) => failedRequests.push(request.url()));
});

test('documentation portal navigation, theme, search, and accessibility', async ({ page }, testInfo) => {
  await page.goto(DOCS_PREFIX);
  await expect(page.getByRole('heading', { name: 'Pocket Lab Lite Documentation' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Development guide' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Production guide' })).toBeVisible();

  const overflow = await page.evaluate(({ surfaceSelector, transientLayerSelector }) => {
    const viewportWidth = document.documentElement.clientWidth;
    const surfaceRoots = [...document.querySelectorAll<HTMLElement>(surfaceSelector)];
    const candidates = [...new Set(
      surfaceRoots.flatMap((root) => [root, ...root.querySelectorAll<HTMLElement>('*')]),
    )];
    const measured = candidates
      .filter((element) => !element.closest(transientLayerSelector))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return { element, rect, style };
      })
      .filter(({ rect, style }) =>
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== 'none' &&
        style.visibility !== 'hidden' &&
        rect.right > 0 &&
        rect.left < viewportWidth,
      );

    const offenders = measured
      .filter(({ rect }) => rect.right > viewportWidth + 1 || rect.left < -1)
      .slice(0, 12)
      .map(({ element, rect }) => ({
        tag: element.tagName.toLowerCase(),
        className: typeof element.className === 'string' ? element.className : '',
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
      }));

    const delta = measured.reduce(
      (largest, { rect }) => Math.max(largest, rect.right - viewportWidth, -rect.left, 0),
      0,
    );
    return { delta: Math.ceil(delta), offenders };
  }, {
    surfaceSelector: SURFACE_SELECTOR,
    transientLayerSelector: TRANSIENT_LAYER_SELECTOR,
  });
  expect(overflow.delta, JSON.stringify(overflow.offenders, null, 2)).toBeLessThanOrEqual(1);

  const themeToggle = page.locator('[data-md-component="palette"] label:visible').first();
  await expect(themeToggle).toBeVisible();
  await themeToggle.click();

  const searchInput = page.locator('input[data-md-component="search-query"]');
  if (!(await searchInput.isVisible())) {
    const searchToggle = page.locator('label.md-header__button[for="__search"]');
    await expect(searchToggle).toBeVisible();
    await searchToggle.click();
  }
  await expect(searchInput).toBeVisible();
  await searchInput.evaluate((element: HTMLInputElement) => {
    element.focus();
    element.value = '';
    element.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.keyboard.type('Devices', { delay: 35 });
  await expect(searchInput).toHaveValue('Devices');

  const searchResult = page.locator('[data-md-component="search-result"]');
  await expect(searchResult.locator('a').first()).toBeVisible({ timeout: 15_000 });
  await expect(searchResult).toContainText(/Devices/i);

  await page.goto(`${DOCS_PREFIX}generated/development/`);
  await expect(page.locator('.pl-status--verified')).toBeVisible();
  await expect(page.locator('button.md-code__button').first()).toBeAttached();

  await page.goto(`${DOCS_PREFIX}generated/production/architecture/`);
  await expect(page.getByRole('heading', { name: 'Pocket Lab Lite Architecture' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'generated component catalog' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Runtime and PM2 process topology' })).toBeVisible();
  const architectureLight = page.locator('img[src*="complete-system.light.svg"]').first();
  const architectureDark = page.locator('img[src*="complete-system.dark.svg"]').first();
  await expect(architectureLight).toBeAttached();
  await expect(architectureDark).toBeAttached();
  await expect(architectureLight).toHaveAttribute('alt', /Complete Pocket Lab Lite system map/i);
  await expect(architectureDark).toHaveAttribute('alt', /Complete Pocket Lab Lite system map/i);

  for (const asset of [
    `${DOCS_PREFIX}assets/diagrams/production/views/complete-system.light.svg`,
    `${DOCS_PREFIX}assets/diagrams/production/views/complete-system.dark.svg`,
    `${DOCS_PREFIX}assets/diagrams/production/views/runtime-topology.light.svg`,
    `${DOCS_PREFIX}assets/diagrams/production/components/lite-api.light.svg`,
  ]) {
    const response = await page.request.get(asset);
    expect(response.ok(), asset).toBeTruthy();
    const svg = await response.text();
    expect(svg, asset).toContain('<title id=');
    expect(svg, asset).toContain('<desc id=');
    expect(svg, asset).toContain('role="img"');
    expect(svg, asset).not.toMatch(/(?:href|xlink:href)=["'](?:https?:)?\/\//i);
  }

  await page.goto(`${DOCS_PREFIX}generated/production/architecture/runtime-topology/`);
  await expect(page.getByRole('heading', { name: 'Runtime and PM2 process topology' })).toBeVisible();
  await expect(page.locator('img[src*="runtime-topology.light.svg"]')).toBeAttached();

  await page.goto(`${DOCS_PREFIX}generated/production/architecture/component-catalog/`);
  await expect(page.getByRole('heading', { name: 'Component catalog' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'FastAPI /api/lite/*' })).toBeVisible();
  const catalogTable = page.locator('.md-typeset__table').first();
  await expect(catalogTable).toBeAttached();
  const tableOverflow = await catalogTable.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
    overflowX: window.getComputedStyle(element).overflowX,
  }));
  expect(['auto', 'scroll', 'overlay']).toContain(tableOverflow.overflowX);
  expect(tableOverflow.scrollWidth).toBeGreaterThanOrEqual(tableOverflow.clientWidth);

  await page.getByRole('link', { name: 'FastAPI /api/lite/*' }).click();
  await expect(page.getByRole('heading', { name: 'FastAPI /api/lite/*' })).toBeVisible();
  await expect(page.locator('img[src*="components/lite-api.light.svg"]')).toBeAttached();
  await expect(page.locator('img[src*="components/lite-api.dark.svg"]')).toBeAttached();

  const architectureSearch = page.locator('input[data-md-component="search-query"]');
  if (!(await architectureSearch.isVisible())) {
    await page.locator('label.md-header__button[for="__search"]').click();
  }
  await architectureSearch.fill('FastAPI /api/lite');
  const architectureResults = page.locator('[data-md-component="search-result"]');
  await expect(architectureResults.locator('a').first()).toBeVisible({ timeout: 15_000 });
  await expect(architectureResults).toContainText(/FastAPI \/api\/lite/i);

  if (testInfo.project.name === 'docs-mobile') {
    const drawerToggle = page.locator('label.md-header__button[for="__drawer"]');
    await expect(drawerToggle).toBeVisible();
    await drawerToggle.click();
    await expect(page.locator('.md-sidebar--primary')).toBeVisible();
  }

  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''));
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  expect(externalAssetRequests).toEqual([]);
  expect(failedRequests).toEqual([]);
  expect(consoleFailures).toEqual([]);
});
