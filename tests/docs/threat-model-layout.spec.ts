import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const DOCS_PREFIX = '/pocket-lab-lite/';
const OVERVIEW = `${DOCS_PREFIX}generated/enterprise/threat-model/`;
const ARCHITECTURE = `${OVERVIEW}architecture/`;
const CATALOG = `${OVERVIEW}catalog/`;

const svgState = async (object: ReturnType<import('@playwright/test').Page['locator']>) => object.evaluate((node: HTMLObjectElement) => {
  const root = node.contentDocument?.documentElement;
  const boxes = Array.from(node.contentDocument?.querySelectorAll<SVGGElement>('.node') || []).map((item) => ({
    id: item.dataset.node,
    bounds: item.dataset.layoutBounds,
    active: item.classList.contains('is-active'),
  }));
  return {
    engine: root?.dataset.layoutEngine,
    layout: root?.dataset.layout,
    variant: root?.dataset.variant,
    viewMode: root?.dataset.viewMode,
    boxes,
  };
});

test('Threat Model uses one deterministic layout engine with dismissible focus and explicit legends', async ({ page }, testInfo) => {
  await page.goto(OVERVIEW);
  const poster = page.locator('[data-pl-threat-poster="true"]');
  const object = poster.locator('#pl-threat-model-svg');
  await expect(object).toBeVisible();
  await expect.poll(async () => object.evaluate((node: HTMLObjectElement) => Boolean(node.contentDocument?.documentElement))).toBe(true);

  const expectedLayout = testInfo.project.name === 'docs-mobile' ? 'stacked' : 'wide';
  await expect.poll(async () => (await svgState(object)).layout).toBe(expectedLayout);
  expect((await svgState(object)).engine).toBe('canonical-security-layout-v2');
  expect((await svgState(object)).variant).toBe('overview');
  const layoutBoxes = (await svgState(object)).boxes;
  expect(layoutBoxes).toHaveLength(19);
  expect(new Set(layoutBoxes.map((row) => row.bounds)).size).toBe(19);
  expect(layoutBoxes.every((row) => /^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?,\d+(?:\.\d+)?,\d+(?:\.\d+)?$/.test(row.bounds || ''))).toBe(true);

  const mode = poster.locator('[data-threat-poster-mode="controls"]');
  await mode.click();
  await expect(mode).toHaveAttribute('aria-pressed', 'true');
  await expect(mode).toHaveAttribute('data-selected', 'true');

  const stride = poster.locator('[data-stride-lens="Tampering"]');
  await stride.click();
  await expect(stride).toHaveAttribute('aria-pressed', 'true');
  await expect(stride).toHaveAttribute('data-selected', 'true');

  await expect(poster.locator('.pl-threat-legend-item')).toHaveCount(5);
  await expect(poster.locator('.pl-threat-legend-note')).toContainText('never live traffic');

  await object.evaluate((node: HTMLObjectElement) => {
    const doc = node.contentDocument;
    const target = doc?.querySelector<SVGGElement>('.node[data-node="lite-api"]');
    target?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  await expect.poll(async () => (await svgState(object)).boxes.find((row) => row.id === 'lite-api')?.active).toBe(true);

  await object.evaluate((node: HTMLObjectElement) => {
    const target = node.contentDocument?.querySelector<SVGRectElement>('[data-reset-target="true"]');
    target?.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
  });
  await expect.poll(async () => (await svgState(object)).boxes.some((row) => row.active)).toBe(false);
  await expect(page).not.toHaveURL(/atlas-(system|control|attack-path)=/);

  await page.keyboard.press('Escape');
  await expect.poll(async () => (await svgState(object)).boxes.some((row) => row.active)).toBe(false);

  await page.goto(ARCHITECTURE);
  const detail = page.locator('.pl-threat-detail-diagram img');
  await expect(detail).toBeVisible();
  await expect.poll(async () => detail.evaluate(
    (image: HTMLImageElement) => image.currentSrc || image.src,
  )).toMatch(
    new RegExp(
      testInfo.project.name === 'docs-mobile'
        ? 'threat-model-detail-mobile\\.svg$'
        : 'threat-model-detail\\.svg$',
    ),
  );
  await expect(page.locator('.pl-threat-detail-diagram + .pl-threat-legend .pl-threat-legend-item')).toHaveCount(5);

  await page.goto(`${CATALOG}?atlas-attack-path=AP-04#security-atlas`);
  const atlasObject = page.locator('.pl-threat-canvas #pl-threat-model-svg');
  await expect(atlasObject).toBeVisible();
  await expect.poll(async () => atlasObject.evaluate((node: HTMLObjectElement) => Boolean(node.contentDocument?.documentElement))).toBe(true);
  expect((await svgState(atlasObject)).variant).toBe('catalog');
  await expect(page.locator('.pl-threat-canvas > .pl-threat-legend .pl-threat-legend-item')).toHaveCount(5);

  const diagramControls = page.locator('[data-threat-mode="controls"]');
  await diagramControls.click();
  await expect(diagramControls).toHaveAttribute('aria-pressed', 'true');
  await expect(diagramControls).toHaveAttribute('data-selected', 'true');
  await expect.poll(async () => (await svgState(atlasObject)).viewMode).toBe('controls');

  const systemAtlas = page.locator('[data-atlas-view="system"]');
  await systemAtlas.click();
  await expect(systemAtlas).toHaveAttribute('aria-selected', 'true');
  await expect(systemAtlas).toHaveAttribute('data-selected', 'true');

  await atlasObject.evaluate((node: HTMLObjectElement) => {
    const doc = node.contentDocument;
    const target = doc?.querySelector<SVGGElement>('.node[data-node="lite-api"]');
    target?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  await expect.poll(async () => (await svgState(atlasObject)).boxes.find((row) => row.id === 'lite-api')?.active).toBe(true);
  await atlasObject.evaluate((node: HTMLObjectElement) => {
    const target = node.contentDocument?.querySelector<SVGRectElement>('[data-reset-target="true"]');
    target?.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
  });
  await expect.poll(async () => (await svgState(atlasObject)).boxes.some((row) => row.active)).toBe(false);
  await expect(page).not.toHaveURL(/atlas-(system|control|attack-path)=/);

  const axe = await new AxeBuilder({ page }).include('.md-content').analyze();
  const serious = axe.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''));
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);

  if (testInfo.project.name === 'docs-mobile') {
    const overflow = await page.locator('.md-content').evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
      bodyScrollWidth: document.body.scrollWidth,
    }));
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
    expect(overflow.bodyScrollWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1);
  }
});
