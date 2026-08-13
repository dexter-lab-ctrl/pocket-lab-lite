import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const consoleFailures: string[] = [];
const failedRequests: string[] = [];
const externalRuntimeRequests: string[] = [];
const DOCS_PREFIX = '/pocket-lab-lite/';
const SURFACE_SELECTOR = '.md-header__inner, .md-tabs__inner, .md-content, .md-footer__inner, .md-banner__inner';
const TRANSIENT_LAYER_SELECTOR = '[data-md-component="search"], .md-sidebar, .md-nav';

const expectNoExternalRuntimeRequests = () => {
  expect(
    externalRuntimeRequests,
    `Unexpected external documentation runtime requests:\n${externalRuntimeRequests.join('\n')}`,
  ).toEqual([]);
};

test.beforeEach(async ({ page }) => {
  consoleFailures.length = 0;
  failedRequests.length = 0;
  externalRuntimeRequests.length = 0;
  page.on('request', (request) => {
    let url: URL;

    try {
      url = new URL(request.url());
    } catch {
      return;
    }

    if (!['http:', 'https:'].includes(url.protocol)) return;

    const isLocalDocsRuntime =
      ['127.0.0.1', 'localhost'].includes(url.hostname);

    if (isLocalDocsRuntime) return;

    externalRuntimeRequests.push(
      `${request.method()} ${request.resourceType()} ${url.toString()}`,
    );
  });

  page.on('console', (message) => {
    if (message.type() !== 'error') return;

    const location = message.location();
    const source = location.url
      ? ` [${location.url}:${location.lineNumber ?? 0}:${location.columnNumber ?? 0}]`
      : '';

    consoleFailures.push(`${message.text()}${source}`);
  });
  page.on('pageerror', (error) => consoleFailures.push(`PAGEERROR ${error.message}`));
  page.on('requestfailed', (request) => {
    const url = request.url();
    const failure = request.failure()?.errorText || 'requestfailed';

    // MkDocs development live reload uses requests that are routinely
    // cancelled during navigation and teardown.
    if (url.includes('/livereload/')) return;

    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      failedRequests.push(`${failure} ${url}`);
      return;
    }

    const isLocalDocsPageAbort =
      failure === 'net::ERR_ABORTED'
      && ['127.0.0.1', 'localhost'].includes(parsed.hostname)
      && parsed.pathname.startsWith(DOCS_PREFIX)
      && parsed.pathname.endsWith('/');

    // Material for MkDocs instant navigation may cancel a redundant
    // same-origin HTML-page request while the requested destination still
    // loads successfully. Destination headings/content are asserted by the
    // test itself, so this transport cancellation is not a broken asset.
    //
    // Do NOT suppress aborted assets, scripts, stylesheets, SVGs, external
    // requests, DNS failures, connection failures, or other error classes.
    if (isLocalDocsPageAbort) return;

    failedRequests.push(`${failure} ${url}`);
  });

  page.on('response', (response) => {
    const status = response.status();

    if (status < 400) return;

    const url = response.url();

    // MkDocs development live reload is infrastructure noise and is already
    // excluded from requestfailed handling.
    if (url.includes('/livereload/')) return;

    failedRequests.push(`HTTP ${status} ${url}`);
  });
});

test('documentation portal navigation, theme, search, and accessibility', async ({ page }, testInfo) => {

  test.setTimeout(90_000);
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
  await expect(page.locator('.pl-architecture-summary-card')).toHaveCount(6);
  await expect(page.locator('.pl-architecture-icon--brand').first()).toBeVisible();
  const architectureLight = page.locator('img[src*="complete-system.light.svg"]').first();
  const architectureDark = page.locator('img[src*="complete-system.dark.svg"]').first();
  await expect(architectureLight).toBeAttached();
  await expect(architectureDark).toBeAttached();
  await expect(architectureLight).toHaveAttribute('alt', /Complete Pocket Lab Lite executive architecture poster/i);
  await expect(architectureDark).toHaveAttribute('alt', /Complete Pocket Lab Lite executive architecture poster/i);
  const architectureFigure = page.locator('.pl-architecture-diagram--system').first();
  await expect(architectureFigure).toBeVisible();

  // Capture the exact browser and network state if the poster fails to render.
  // This deliberately keeps the production assertions strict while making the
  // failure actionable instead of collapsing every cause to a boolean false.
  type ArchitectureImageState = {
    className: string;
    src: string;
    currentSrc: string;
    complete: boolean;
    naturalWidth: number;
    naturalHeight: number;
    clientWidth: number;
    clientHeight: number;
    rectWidth: number;
    rectHeight: number;
    display: string;
    visibility: string;
    opacity: string;
  };
  type ArchitecturePosterState = {
    scheme: string | null;
    readyState: string;
    figureWidth: number;
    figureHeight: number;
    images: ArchitectureImageState[];
  };

  const readArchitecturePosterState = async (): Promise<ArchitecturePosterState> =>
    architectureFigure.evaluate((element) => ({
      scheme:
        document.documentElement.getAttribute('data-md-color-scheme') ||
        document.body.getAttribute('data-md-color-scheme'),
      readyState: document.readyState,
      figureWidth: element.getBoundingClientRect().width,
      figureHeight: element.getBoundingClientRect().height,
      images: [...element.querySelectorAll<HTMLImageElement>('.pl-architecture-diagram__image')].map((image) => {
        const rect = image.getBoundingClientRect();
        const style = getComputedStyle(image);
        return {
          className: image.className,
          src: image.getAttribute('src') || '',
          currentSrc: image.currentSrc,
          complete: image.complete,
          naturalWidth: image.naturalWidth,
          naturalHeight: image.naturalHeight,
          clientWidth: image.clientWidth,
          clientHeight: image.clientHeight,
          rectWidth: rect.width,
          rectHeight: rect.height,
          display: style.display,
          visibility: style.visibility,
          opacity: style.opacity,
        };
      }),
    }));

  let lastPosterState = await readArchitecturePosterState();
  try {
    await expect.poll(async () => {
      lastPosterState = await readArchitecturePosterState();
      return lastPosterState.images.some((candidate) =>
        candidate.complete &&
        candidate.naturalWidth > 0 &&
        candidate.naturalHeight > 0 &&
        candidate.rectWidth > 120 &&
        candidate.rectHeight > 40 &&
        candidate.display !== 'none' &&
        candidate.visibility !== 'hidden'
      );
    }, {
      message: 'architecture poster should finish loading and render one theme image',
      timeout: 15_000,
    }).toBe(true);
  } catch (error) {
    const responseStates = await Promise.all(lastPosterState.images.map(async (image) => {
      const response = image.currentSrc ? await page.request.get(image.currentSrc) : null;
      return {
        src: image.currentSrc || image.src,
        status: response?.status() ?? null,
        ok: response?.ok() ?? false,
        contentType: response?.headers()['content-type'] || '',
      };
    }));
    throw new Error(
      `Architecture poster diagnostic:
${JSON.stringify({ ...lastPosterState, responses: responseStates }, null, 2)}

${String(error)}`
    );
  }

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

  await page.goto(`${DOCS_PREFIX}generated/production/architecture/complete-system/`);
  await expect(page.getByRole('heading', { name: 'Complete Pocket Lab Lite system map' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Executive summary' })).toBeVisible();
  await expect(page.locator('.pl-architecture-zone-card')).toHaveCount(6);
  await expect(page.locator('.pl-architecture-legend')).toBeVisible();
  await expect(page.getByText('Zone A — Experience')).toBeVisible();
  await expect(page.getByText('Zone F — Remote access and apps')).toBeVisible();
  await expect(page.locator('img[src*="icons/fastapi.svg"]').first()).toBeAttached();
  await expect(page.locator('img[src*="icons/nats.svg"]').first()).toBeAttached();
  await expect(page.locator('img[src*="icons/caddy.svg"]').first()).toBeAttached();

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
  const liteApiLightDiagram = page.locator('img[src*="components/lite-api.light.svg"]');
  await expect(liteApiLightDiagram).toBeAttached();
  await expect(page.locator('img[src*="components/lite-api.dark.svg"]')).toBeAttached();

  // Embedded diagrams must be self-contained because browsers do not load
  // nested external SVG icon assets when the parent SVG is displayed via img.
  const liteApiDiagramSource = await liteApiLightDiagram.getAttribute('src');
  expect(liteApiDiagramSource).toBeTruthy();
  const liteApiDiagramUrl = new URL(liteApiDiagramSource!, page.url()).toString();
  const liteApiDiagramResponse = await page.request.get(liteApiDiagramUrl);
  expect(liteApiDiagramResponse.ok()).toBe(true);
  expect(liteApiDiagramResponse.headers()['content-type']).toContain('image/svg+xml');
  const liteApiDiagramSvg = await liteApiDiagramResponse.text();
  expect(liteApiDiagramSvg).toContain('<symbol id="pl-icon-');
  expect(liteApiDiagramSvg).toContain('<use class="pl-node-icon__primary"');
  expect(liteApiDiagramSvg).not.toContain('<image href=');
  expect(liteApiDiagramSvg).not.toContain('PLICON__');

  const architectureSearch = page.locator('input[data-md-component="search-query"]');
  if (!(await architectureSearch.isVisible())) {
    await page.locator('label.md-header__button[for="__search"]').click();
  }
  // Material search is worker-backed. Reusing fill() with punctuation after
  // several full-page navigations can race the worker's query subscription and
  // leave the result surface empty. Reset the input through real keyboard
  // events, as above, and use a punctuation-safe token while still asserting
  // that the canonical FastAPI /api/lite component is returned.
  await architectureSearch.focus();
  await architectureSearch.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A');
  await architectureSearch.press('Backspace');
  await page.keyboard.type('FastAPI', { delay: 35 });
  await expect(architectureSearch).toHaveValue('FastAPI');
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

test('documentation intelligence dashboard is responsive, progressive, and evidence-aware', async ({ page }, testInfo) => {
  await page.goto(DOCS_PREFIX);
  await expect(page.locator('[data-pl-dashboard="true"]')).toBeVisible();
  await expect(page.getByText('Documentation Control Center')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Current operational health' })).toBeVisible();
  await expect(page.locator('.pl-health-card')).toHaveCount(5);
  const recoveryHealthCard = page
    .locator('.pl-health-card')
    .filter({ hasText: 'Backup & Restore' });

  await expect(recoveryHealthCard).toHaveCount(1);
  await expect(
    recoveryHealthCard.getByText('projection_too_old', { exact: true }),
  ).toBeVisible();

  const dashboardOverflow = await page.locator('[data-pl-dashboard="true"]').evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  expect(dashboardOverflow.scrollWidth).toBeLessThanOrEqual(dashboardOverflow.clientWidth + 1);

  await page.goto(`${DOCS_PREFIX}generated/development/intelligence/dependency-health/`);
  await expect(page.getByRole('heading', { name: 'Service and dependency health' })).toBeVisible();
  await expect(page.locator('.pl-status-strip').first()).toBeVisible();
  // Scope evidence assertions to Material's rendered article, never to
  // <main>, because desktop Material navigation can place hidden labels
  // inside the broader main DOM tree.
  const dependencyContent = page
    .locator('.md-content__inner.md-typeset')
    .first();

  await expect(dependencyContent).toBeVisible();
  await expect(dependencyContent).toContainText(/Lynis/i);
  await expect(dependencyContent).toContainText(/unvalidated/i);

  // If the requested evidence is intentionally behind progressive
  // disclosure, exercise the real disclosure interaction before making
  // visibility assertions. Do not assume a fixed DOM position.
  const lynisDisclosure = dependencyContent
    .locator('details')
    .filter({ hasText: /Lynis/i })
    .first();

  if (await lynisDisclosure.count()) {
    const lynisSummary = lynisDisclosure.locator('summary').first();

    await expect(lynisSummary).toBeVisible();

    const alreadyOpen = await lynisDisclosure.evaluate(
      (element: HTMLDetailsElement) => element.open,
    );

    if (!alreadyOpen) {
      await lynisSummary.click();
    }

    await expect(lynisDisclosure).toHaveAttribute('open', '');
    await expect(lynisDisclosure).toContainText(/Lynis/i);
    await expect(lynisDisclosure).toContainText(/unvalidated/i);
  }

  await page.goto(`${DOCS_PREFIX}generated/development/intelligence/evidence-lineage/`);
  await expect(page.getByRole('heading', { name: 'Why do we believe this?' })).toBeVisible();
  await expect(page.locator('.pl-lineage').first()).toBeVisible();
  const disclosure = page.locator('details.pl-disclosure').first();
  await expect(disclosure).toBeVisible();
  expect(await disclosure.getAttribute('open')).toBeNull();

  await page.goto(`${DOCS_PREFIX}generated/development/intelligence/release-impact/`);
  await expect(page.getByRole('heading', { name: 'What changed?' })).toBeVisible();

  const releaseImpactContent = page
    .locator('.md-content__inner.md-typeset')
    .first();
  const releaseImpactKpis = releaseImpactContent
    .locator('.pl-release-kpis')
    .first();

  await expect(releaseImpactContent.getByText('Release impact summary')).toBeVisible();
  await expect(releaseImpactContent.getByRole('heading', { name: 'Executive summary' })).toBeVisible();
  await expect(releaseImpactKpis).toBeVisible();
  await expect(releaseImpactKpis).toContainText('Comparison basis');
  await expect(releaseImpactKpis).toContainText(
    /Canonical release evidence not yet promoted|Initial canonical comparison baseline|Verified release-to-release comparison|Verified releases awaiting local comparison history/,
  );
  await expect(releaseImpactContent).not.toContainText('No comparable verified prior release');

  await page.goto(`${DOCS_PREFIX}generated/production/intelligence/what-changed/`);

  const technicalDelta = page.locator('.pl-technical-delta').first();
  await expect(technicalDelta).toBeVisible();
  await expect(technicalDelta).toContainText('Machine-derived release dimensions');
  await expect(technicalDelta.locator('.pl-delta-card')).toHaveCount(22);
  await expect(technicalDelta).not.toContainText('Raw classifications and source paths');

  const firstDeltaCard = technicalDelta.locator('.pl-delta-card').first();
  await expect(firstDeltaCard).toBeVisible();
  await firstDeltaCard.locator('summary').click();
  await expect(firstDeltaCard.locator('.pl-delta-sources')).toBeVisible();

  if (testInfo.project.name === 'docs-mobile') {
    const deltaLayout = await technicalDelta.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));

    expect(deltaLayout.scrollWidth).toBeLessThanOrEqual(
      deltaLayout.clientWidth + 1,
    );
  }

  if (testInfo.project.name === 'docs-mobile') {
    await page.goto(
      `${DOCS_PREFIX}generated/development/intelligence/platform-matrix/`,
    );

    const capabilityMatrix = page
      .locator('.pl-capability-matrix')
      .first();

    await expect(capabilityMatrix).toBeVisible();

    // Responsive behavior is validated from computed browser layout,
    // not from a transient CSS wrapper class.
    const matrixLayout = await capabilityMatrix.evaluate((matrix) => {
      const viewportWidth = document.documentElement.clientWidth;
      const matrixRect = matrix.getBoundingClientRect();

      let candidate: HTMLElement | null = matrix.parentElement;
      let scrollHost: HTMLElement | null = null;

      while (candidate && candidate !== document.body) {
        const style = window.getComputedStyle(candidate);
        const overflowX = style.overflowX;

        if (
          overflowX === 'auto' ||
          overflowX === 'scroll'
        ) {
          scrollHost = candidate;
          break;
        }

        candidate = candidate.parentElement;
      }

      return {
        viewportWidth,
        matrixLeft: matrixRect.left,
        matrixRight: matrixRect.right,
        scrollContainerFound: Boolean(scrollHost),
        scrollClientWidth: scrollHost?.clientWidth ?? 0,
        scrollWidth: scrollHost?.scrollWidth ?? 0,
      };
    });

    expect(
      matrixLayout.scrollContainerFound,
      'Platform capability matrix must have a bounded horizontal scroll container on mobile',
    ).toBeTruthy();

    expect(
      matrixLayout.scrollClientWidth,
      'Platform Matrix scroll container must fit within the viewport',
    ).toBeLessThanOrEqual(matrixLayout.viewportWidth + 1);

    expect(
      matrixLayout.scrollWidth,
      'Platform Matrix scroll region must contain at least its visible width',
    ).toBeGreaterThanOrEqual(matrixLayout.scrollClientWidth);
  }

  expectNoExternalRuntimeRequests();
  expect(consoleFailures, consoleFailures.join('\n')).toEqual([]);
  expect(failedRequests, failedRequests.join('\n')).toEqual([]);
});

test('Security Atlas is a responsive catalog with deterministic deep links and no runtime polling', async ({ page }) => {
  await page.goto(`${DOCS_PREFIX}generated/enterprise/threat-model/#attack-path=AP-04`);

  await expect(page.locator('h1#threat-model')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Security Atlas' })).toBeVisible();
  await expect(page.locator('.pl-security-atlas-poster img')).toBeVisible();

  const selection = page.locator('#threat-selection');
  await expect(selection).toContainText('Attack path AP-04');
  await expect(selection).toContainText('Messaging command tampering or replay');

  const ap04 = page.locator('[data-catalog-kind="attack-path"][data-catalog-target="AP-04"]').first();
  await expect(ap04).toBeVisible();
  await expect(ap04).toHaveAttribute('aria-pressed', 'true');
  await expect(page).toHaveURL(/#attack-path=AP-04$/);

  const attackSurfaceTab = page.locator('[data-atlas-view="attack-surface"]');
  await expect(attackSurfaceTab).toHaveAttribute('aria-selected', 'true');

  await page.locator('[data-atlas-view="controls"]').click();
  const control = page.locator('[data-catalog-kind="control"]').first();
  await expect(control).toBeVisible();
  const controlTarget = await control.getAttribute('data-catalog-target');
  await control.click();
  await expect(selection).toContainText(/Control CTRL-/);
  expect(controlTarget).toBeTruthy();
  await expect(page).toHaveURL((url) =>
    url.searchParams.get('atlas-control') === controlTarget
    && url.hash === '#security-atlas'
  );

  const runtimeRequests = await page.evaluate(() => performance
    .getEntriesByType('resource')
    .map((entry) => (entry as PerformanceResourceTiming).name)
    .filter((url) => /\/api\//.test(new URL(url).pathname)));
  expect(runtimeRequests).toEqual([]);

  const layout = await page.evaluate(() => {
    const viewport = document.documentElement.clientWidth;
    const atlas = document.querySelector<HTMLElement>('.pl-atlas-layout');

    if (!atlas) {
      return {
        viewport,
        atlasWidth: 0,
        atlasScrollWidth: 0,
        atlasClientWidth: 0,
        atlasLeft: 0,
        atlasRight: 0,
        overflowers: [],
      };
    }

    const atlasRect = atlas.getBoundingClientRect();

    const overflowers = Array.from(atlas.querySelectorAll<HTMLElement>('*'))
      .filter((element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();

        return (
          !element.hidden
          && style.display !== 'none'
          && style.visibility !== 'hidden'
          && rect.width > 0
          && rect.height > 0
        );
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();

        return {
          tag: element.tagName.toLowerCase(),
          id: element.id,
          className: typeof element.className === 'string' ? element.className : '',
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
        };
      })
      .filter(({ left, right }) =>
        left < atlasRect.left - 1 || right > atlasRect.right + 1
      )
      .slice(0, 20);

    return {
      viewport,
      atlasWidth: atlasRect.width,
      atlasScrollWidth: atlas.scrollWidth,
      atlasClientWidth: atlas.clientWidth,
      atlasLeft: atlasRect.left,
      atlasRight: atlasRect.right,
      overflowers,
    };
  });

  expect(layout.atlasWidth).toBeGreaterThan(0);

  expect(
    layout.atlasRight,
    `Security Atlas exceeds viewport: ${JSON.stringify(layout, null, 2)}`,
  ).toBeLessThanOrEqual(layout.viewport + 1);

  expect(
    layout.atlasScrollWidth,
    `Security Atlas internal horizontal overflow:\n${JSON.stringify(layout.overflowers, null, 2)}`,
  ).toBeLessThanOrEqual(layout.atlasClientWidth + 1);

  expect(
    layout.overflowers,
    `Security Atlas descendants exceed their layout boundary:\n${JSON.stringify(layout.overflowers, null, 2)}`,
  ).toEqual([]);

  expectNoExternalRuntimeRequests();
  expect(consoleFailures, consoleFailures.join('\n')).toEqual([]);
  expect(failedRequests, failedRequests.join('\n')).toEqual([]);
});
