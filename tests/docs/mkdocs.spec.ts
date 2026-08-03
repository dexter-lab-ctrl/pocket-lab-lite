import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const consoleFailures: string[] = [];
const failedRequests: string[] = [];
const DOCS_PREFIX = '/pocket-lab-lite/';
const SURFACE_SELECTOR = '.md-header__inner, .md-tabs__inner, .md-content, .md-footer__inner, .md-banner__inner';
const TRANSIENT_LAYER_SELECTOR = '[data-md-component="search"], .md-sidebar, .md-nav';

test.beforeEach(async ({ page }) => {
  consoleFailures.length = 0;
  failedRequests.length = 0;
  page.on('console', (message) => {
    if (message.type() === 'error') consoleFailures.push(message.text());
  });
  page.on('pageerror', (error) => consoleFailures.push(`PAGEERROR ${error.message}`));
  page.on('requestfailed', (request) => {
    const url = request.url();
    // MkDocs dev-server live reload uses long-poll requests that are routinely
    // aborted during page navigation and worker teardown. They are transport
    // noise, not broken documentation assets.
    if (url.includes('/livereload/')) return;
    failedRequests.push(`${request.failure()?.errorText || 'requestfailed'} ${url}`);
  });
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
  const architectureFigure = page.locator('.pl-architecture-diagram--system').first();
  await expect(architectureFigure).toBeVisible();
  const diagramLayout = await architectureFigure.evaluate((element) => {
    const images = [...element.querySelectorAll<HTMLImageElement>('.pl-architecture-diagram__image')];
    const image = images.find((candidate) => {
      const candidateRect = candidate.getBoundingClientRect();
      const style = getComputedStyle(candidate);
      return candidateRect.width > 0 &&
        candidateRect.height > 0 &&
        style.display !== 'none' &&
        style.visibility !== 'hidden';
    });
    const viewport = element.querySelector<HTMLElement>('.pl-architecture-diagram__viewport');
    const content = element.closest<HTMLElement>('.md-content');
    const rect = image?.getBoundingClientRect();
    const contentRect = content?.getBoundingClientRect();
    const figureRect = element.getBoundingClientRect();
    const viewportRect = viewport?.getBoundingClientRect();
    return {
      figureContained: contentRect
        ? figureRect.left >= contentRect.left - 1 && figureRect.right <= contentRect.right + 1
        : false,
      viewportContained: viewportRect
        ? viewportRect.left >= figureRect.left - 1 && viewportRect.right <= figureRect.right + 1
        : false,
      imageWidth: rect?.width || 0,
      imageHeight: rect?.height || 0,
      naturalWidth: image?.naturalWidth || 0,
      naturalHeight: image?.naturalHeight || 0,
      viewportWidth: viewport?.clientWidth || 0,
      viewportScrollWidth: viewport?.scrollWidth || 0,
      overflowX: viewport ? getComputedStyle(viewport).overflowX : '',
      visibleImageCount: images.filter((candidate) => {
        const candidateRect = candidate.getBoundingClientRect();
        const style = getComputedStyle(candidate);
        return candidateRect.width > 0 &&
          candidateRect.height > 0 &&
          style.display !== 'none' &&
          style.visibility !== 'hidden';
      }).length,
    };
  });
  expect(diagramLayout.figureContained, JSON.stringify(diagramLayout, null, 2)).toBe(true);
  expect(diagramLayout.viewportContained, JSON.stringify(diagramLayout, null, 2)).toBe(true);
  expect(diagramLayout.visibleImageCount).toBeGreaterThanOrEqual(1);
  expect(diagramLayout.imageWidth).toBeGreaterThan(120);
  expect(diagramLayout.imageHeight).toBeGreaterThan(40);
  expect(diagramLayout.naturalWidth).toBeGreaterThan(0);
  expect(diagramLayout.naturalHeight).toBeGreaterThan(0);
  const renderedRatio = diagramLayout.imageWidth / diagramLayout.imageHeight;
  const intrinsicRatio = diagramLayout.naturalWidth / diagramLayout.naturalHeight;
  expect(Math.abs(renderedRatio - intrinsicRatio) / intrinsicRatio).toBeLessThan(0.02);
  if (testInfo.project.name === 'docs-mobile') {
    expect(['auto', 'scroll']).toContain(diagramLayout.overflowX);
    expect(diagramLayout.viewportScrollWidth).toBeGreaterThan(diagramLayout.viewportWidth);
    expect(diagramLayout.imageHeight).toBeGreaterThan(100);
  } else {
    expect(diagramLayout.imageWidth).toBeLessThanOrEqual(diagramLayout.viewportWidth + 1);
  }

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
  const catalogTable = page.locator('.md-typeset__table').first();
  const liteApiCatalogLink = catalogTable.getByRole('link', { name: 'FastAPI /api/lite/*' });
  await expect(liteApiCatalogLink).toBeVisible();
  await expect(catalogTable).toBeAttached();
  const tableOverflow = await catalogTable.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
    overflowX: window.getComputedStyle(element).overflowX,
  }));
  expect(['auto', 'scroll', 'overlay'], JSON.stringify(tableOverflow)).toContain(tableOverflow.overflowX);
  expect(tableOverflow.scrollWidth).toBeGreaterThanOrEqual(tableOverflow.clientWidth);

  await liteApiCatalogLink.click();
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
    // Close the search overlay before exercising the mobile navigation drawer.
    // Search results intentionally cover the header and otherwise intercept the
    // drawer toggle's pointer events.
    await page.keyboard.press('Escape');
    const searchToggleInput = page.locator('input#__search');
    if (await searchToggleInput.count()) {
      await searchToggleInput.evaluate((element: HTMLInputElement) => {
        element.checked = false;
        element.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }
    await expect(page.locator('[data-md-component="search-result"]')).not.toBeVisible();

    const drawerToggle = page.locator('label.md-header__button[for="__drawer"]');
    await expect(drawerToggle).toBeVisible();
    await drawerToggle.click();
    await expect(page.locator('.md-sidebar--primary')).toBeVisible();
  }

  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''));
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  expect(failedRequests).toEqual([]);
  expect(consoleFailures).toEqual([]);
});
